"""
Disk-usage API endpoints.

GET  /api/disk-usage           – fetch cached usage for the current pane location
POST /api/disk-usage/refresh   – (re-)populate cache; triggers background rclone fetch if needed
POST /api/disk-usage/cancel    – abort an in-flight rclone about/size fetch
"""

import logging
from datetime import datetime, timezone
from flask import Blueprint, jsonify, request, current_app

from ..disk_usage import (
    resolve_canonical,
    s3_bucket_root,
    find_best_match,
    fetch_all_local_stats,
    run_script,
    start_background_fetch,
    cancel_fetch,
)

logger = logging.getLogger(__name__)

disk_usage_bp = Blueprint('disk_usage', __name__)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_context():
    """Return frequently-used objects from the app context."""
    return (
        current_app.rclone,
        current_app.db,
        current_app.motus_config,
    )


def _oldest_fetched_at(row: dict) -> str | None:
    """
    Return the minimum (oldest) of script_fetched_at and metric_fetched_at,
    or None if neither is set.
    """
    candidates = [
        row.get('script_fetched_at'),
        row.get('metric_fetched_at'),
    ]
    valid = [c for c in candidates if c]
    return min(valid) if valid else None


def _row_to_response(row: dict | None, at_s3_root: bool = False) -> dict:
    if at_s3_root:
        return {'at_s3_root': True}

    if row is None:
        return {
            'at_s3_root': False,
            'space_used_bytes': None,
            'quota_bytes': None,
            'object_count': None,
            'fetched_at': None,
            'is_computing': False,
        }

    return {
        'at_s3_root': False,
        'space_used_bytes': row.get('space_used_bytes'),
        'quota_bytes': row.get('quota_bytes'),
        'object_count': row.get('object_count'),
        'fetched_at': _oldest_fetched_at(row),
        'is_computing': bool(row.get('is_computing')),
    }


def _maybe_start_rclone(canonical_key, storage_type, remote, path, rclone, config, db):
    """
    If there is any missing field for a non-local location, start a background
    rclone about + rclone size fetch (unless one is already running).
    """
    if storage_type not in ('s3', 'other'):
        return

    rows = db.list_disk_usage()
    best = find_best_match(canonical_key, rows)
    needs_fetch = (
        best is None
        or best.get('space_used_bytes') is None
        or (storage_type == 's3' and best.get('object_count') is None)
    )
    if not needs_fetch:
        return

    # Determine the rclone target (bucket root for S3, path for other).
    try:
        resolved_remote, resolved_path = rclone.rclone_config.resolve_alias_chain(remote, path)
    except Exception:
        resolved_remote, resolved_path = remote, path

    if storage_type == 's3':
        _, bucket, bucket_key = s3_bucket_root(remote, path, rclone.rclone_config)
        if not bucket:
            return
        rclone_target = f'{resolved_remote}:{bucket}'
        fetch_key = bucket_key or canonical_key
    else:
        rclone_target = f'{resolved_remote}:{resolved_path.lstrip("/")}'
        fetch_key = canonical_key

    start_background_fetch(
        canonical_key=fetch_key,
        resolved_remote=resolved_remote,
        rclone_target=rclone_target,
        rclone_path=rclone.rclone_path,
        config_file=rclone.rclone_config.config_file,
        db=db,
    )


# ── GET /api/disk-usage ───────────────────────────────────────────────────────

@disk_usage_bp.route('/api/disk-usage', methods=['GET'])
def get_disk_usage():
    """
    Query params:
        remote  – selected remote name (may be an alias)
        path    – current path within the remote
    """
    remote = request.args.get('remote', '')
    path   = request.args.get('path', '/')
    rclone, db, _config = _get_context()

    canonical_key, storage_type = resolve_canonical(remote, path, rclone.rclone_config)

    if storage_type == 's3_at_root':
        return jsonify(_row_to_response(None, at_s3_root=True))

    rows = db.list_disk_usage()
    best = find_best_match(canonical_key, rows)
    return jsonify(_row_to_response(best))


# ── POST /api/disk-usage/refresh ─────────────────────────────────────────────

@disk_usage_bp.route('/api/disk-usage/refresh', methods=['POST'])
def refresh_disk_usage():
    """
    Body (JSON):
        remote  – selected remote name
        path    – current path
    """
    data   = request.get_json(force=True) or {}
    remote = data.get('remote', '')
    path   = data.get('path', '/')
    rclone, db, config = _get_context()

    canonical_key, storage_type = resolve_canonical(remote, path, rclone.rclone_config)

    if storage_type == 's3_at_root':
        return jsonify({'error': 'Cannot refresh at S3 root level'}), 400

    now = _utcnow()

    # 1. Always refresh all local mount points via df (fast).
    local_stats = fetch_all_local_stats()
    for mount, stats in local_stats.items():
        db.upsert_disk_usage_from_df(
            location=mount,
            space_used_bytes=stats.get('space_used_bytes'),
            quota_bytes=stats.get('quota_bytes'),
            object_count=stats.get('object_count'),
            fetched_at=now,
        )

    # 2. Run override script (higher precedence — overwrites df data).
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

    # 3. For non-local locations: start background rclone fetch if needed.
    _maybe_start_rclone(canonical_key, storage_type, remote, path, rclone, config, db)

    # Return the current (possibly stale) cached value immediately.
    rows = db.list_disk_usage()
    best = find_best_match(canonical_key, rows)
    return jsonify(_row_to_response(best))


# ── POST /api/disk-usage/cancel ──────────────────────────────────────────────

@disk_usage_bp.route('/api/disk-usage/cancel', methods=['POST'])
def cancel_disk_usage():
    """
    Body (JSON):
        remote  – selected remote name
        path    – current path
    """
    data   = request.get_json(force=True) or {}
    remote = data.get('remote', '')
    path   = data.get('path', '/')
    rclone, db, _config = _get_context()

    canonical_key, storage_type = resolve_canonical(remote, path, rclone.rclone_config)

    if canonical_key:
        cancel_fetch(canonical_key)
        db.set_computing(canonical_key, False)

    # For S3, also cancel at the bucket-root canonical key.
    if storage_type == 's3':
        _, _bucket, bucket_key = s3_bucket_root(remote, path, rclone.rclone_config)
        if bucket_key and bucket_key != canonical_key:
            cancel_fetch(bucket_key)
            db.set_computing(bucket_key, False)

    return jsonify({'ok': True})
