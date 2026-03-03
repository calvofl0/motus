"""
Database models for job tracking
Uses SQLite for simple persistence
"""
import json
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional
from contextlib import contextmanager


class Database:
    """Simple SQLite database for job tracking"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Jobs table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id INTEGER UNIQUE NOT NULL,
                    operation TEXT NOT NULL,
                    src_path TEXT NOT NULL,
                    dst_path TEXT NOT NULL,
                    src_config TEXT,
                    dst_config TEXT,
                    status TEXT DEFAULT 'running',
                    progress INTEGER DEFAULT 0,
                    error_text TEXT,
                    log_text TEXT,
                    resumed_by_job_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    finished_at TIMESTAMP
                )
            ''')

            # Index on job_id for fast lookups
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_job_id ON jobs(job_id)
            ''')

            # Index on status for filtering
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)
            ''')

            # Add download-specific columns (migration for existing databases)
            try:
                cursor.execute('ALTER TABLE jobs ADD COLUMN download_token TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute('ALTER TABLE jobs ADD COLUMN zip_path TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists

            try:
                cursor.execute('ALTER TABLE jobs ADD COLUMN zip_filename TEXT')
            except sqlite3.OperationalError:
                pass  # Column already exists

            # Disk usage cache table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS disk_usage (
                    location           TEXT PRIMARY KEY,
                    space_used_bytes   INTEGER,
                    quota_bytes        INTEGER,
                    object_count       INTEGER,
                    script_fetched_at  TEXT,
                    metric_fetched_at  TEXT,
                    is_computing       INTEGER DEFAULT 0
                )
            ''')

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection as context manager"""
        # Use timeout to handle concurrent access better
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for better concurrent access
        conn.execute('PRAGMA journal_mode=WAL')
        try:
            yield conn
        finally:
            conn.close()

    def create_job(
        self,
        job_id: int,
        operation: str,
        src_path: str,
        dst_path: str,
        src_config: Optional[Dict] = None,
        dst_config: Optional[Dict] = None,
    ) -> int:
        """Create a new job record"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO jobs (
                    job_id, operation, src_path, dst_path,
                    src_config, dst_config, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'running')
            ''', (
                job_id,
                operation,
                src_path,
                dst_path,
                json.dumps(src_config) if src_config else None,
                json.dumps(dst_config) if dst_config else None,
            ))
            conn.commit()
            return cursor.lastrowid

    def update_job(
        self,
        job_id: int,
        status: Optional[str] = None,
        progress: Optional[int] = None,
        error_text: Optional[str] = None,
        log_text: Optional[str] = None,
        download_token: Optional[str] = None,
        zip_path: Optional[str] = None,
        zip_filename: Optional[str] = None,
    ):
        """Update job status"""
        updates = []
        values = []

        if status is not None:
            updates.append('status = ?')
            values.append(status)

        if progress is not None:
            updates.append('progress = ?')
            values.append(progress)

        if error_text is not None:
            updates.append('error_text = ?')
            values.append(error_text)

        if log_text is not None:
            updates.append('log_text = ?')
            values.append(log_text)

        if download_token is not None:
            updates.append('download_token = ?')
            values.append(download_token)

        if zip_path is not None:
            updates.append('zip_path = ?')
            values.append(zip_path)

        if zip_filename is not None:
            updates.append('zip_filename = ?')
            values.append(zip_filename)

        if status in ['completed', 'failed', 'cancelled', 'interrupted', 'resumed']:
            updates.append('finished_at = ?')
            values.append(datetime.utcnow().isoformat())

        updates.append('updated_at = ?')
        values.append(datetime.utcnow().isoformat())

        values.append(job_id)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                UPDATE jobs
                SET {', '.join(updates)}
                WHERE job_id = ?
            ''', values)
            conn.commit()

    def get_job(self, job_id: int) -> Optional[Dict]:
        """Get job by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
            row = cursor.fetchone()

            if row:
                return self._row_to_dict(row)
            return None

    def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict]:
        """List jobs with optional filtering"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            if status:
                cursor.execute('''
                    SELECT * FROM jobs
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ''', (status, limit, offset))
            else:
                cursor.execute('''
                    SELECT * FROM jobs
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                ''', (limit, offset))

            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def delete_job(self, job_id: int):
        """Delete a job record"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM jobs WHERE job_id = ?', (job_id,))
            conn.commit()

    def cleanup_old_jobs(self, days: int = 7):
        """Delete jobs older than N days"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM jobs
                WHERE finished_at IS NOT NULL
                AND finished_at < datetime('now', '-' || ? || ' days')
            ''', (days,))
            conn.commit()
            return cursor.rowcount

    def get_max_job_id(self) -> int:
        """Get the maximum job_id in the database"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MAX(job_id) FROM jobs')
            result = cursor.fetchone()
            return result[0] if result[0] is not None else 0

    def mark_running_as_interrupted(self) -> int:
        """Mark all running jobs as interrupted (for startup cleanup)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs
                SET status = 'interrupted',
                    finished_at = ?,
                    updated_at = ?
                WHERE status = 'running'
            ''', (datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
            conn.commit()
            return cursor.rowcount

    def mark_job_as_resumed(self, old_job_id: int, new_job_id: int):
        """Mark a job as resumed and link to the new job"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs
                SET status = 'resumed',
                    resumed_by_job_id = ?,
                    finished_at = ?,
                    updated_at = ?
                WHERE job_id = ?
            ''', (new_job_id, datetime.utcnow().isoformat(), datetime.utcnow().isoformat(), old_job_id))
            conn.commit()

    def list_aborted_jobs(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """List failed and interrupted jobs (excluding already resumed)"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM jobs
                WHERE status IN ('failed', 'interrupted')
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def list_interrupted_resumable_jobs(self, limit: int = 100, offset: int = 0) -> List[Dict]:
        """List interrupted jobs that haven't been resumed yet"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM jobs
                WHERE status = 'interrupted' AND resumed_by_job_id IS NULL
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            rows = cursor.fetchall()
            return [self._row_to_dict(row) for row in rows]

    def delete_stopped_jobs(self) -> tuple[int, List[int]]:
        """Delete all non-running jobs and return count + list of deleted job IDs.
        Used by Expert Mode to clear all stopped jobs (completed, failed, interrupted)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # First get the job IDs we're about to delete
            cursor.execute('''
                SELECT job_id FROM jobs
                WHERE status != 'running'
            ''')
            deleted_job_ids = [row[0] for row in cursor.fetchall()]

            # Now delete them
            cursor.execute('''
                DELETE FROM jobs
                WHERE status != 'running'
            ''')
            conn.commit()
            return cursor.rowcount, deleted_job_ids

    def delete_completed_jobs(self) -> tuple[int, List[int]]:
        """Delete all completed jobs and return count + list of deleted job IDs.
        Only deletes completed jobs (not failed/interrupted).
        Used by Completed Jobs Modal and auto_cleanup_db."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # First get the job IDs we're about to delete
            cursor.execute('''
                SELECT job_id FROM jobs
                WHERE status = 'completed'
            ''')
            deleted_job_ids = [row[0] for row in cursor.fetchall()]

            # Now delete them
            cursor.execute('''
                DELETE FROM jobs
                WHERE status = 'completed'
            ''')
            conn.commit()
            return cursor.rowcount, deleted_job_ids

    def delete_jobs_before(self, cutoff_time) -> tuple[int, List[int]]:
        """
        Delete completed jobs finished before the cutoff time.
        Only deletes completed jobs (not failed/interrupted).

        Args:
            cutoff_time: datetime object (timezone-aware or naive)

        Returns:
            Tuple of (count, list of deleted job IDs)
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Convert cutoff time to ISO format string for SQLite comparison
            cutoff_str = cutoff_time.isoformat()

            # First get the job IDs we're about to delete
            cursor.execute('''
                SELECT job_id FROM jobs
                WHERE status = 'completed'
                AND finished_at IS NOT NULL
                AND finished_at < ?
            ''', (cutoff_str,))
            deleted_job_ids = [row[0] for row in cursor.fetchall()]

            # Now delete them
            cursor.execute('''
                DELETE FROM jobs
                WHERE status = 'completed'
                AND finished_at IS NOT NULL
                AND finished_at < ?
            ''', (cutoff_str,))
            conn.commit()
            return cursor.rowcount, deleted_job_ids

    def delete_all_jobs(self) -> tuple[int, List[int]]:
        """Delete all jobs and return count + list of deleted job IDs"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # First get the job IDs we're about to delete
            cursor.execute('SELECT job_id FROM jobs')
            deleted_job_ids = [row[0] for row in cursor.fetchall()]

            # Now delete them all
            cursor.execute('DELETE FROM jobs')
            conn.commit()
            return cursor.rowcount, deleted_job_ids

    # ── Disk usage cache ──────────────────────────────────────────────────────

    def upsert_disk_usage_from_df(
        self,
        location: str,
        space_used_bytes: Optional[int],
        quota_bytes: Optional[int],
        object_count: Optional[int],
        fetched_at: str,
    ):
        """Full overwrite of metric fields (df source); preserves script_fetched_at."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO disk_usage
                    (location, space_used_bytes, quota_bytes, object_count,
                     metric_fetched_at, is_computing)
                VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(location) DO UPDATE SET
                    space_used_bytes  = excluded.space_used_bytes,
                    quota_bytes       = excluded.quota_bytes,
                    object_count      = excluded.object_count,
                    metric_fetched_at = excluded.metric_fetched_at
            ''', (location, space_used_bytes, quota_bytes, object_count, fetched_at))
            conn.commit()

    def upsert_disk_usage_from_script(
        self,
        location: str,
        space_used_bytes: Optional[int],
        quota_bytes: Optional[int],
        object_count: Optional[int],
        fetched_at: str,
    ):
        """Full overwrite of all value fields (script source); preserves metric_fetched_at."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO disk_usage
                    (location, space_used_bytes, quota_bytes, object_count,
                     script_fetched_at, is_computing)
                VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(location) DO UPDATE SET
                    space_used_bytes = excluded.space_used_bytes,
                    quota_bytes      = excluded.quota_bytes,
                    object_count     = excluded.object_count,
                    script_fetched_at = excluded.script_fetched_at
            ''', (location, space_used_bytes, quota_bytes, object_count, fetched_at))
            conn.commit()

    def upsert_disk_usage_from_rclone(
        self,
        location: str,
        space_used_bytes: Optional[int],
        quota_bytes: Optional[int],
        object_count: Optional[int],
        fetched_at: str,
    ):
        """Fill in only NULL fields (rclone about/size source); never overwrites existing values."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO disk_usage
                    (location, space_used_bytes, quota_bytes, object_count,
                     metric_fetched_at, is_computing)
                VALUES (?, ?, ?, ?, ?, 0)
                ON CONFLICT(location) DO UPDATE SET
                    space_used_bytes  = COALESCE(disk_usage.space_used_bytes,  excluded.space_used_bytes),
                    quota_bytes       = COALESCE(disk_usage.quota_bytes,       excluded.quota_bytes),
                    object_count      = COALESCE(disk_usage.object_count,      excluded.object_count),
                    metric_fetched_at = excluded.metric_fetched_at
            ''', (location, space_used_bytes, quota_bytes, object_count, fetched_at))
            conn.commit()

    def get_disk_usage(self, location: str) -> Optional[Dict]:
        """Return the row for an exact location key, or None."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                'SELECT * FROM disk_usage WHERE location = ?', (location,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def list_disk_usage(self) -> List[Dict]:
        """Return all disk_usage rows (used for prefix-matching lookups)."""
        with self._get_connection() as conn:
            cursor = conn.execute('SELECT * FROM disk_usage')
            return [dict(r) for r in cursor.fetchall()]

    def set_computing(self, location: str, is_computing: bool):
        """Create or update the is_computing flag for a location."""
        with self._get_connection() as conn:
            conn.execute('''
                INSERT INTO disk_usage (location, is_computing)
                VALUES (?, ?)
                ON CONFLICT(location) DO UPDATE SET is_computing = excluded.is_computing
            ''', (location, 1 if is_computing else 0))
            conn.commit()

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert sqlite Row to dict"""
        d = dict(row)
        # Parse JSON fields
        if d.get('src_config'):
            d['src_config'] = json.loads(d['src_config'])
        if d.get('dst_config'):
            d['dst_config'] = json.loads(d['dst_config'])
        return d
