"""
Job queue for managing rclone copy/move operations
Adapted from Motuz (MIT License) - FredHutch/motuz
"""
import functools
import json
import logging
import os
import re
import subprocess
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
        all_jobs = list(self._processes.keys())
        for job_id in all_jobs:
            is_fin = self.is_finished(job_id)
            if not is_fin:
                running.append(job_id)
        logging.debug(f"get_running_jobs: all_jobs={all_jobs}, running={running}")
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
        """Execute rclone command and track progress (Motuz-style synchronous reading)"""
        stop_event = self._stop_events[job_id]

        # Merge environment variables
        full_env = os.environ.copy()
        full_env.update(env)

        # Start process (matches original Motuz implementation)
        try:
            process = subprocess.Popen(
                command,
                env=full_env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self._processes[job_id] = process
            logging.info(f"Job {job_id}: Started process PID {process.pid}")
        except Exception as e:
            logging.error(f"Failed to start job {job_id}: {e}")
            self._job_error_text[job_id] = str(e)
            self._job_exitstatus[job_id] = -1
            stop_event.set()
            return

        # Motuz uses specific ANSI reset sequences
        reset_sequence1 = '\x1b[2K\x1b[0'  # Clear line + reset
        reset_sequence2 = '\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[A\x1b[2K\x1b[0'  # Multiple line clears

        # Main loop: read stdout synchronously (like Motuz)
        while not stop_event.is_set():
            line = process.stdout.readline().decode('utf-8')

            # Empty line check - see if process finished
            if len(line) == 0:
                if process.poll() is not None:
                    stop_event.set()
                else:
                    time.sleep(0.5)
                continue

            line = line.strip()

            # Strip ANSI sequences (Motuz approach)
            q1 = line.find(reset_sequence1)
            if q1 != -1:
                line = line[q1 + len(reset_sequence1):]

            q2 = line.find(reset_sequence2)
            if q2 != -1:
                line = line[q2 + len(reset_sequence1):]

            line = line.replace(reset_sequence1, '')
            line = line.replace(reset_sequence2, '')

            # Log raw line for debugging
            if job_id <= 150:
                logging.debug(f"Job {job_id}: Raw line: {repr(line[:100])}")

            # Check for errors
            error_match = re.search(r'(ERROR.*)', line)
            if error_match:
                error = error_match.group(0)
                logging.error(f"Job {job_id}: {error}")
                self._job_error_text[job_id] += error + '\n'
                self._job_error_text[job_id] = self._job_error_text[job_id][-10000:]
                continue

            # Parse status line key-value pairs
            status_match = re.search(r'([A-Za-z ]+):\s*(.*)', line)
            if status_match is None:
                logging.info(f"Job {job_id}: No match in {repr(line[:100])}")
                time.sleep(0.5)
                continue

            key, value = status_match.groups()
            self._job_status[job_id][key] = value
            self._process_status(job_id)

        # Job finished - set to 100%
        self._job_percent[job_id] = 100
        self._process_status(job_id)

        # Get exit status
        exitstatus = process.poll()
        self._job_exitstatus[job_id] = exitstatus

        # Read any remaining stderr output (like Motuz does)
        for _ in range(100000):
            line = process.stderr.readline().decode('utf-8')
            if len(line) == 0:
                break
            line = line.strip()
            self._job_error_text[job_id] += line + '\n'
            # Restrict size to 10000 characters
            self._job_error_text[job_id] = self._job_error_text[job_id][-10000:]

        logging.info(f"Job {job_id}: Copy process exited with exit status {exitstatus}")
        stop_event.set()

    def _process_status(self, job_id):
        """Process status dict into formatted text and percentage (Motuz-style)"""
        status = self._job_status[job_id]

        # Expected headers from rclone --progress (matching Motuz)
        headers = [
            'GTransferred',
            'Errors',
            'Checks',
            'Transferred0',
            'Transferred',
            'Elapsed time',
            'Transferring',
        ]

        # Handle outliers - Motuz splits combined "Transferring" + "Transferred" lines
        outliers = []
        for key in status.keys():
            if key not in headers:
                outliers.append(key)

        if len(outliers) == 1:
            value = status[outliers[0]]
            if job_id <= 150:
                logging.debug(f"Job {job_id}: Outlier detected: key={repr(outliers[0])}, value={repr(value)}")
            try:
                pos = value.index("Transferred:")
                transferring, transferred = value[:pos], value[pos:]
                transferring = transferring.replace("Transferring:", "").strip()
                transferred = transferred.replace("Transferred:", "").strip()
                status['Transferred0'] = transferred
                status['Transferring'] = transferring
                if job_id <= 150:
                    logging.debug(f"Job {job_id}: After split: Transferred0={repr(transferred)}, Transferring={repr(transferring)}")
                del status[outliers[0]]
            except ValueError:
                if job_id <= 150:
                    logging.debug(f"Job {job_id}: No 'Transferred:' found in outlier value")

        # Clean up Transferred0 if it exists
        if 'Transferred0' in status:
            status['Transferred0'] = status['Transferred0'].replace("Transferred:", "").strip()

        # Remove Transferring if job is complete
        if status.get('Transferred') == "1 / 1, 100%":
            status.pop('Transferring', None)

        # Format status text
        text_lines = []
        for header in headers:
            if header in status:
                display_header = " Transferred" if header == "Transferred0" else header
                text_lines.append(f"{display_header:>15}: {status[header]}")

        self._job_text[job_id] = '\n'.join(text_lines)

        # Extract percentage (Motuz-style: check GTransferred then Transferred0)
        old_progress = self._job_percent.get(job_id, 0)
        new_progress = None

        # Check GTransferred first
        if 'GTransferred' in status:
            match = re.search(r'(\d+)%', status['GTransferred'])
            if match:
                new_progress = int(match.group(1))
                if job_id <= 150:
                    logging.debug(f"Job {job_id}: Extracted {new_progress}% from GTransferred: {repr(status['GTransferred'])}")

        # Fall back to Transferred0 (byte-based transfer info)
        if new_progress is None and 'Transferred0' in status:
            match = re.search(r'(\d+)%', status['Transferred0'])
            if match:
                new_progress = int(match.group(1))
                if job_id <= 150:
                    logging.debug(f"Job {job_id}: Extracted {new_progress}% from Transferred0: {repr(status['Transferred0'])}")

        # Fall back to Transferred (file count - less accurate)
        if new_progress is None and 'Transferred' in status:
            match = re.search(r'(\d+)%', status['Transferred'])
            if match:
                new_progress = int(match.group(1))
                if job_id <= 150:
                    logging.debug(f"Job {job_id}: Extracted {new_progress}% from Transferred: {repr(status['Transferred'])}")

        # Update progress (never go backwards)
        if new_progress is not None and new_progress >= old_progress:
            self._job_percent[job_id] = new_progress
            if new_progress != old_progress:
                logging.info(f"Job {job_id}: Progress updated: {old_progress}% → {new_progress}%")
        elif new_progress is not None and new_progress < old_progress:
            logging.warning(f"Job {job_id}: Ignoring backwards progress: {old_progress}% ← {new_progress}% (keeping {old_progress}%)")
