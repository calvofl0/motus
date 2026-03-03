"""
Disk-usage polling: df (local), rclone about/size (remote), optional override script.

Precedence (lowest → highest):
  df / rclone about / rclone size  →  override script

The override script outputs one line per location:
    <path> <space_used_1024blocks|undef> <quota_1024blocks|undef> <count|undef>
where <path> may be surrounded by double-quotes.
Local paths start with '/'; S3 locations start with 'https://'.
"""

import json
import logging
import os
import subprocess
import threading
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# rclone remote types that use the S3 API.
_S3_TYPES = frozenset({
    's3', 'b2', 'wasabi', 'minio', 'ceph', 'digitalocean', 'dreamhost',
    'ibmcos', 'scaleway', 'stackpath', 'alibaba', 'qingstor', 'huaweiobs',
})

# Module-level registry of active background fetches.
_lock = threading.Lock()
_active_procs: dict[str, list[subprocess.Popen]] = {}
_active_threads: dict[str, threading.Thread] = {}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Canonical key helpers ─────────────────────────────────────────────────────

def resolve_canonical(remote: str, path: str, rclone_config) -> tuple[Optional[str], str]:
    """
    Map a (remote, path) pair – after full alias-chain resolution – to a
    canonical location key and a storage type.

    storage_type:
      'local'      – bare local filesystem path
      's3_at_root' – S3 remote with no bucket selected (key is None)
      's3'         – S3 bucket or sub-prefix
      'other'      – any other rclone backend

    canonical_key:
      '/abs/path'                           for local
      'https://<endpoint>/<bucket>[/path]'  for S3
      'rclone:<remote>:<path>'              for other
      None                                  when storage_type == 's3_at_root'
    """
    # Resolve through the alias chain first.
    try:
        resolved_remote, resolved_path = rclone_config.resolve_alias_chain(remote, path)
    except Exception:
        resolved_remote, resolved_path = remote, path

    if not resolved_remote:
        return resolved_path or '/', 'local'

    cfg = rclone_config.get_remote(resolved_remote) or {}
    rtype = cfg.get('type', '').lower()

    if rtype in _S3_TYPES:
        endpoint = (cfg.get('endpoint') or 'https://s3.amazonaws.com').rstrip('/')
        if not endpoint.startswith('http'):
            endpoint = 'https://' + endpoint

        # resolved_path for S3 looks like "bucket[/sub/path]" or empty.
        bucket = resolved_path.lstrip('/').split('/')[0] if resolved_path.strip('/') else ''
        if not bucket:
            return None, 's3_at_root'

        rest = '/'.join(resolved_path.lstrip('/').split('/')[1:])
        canonical = f'{endpoint}/{bucket}'
        if rest:
            canonical += f'/{rest}'
        return canonical, 's3'

    return f'rclone:{resolved_remote}:{resolved_path.lstrip("/")}', 'other'


def s3_bucket_root(remote: str, path: str, rclone_config) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """
    For an S3 location, return (resolved_remote, bucket, bucket_canonical_key).
    Returns (None, None, None) if not applicable.
    """
    try:
        resolved_remote, resolved_path = rclone_config.resolve_alias_chain(remote, path)
    except Exception:
        resolved_remote, resolved_path = remote, path

    if not resolved_remote:
        return None, None, None

    cfg = rclone_config.get_remote(resolved_remote) or {}
    rtype = cfg.get('type', '').lower()
    if rtype not in _S3_TYPES:
        return None, None, None

    endpoint = (cfg.get('endpoint') or 'https://s3.amazonaws.com').rstrip('/')
    if not endpoint.startswith('http'):
        endpoint = 'https://' + endpoint

    bucket = resolved_path.lstrip('/').split('/')[0] if resolved_path.strip('/') else ''
    if not bucket:
        return None, None, None

    return resolved_remote, bucket, f'{endpoint}/{bucket}'


def find_best_match(canonical: str, rows: list[dict]) -> Optional[dict]:
    """
    Return the DB row whose ``location`` is the longest ancestor prefix of
    ``canonical``.  A prefix is valid if it equals ``canonical`` exactly or if
    the next character in ``canonical`` after the prefix is ``/``.
    """
    best, best_len = None, -1
    for row in rows:
        loc = row['location'].rstrip('/')
        if canonical == loc or canonical.startswith(loc + '/'):
            if len(loc) > best_len:
                best, best_len = row, len(loc)
    return best


