"""
Job queue for managing rclone copy/move operations
Adapted from Motuz (MIT License) - FredHutch/motuz
"""
import functools
import json
import logging
import os
import re
import select
import subprocess
import sys
import threading
import time
from collections import defaultdict

from .exceptions import RcloneException


class JobQueue:
    """Manages background rclone jobs with progress tracking"""

    def __init__(self):
        self._job_status = defaultdict(functools.partial(defaultdict, str))
        self._job_text = defaultdict(str)
        self._job_error_text = defaultdict(str)
        self._job_percent = defaultdict(int)
        self._job_exitstatus = {}
        self._stop_events = {}  # job_id -> threading.Event
        self._processes = {}  # job_id -> subprocess.Popen

    def push(self, command, env, job_id):
        """Start a new job in background"""
        if job_id in self._job_status:
            raise KeyError(f"Job with ID {job_id} already exists")

        self._stop_events[job_id] = threading.Event()

        # Start job in background thread
        thread = threading.Thread(
            target=self._execute_job,
            args=(command, env, job_id),
            daemon=True
        )
        thread.start()

        return job_id

    def get_text(self, job_id):
        """Get formatted status text for a job"""
        return self._job_text.get(job_id, '')

    def get_error_text(self, job_id):
        """Get error text for a job"""
        return self._job_error_text.get(job_id, '')

    def get_percent(self, job_id):
        """Get completion percentage (0-100)"""
        return self._job_percent.get(job_id, 0)

    def stop(self, job_id):
        """Stop a running job"""
        if job_id in self._stop_events:
            self._stop_events[job_id].set()
            # Also terminate the process
            if job_id in self._processes:
                try:
                    self._processes[job_id].terminate()
                except:
                    pass

    def is_finished(self, job_id):
        """Check if job has finished"""
        if job_id not in self._stop_events:
            return False
        return self._stop_events[job_id].is_set()

    def get_exitstatus(self, job_id):
        """Get exit status of job (-1 if not finished)"""
        return self._job_exitstatus.get(job_id, -1)

    def delete(self, job_id):
        """Delete a job's data"""
        self._job_status.pop(job_id, None)
        self._job_text.pop(job_id, None)
        self._job_error_text.pop(job_id, None)
        self._job_percent.pop(job_id, None)
        self._job_exitstatus.pop(job_id, None)
        self._stop_events.pop(job_id, None)
        self._processes.pop(job_id, None)

    def get_running_jobs(self):
        """Get list of running job IDs"""
        running = []
        for job_id in list(self._processes.keys()):
            if not self.is_finished(job_id):
                running.append(job_id)
        return running

    def shutdown_all(self):
        """Stop all running jobs (for graceful shutdown)"""
        running = self.get_running_jobs()
        logging.info(f"Stopping {len(running)} running jobs...")
        for job_id in running:
            try:
                self.stop(job_id)
            except Exception as e:
                logging.error(f"Error stopping job {job_id}: {e}")
        return len(running)

    def _execute_job(self, command, env, job_id):
        """Execute rclone command and track progress"""
        stop_event = self._stop_events[job_id]

        # Merge environment variables
        full_env = os.environ.copy()
        full_env.update(env)

        # Start process
        try:
            process = subprocess.Popen(
                command,
                env=full_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._processes[job_id] = process
        except Exception as e:
            logging.error(f"Failed to start job {job_id}: {e}")
            self._job_error_text[job_id] = str(e)
            self._job_exitstatus[job_id] = -1
            stop_event.set()
            return

        # ANSI reset sequences from rclone output
        reset_sequence1 = '\x1b[2K\x1b[0'
        reset_sequence2 = '\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[0'

        # Use select for non-blocking stdout reading with periodic process checks
        # This prevents hanging when process completes quickly with no output
        stdout_fd = process.stdout.fileno()

        # Read output line by line
        while not stop_event.is_set():
            # Check if process has finished before trying to read
            # This catches fast operations that complete with minimal output
            poll_result = process.poll()
            if poll_result is not None:
                # Process finished - break out immediately
                logging.debug(f"Job {job_id}: Process exited with code {poll_result}")
                break

            # Use select with timeout to avoid blocking indefinitely on readline
            # select() only works on Unix file descriptors
            if hasattr(select, 'select'):
                # Unix/Linux: use select with 0.5s timeout
                try:
                    readable, _, _ = select.select([stdout_fd], [], [], 0.5)
                    if not readable:
                        # No data available - loop back to check process status
                        continue
                except (ValueError, OSError):
                    # File descriptor closed or invalid - process likely finished
                    break
            else:
                # Windows: fallback to polling with small sleep
                time.sleep(0.1)

            # Data is available (or we're on Windows), try to read a line
            line = process.stdout.readline().decode('utf-8', errors='ignore')

            if len(line) == 0:
                # Empty line might mean EOF - check if process finished
                if process.poll() is not None:
                    break
                continue

            line = line.strip()

            # Remove ANSI escape sequences
            if reset_sequence1 in line:
                line = line[line.find(reset_sequence1) + len(reset_sequence1):]
            if reset_sequence2 in line:
                line = line[line.find(reset_sequence2) + len(reset_sequence2):]
            line = line.replace(reset_sequence1, '').replace(reset_sequence2, '')

            # Check for errors
            error_match = re.search(r'(ERROR.*)', line)
            if error_match:
                error = error_match.group(1)
                logging.error(f"Job {job_id}: {error}")
                self._job_error_text[job_id] += error + '\n'
                # Limit error text size
                self._job_error_text[job_id] = self._job_error_text[job_id][-10000:]
                continue

            # Parse status line
            status_match = re.search(r'([A-Za-z ]+):\s*(.*)', line)
            if status_match:
                key, value = status_match.groups()
                self._job_status[job_id][key] = value
                self._process_status(job_id)

        # Job finished
        self._job_percent[job_id] = 100
        self._process_status(job_id)

        # Get exit status
        exitstatus = process.poll()
        if exitstatus is None:
            process.wait(timeout=5)
            exitstatus = process.poll()

        self._job_exitstatus[job_id] = exitstatus if exitstatus is not None else -1

        # Read any remaining stderr
        try:
            stderr = process.stderr.read().decode('utf-8', errors='ignore')
            if stderr:
                self._job_error_text[job_id] += stderr
                self._job_error_text[job_id] = self._job_error_text[job_id][-10000:]
        except:
            pass

        logging.info(f"Job {job_id} finished with exit status {exitstatus}")
        stop_event.set()

    def _process_status(self, job_id):
        """Process status dict into formatted text and percentage"""
        status = self._job_status[job_id]

        # Expected headers from rclone --progress
        headers = [
            'Transferred',
            'Errors',
            'Checks',
            'Transferred',
            'Elapsed time',
            'Transferring',
        ]

        # Format status text
        text_lines = []
        for key, value in status.items():
            text_lines.append(f"{key:>15}: {value}")

        self._job_text[job_id] = '\n'.join(text_lines)

        # Extract percentage
        for key, value in status.items():
            percent_match = re.search(r'(\d+)%', value)
            if percent_match:
                try:
                    self._job_percent[job_id] = int(percent_match.group(1))
                    break
                except:
                    pass
