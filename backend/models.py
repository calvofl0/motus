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

            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection as context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
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

        if status in ['completed', 'failed', 'cancelled', 'interrupted', 'resumed']:
            updates.append('finished_at = ?')
            values.append(datetime.now().isoformat())

        updates.append('updated_at = ?')
        values.append(datetime.now().isoformat())

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
            ''', (datetime.now().isoformat(), datetime.now().isoformat()))
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
            ''', (new_job_id, datetime.now().isoformat(), datetime.now().isoformat(), old_job_id))
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

    def delete_stopped_jobs(self) -> int:
        """Delete all non-running jobs"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                DELETE FROM jobs
                WHERE status != 'running'
            ''')
            conn.commit()
            return cursor.rowcount

    def _row_to_dict(self, row: sqlite3.Row) -> Dict:
        """Convert sqlite Row to dict"""
        d = dict(row)
        # Parse JSON fields
        if d.get('src_config'):
            d['src_config'] = json.loads(d['src_config'])
        if d.get('dst_config'):
            d['dst_config'] = json.loads(d['dst_config'])
        return d