# ── Script parsing ────────────────────────────────────────────────────────────

def _tokenize(line: str) -> list[str]:
    """
    Split on whitespace (space or tab) outside double-quotes.
    Double-quotes themselves are stripped from tokens.
    """
    tokens, cur, in_q = [], [], False
    for ch in line:
        if ch == '"':
            in_q = not in_q
        elif not in_q and ch in (' ', '\t'):
            if cur:
                tokens.append(''.join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        tokens.append(''.join(cur))
    return tokens


def _blocks_to_bytes(s: str) -> Optional[int]:
    """Parse a 1024-block count → bytes, or None for 'undef' / '-'."""
    if s.lower() in ('undef', '-', ''):
        return None
    try:
        return int(s) * 1024
    except ValueError:
        return None


def _to_count(s: str) -> Optional[int]:
    """Parse a raw integer count, or None for 'undef' / '-'."""
    if s.lower() in ('undef', '-', ''):
        return None
    try:
        return int(s)
    except ValueError:
        return None


def parse_script_output(text: str) -> list[dict]:
    """
    Parse the script's stdout.  Each non-comment line has the form:
        <path> <space_used_1024blocks> <quota_1024blocks> <count>
    Returns list of dicts: {location, space_used_bytes, quota_bytes, object_count}.
    """
    results = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        tokens = _tokenize(line)
        if len(tokens) < 4:
            logger.warning('disk_usage script: malformed line %r', line)
            continue
        # Last 3 tokens are the metrics; everything before is the path.
        path = ' '.join(tokens[:-3])
        used_str, quota_str, count_str = tokens[-3], tokens[-2], tokens[-1]
        results.append({
            'location':        path,
            'space_used_bytes': _blocks_to_bytes(used_str),
            'quota_bytes':      _blocks_to_bytes(quota_str),
            'object_count':     _to_count(count_str),
        })
    return results


def run_script(script_path: str, timeout: int = 30) -> list[dict]:
    """Execute the override script and parse its output. Returns [] on failure."""
    try:
        result = subprocess.run(
            [script_path],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0:
            logger.warning(
                'disk_usage script exited %d: %s',
                result.returncode, result.stderr[:300],
            )
        return parse_script_output(result.stdout)
    except Exception as exc:
        logger.error('disk_usage script %r failed: %s', script_path, exc)
        return []


# ── df ────────────────────────────────────────────────────────────────────────

def _run_df(extra_args: list[str]) -> str:
    try:
        r = subprocess.run(
            ['df', '-P'] + extra_args,
            capture_output=True, text=True, timeout=15,
        )
        return r.stdout
    except Exception as exc:
        logger.error('df failed: %s', exc)
        return ''


def fetch_all_local_stats() -> dict[str, dict]:
    """
    Run ``df -P`` and ``df -P --inodes`` globally (no path argument).

    Returns a dict keyed by mount point:
        {'/nas': {'space_used_bytes': N, 'quota_bytes': M, 'object_count': K}, ...}
    """
    result: dict[str, dict] = {}

    # Block-level stats.
    for line in _run_df([]).splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            result.setdefault(parts[5], {}).update({
                'quota_bytes':      int(parts[1]) * 1024,
                'space_used_bytes': int(parts[2]) * 1024,
            })
        except (ValueError, IndexError):
            continue

    # Inode stats.
    for line in _run_df(['--inodes']).splitlines()[1:]:
        parts = line.split()
        if len(parts) < 6:
            continue
        try:
            result.setdefault(parts[5], {}).update({
                'object_count': int(parts[2]),
            })
        except (ValueError, IndexError):
            continue

    return result


# ── Background rclone about + size ───────────────────────────────────────────

def _rclone_base_cmd(rclone_path: str, config_file: str) -> list[str]:
    devnull = 'NUL' if os.name == 'nt' else '/dev/null'
    return [rclone_path, '--config', config_file or devnull]


def _register_proc(key: str, proc: subprocess.Popen):
    with _lock:
        _active_procs.setdefault(key, []).append(proc)


def _unregister_proc(key: str, proc: subprocess.Popen):
    with _lock:
        lst = _active_procs.get(key, [])
        try:
            lst.remove(proc)
        except ValueError:
            pass
        if not lst:
            _active_procs.pop(key, None)


def cancel_fetch(canonical_key: str):
    """Terminate all active subprocesses for the given canonical key."""
    with _lock:
        procs = list(_active_procs.get(canonical_key, []))
    for proc in procs:
        try:
            proc.terminate()
        except Exception:
            pass
    with _lock:
        _active_procs.pop(canonical_key, None)


def _background_fetch(
    canonical_key: str,
    resolved_remote: str,
    rclone_target: str,      # e.g. "my_s3:mybucket" or "gdrive:/"
    rclone_path: str,
    config_file: str,
    db,
):
    """
    Run ``rclone about`` then (if needed) ``rclone size`` for a non-local location.
    Updates the DB with NULL-filling semantics. Clears ``is_computing`` when done.
    """
    try:
        space_used = quota = count = None
        base = _rclone_base_cmd(rclone_path, config_file)

        # 1. rclone about (at the remote root — fast API call).
        about_target = f'{resolved_remote}:'
        cmd = base + ['about', about_target, '--json']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _register_proc(canonical_key, proc)
        stdout, _ = proc.communicate()
        _unregister_proc(canonical_key, proc)

        if proc.returncode == 0:
            try:
                data = json.loads(stdout)
                space_used = data.get('used')
                quota      = data.get('total')
            except Exception:
                pass

        # 2. rclone size (bucket/path root) — only if space_used still unknown.
        if space_used is None:
            cmd = base + ['size', rclone_target, '--json']
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _register_proc(canonical_key, proc)
            stdout, _ = proc.communicate()
            _unregister_proc(canonical_key, proc)

            if proc.returncode == 0:
                try:
                    data = json.loads(stdout)
                    space_used = data.get('bytes')
                    count      = data.get('count')
                except Exception:
                    pass

        if space_used is not None or quota is not None or count is not None:
            db.upsert_disk_usage_from_rclone(
                canonical_key,
                space_used_bytes=space_used,
                quota_bytes=quota,
                object_count=count,
                fetched_at=_utcnow(),
            )

    except Exception as exc:
        logger.error('disk_usage background fetch for %s: %s', canonical_key, exc)
    finally:
        db.set_computing(canonical_key, False)
        with _lock:
            _active_threads.pop(canonical_key, None)


def start_background_fetch(
    canonical_key: str,
    resolved_remote: str,
    rclone_target: str,
    rclone_path: str,
    config_file: str,
    db,
):
    """
    Spawn the background fetch thread for a non-local location, unless one is
    already running for the same key.
    """
    with _lock:
        existing = _active_threads.get(canonical_key)
        if existing and existing.is_alive():
            return   # already in flight

    db.set_computing(canonical_key, True)

    thread = threading.Thread(
        target=_background_fetch,
        args=(canonical_key, resolved_remote, rclone_target,
              rclone_path, config_file, db),
        daemon=True,
        name=f'disk-usage-{canonical_key[:50]}',
    )
    with _lock:
        _active_threads[canonical_key] = thread
    thread.start()


# ── Startup / refresh orchestration ──────────────────────────────────────────

def startup_populate(config, db):
    """
    Called once at Motus startup.
    1. Runs ``df`` globally and populates all local mount points.
    2. Runs the override script (if configured) — results take precedence.
    """
    now = _utcnow()

    # 1. df — covers all local filesystems immediately.
    local_stats = fetch_all_local_stats()
    for mount, stats in local_stats.items():
        db.upsert_disk_usage_from_df(
            location=mount,
            space_used_bytes=stats.get('space_used_bytes'),
            quota_bytes=stats.get('quota_bytes'),
            object_count=stats.get('object_count'),
            fetched_at=now,
        )

    # 2. Override script (higher precedence — runs after df).
    if config.disk_usage_script:
        entries = run_script(config.disk_usage_script)
        for entry in entries:
            db.upsert_disk_usage_from_script(
                location=entry['location'],
                space_used_bytes=entry['space_used_bytes'],
                quota_bytes=entry['quota_bytes'],
                object_count=entry['object_count'],
                fetched_at=now,
            )
