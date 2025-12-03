"""
Rclone wrapper for single-user file operations
Adapted from Motuz (MIT License) - FredHutch/motuz
Simplified for single-user, no authentication needed
"""
import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional

from .exceptions import RcloneException, RcloneNotFoundError
from .job_queue import JobQueue
from .rclone_config import RcloneConfig

# Cross-platform null device
DEVNULL = 'NUL' if sys.platform == 'win32' else '/dev/null'


def safe_remove(path):
    """
    Safely remove a file or directory

    Handles both files and directories (recursively)
    """
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


class RcloneWrapper:
    """
    Wrapper around rclone command-line tool for file operations.
    Supports local filesystem and cloud backends (S3, SFTP, etc.)
    """

    def __init__(self, rclone_path: str = None, rclone_config_file: str = None, logs_dir: str = None,
                 readonly_config_file: str = None, cache_dir: str = None):
        """
        Initialize rclone wrapper

        Args:
            rclone_path: Path to rclone executable (default: searches PATH)
            rclone_config_file: Path to rclone config file (default: rclone default)
            logs_dir: Directory to store job log files (default: None, logging disabled)
            readonly_config_file: Path to readonly remotes config file (from --add-remotes)
            cache_dir: Cache directory for merged config file
        """
        self.rclone_path = rclone_path or self._find_rclone()
        self.rclone_config_file = rclone_config_file
        self.logs_dir = logs_dir
        self.readonly_config_file = readonly_config_file
        self.cache_dir = cache_dir
        self._job_queue = JobQueue()
        self._next_job_id = 1
        self._job_id_lock = __import__('threading').Lock()  # Thread-safe job ID generation
        self._job_log_files = {}  # Track log file paths for each job

        # Create logs directory if specified
        if self.logs_dir:
            os.makedirs(self.logs_dir, exist_ok=True)
            logging.info(f"Job logs will be stored in: {self.logs_dir}")

        # Verify rclone is installed
        self._verify_rclone()

        # Discover rclone config file path if not provided
        if not self.rclone_config_file:
            self.rclone_config_file = self._get_rclone_config_path()

        logging.info(f"Using rclone config: {self.rclone_config_file}")

        # Initialize RcloneConfig with two-tier support
        self.rclone_config = RcloneConfig(
            self.rclone_config_file,
            readonly_config_file=self.readonly_config_file,
            cache_dir=self.cache_dir
        )

    def initialize_job_counter(self, db):
        """
        Initialize job ID counter from database to avoid UNIQUE constraint errors

        Args:
            db: Database instance to query for max job_id
        """
        with self._job_id_lock:
            max_job_id = db.get_max_job_id()
            self._next_job_id = max_job_id + 1
            logging.info(f"Initialized job counter to {self._next_job_id} (max existing job_id: {max_job_id})")

    def _find_rclone(self) -> str:
        """Find rclone executable in PATH"""
        rclone = shutil.which('rclone')
        if not rclone:
            raise RcloneNotFoundError(
                "rclone not found in PATH. Please install rclone: "
                "https://rclone.org/downloads/"
            )
        return rclone

    def _verify_rclone(self):
        """Verify rclone is installed and working"""
        try:
            result = subprocess.run(
                [self.rclone_path, 'version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode != 0:
                raise RcloneNotFoundError(
                    f"rclone at {self.rclone_path} is not working properly"
                )
            logging.info(f"rclone found: {result.stdout.splitlines()[0]}")
        except FileNotFoundError:
            raise RcloneNotFoundError(
                f"rclone not found at {self.rclone_path}. "
                "Install from https://rclone.org/downloads/"
            )
        except subprocess.TimeoutExpired:
            raise RcloneNotFoundError("rclone version check timed out")

    def _get_rclone_config_path(self) -> str:
        """Get the rclone config file path using rclone itself"""
        try:
            result = subprocess.run(
                [self.rclone_path, 'config', 'file'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                # Output format: "Configuration file is stored at:\n/path/to/rclone.conf"
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    return lines[1].strip()
                elif len(lines) == 1:
                    return lines[0].strip()

            # Fallback to default location
            return os.path.expanduser('~/.config/rclone/rclone.conf')
        except Exception as e:
            logging.warning(f"Failed to get rclone config path: {e}, using default")
            return os.path.expanduser('~/.config/rclone/rclone.conf')

    def list_remotes(self) -> List[str]:
        """
        List configured rclone remotes

        Returns:
            List of remote names (e.g., ['myS3', 'mySFTP', ...])
        """
        try:
            command = [self.rclone_path, 'listremotes']

            # Use custom config file if specified (use merged config from RcloneConfig)
            if self.rclone_config.config_file:
                command.extend(['--config', self.rclone_config.config_file])

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                raise RcloneException(f"Failed to list remotes: {result.stderr}")

            # Parse output - each line is a remote name ending with ':'
            remotes = []
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if line and line.endswith(':'):
                    remotes.append(line[:-1])  # Remove trailing ':'

            return remotes

        except subprocess.TimeoutExpired:
            raise RcloneException("List remotes command timed out")
        except Exception as e:
            raise RcloneException(f"Failed to list remotes: {e}")

    def resolve_to_local_path(self, path: str) -> Optional[str]:
        """
        Resolve a path through alias chains and return local filesystem path if applicable

        This handles both:
        - Type 'alias' remotes that point to local paths
        - Type 'local' remotes (rclone local filesystem remotes)

        Follows alias chains: if you have alias1 -> alias2 -> alias3 -> /local/path,
        it will follow the chain and return the final local path.

        Args:
            path: Path to resolve (e.g., "myalias:/folder/file.txt" or "localremote:/path")

        Returns:
            Local filesystem path if the resolved remote is local, None otherwise

        Example:
            # If MyAlias (type=alias) -> AnotherAlias:/folder1 and AnotherAlias -> /mnt/data
            resolve_to_local_path("MyAlias:/folder2/file.txt")
            # Returns: "/mnt/data/folder1/folder2/file.txt"

            # If localtest (type=local) has root=/home/user
            resolve_to_local_path("localtest:/documents/file.txt")
            # Returns: "/home/user/documents/file.txt"
        """
        # Check if it's a Windows path (C:, D:, etc.)
        if len(path) > 1 and path[1] == ':' and path[0].isalpha():
            return path  # Windows absolute path

        # If no colon, it's already a local path
        if ':' not in path:
            return path

        # Parse the path to extract remote and path components
        remote_name, remote_path = path.split(':', 1)

        try:
            # Reload config to get latest remotes
            self.rclone_config.reload()

            # Resolve alias chain (follows type=alias remotes)
            resolved_remote, resolved_path = self.rclone_config.resolve_alias_chain(remote_name, remote_path)

            # Check if the resolved remote is actually a configured remote or local path
            # If it's a configured remote name, it's still remote
            # If it's a local path, it won't be in the list of configured remotes
            configured_remotes = self.rclone_config.list_remotes()

            if resolved_remote in configured_remotes:
                # It's a configured remote - check if it's type 'local'
                remote_config = self.rclone_config.get_remote(resolved_remote)

                if remote_config and remote_config.get('type') == 'local':
                    # It's a local filesystem remote!
                    # Get the root path from the remote config (defaults to / if not specified)
                    root_path = remote_config.get('root', '/')

                    # Construct full local path
                    if resolved_path:
                        # Combine root path with resolved path
                        if root_path.endswith('/'):
                            full_path = f"{root_path.rstrip('/')}{resolved_path}"
                        else:
                            full_path = f"{root_path}{resolved_path}"
                        return full_path
                    else:
                        return root_path
                else:
                    # It's a different type of configured remote (s3, onedrive, etc.)
                    return None

            # Not a configured remote - must be a local path string
            # Construct the full local path
            if resolved_path:
                return f"{resolved_remote}{resolved_path}"
            else:
                return resolved_remote

        except (ValueError, Exception) as e:
            # If resolution fails, treat as remote
            logging.debug(f"Failed to resolve alias chain for {path}: {e}")
            return None

    def _parse_path(self, path: str) -> tuple[Optional[str], str]:
        """
        Parse a path to detect remote syntax

        Args:
            path: Path string (e.g., 'myS3:/bucket/file' or '/local/path' or '~/docs')

        Returns:
            Tuple of (remote_name, path) where remote_name is None for local paths
            Examples:
                'myS3:/bucket/file' -> ('myS3', '/bucket/file')
                '/local/path' -> (None, '/local/path')
                '~/docs' -> (None, '/home/user/docs')
                'remote:path' -> ('remote', 'path')
        """
        if ':' in path:
            # Check if this looks like a remote path (remote_name:path)
            parts = path.split(':', 1)
            if len(parts) == 2:
                remote_name = parts[0]
                remote_path = parts[1]

                # Validate it's not a Windows path (C:\...) or URL (http://...)
                if remote_name and not ('\\' in remote_name or '/' in remote_name):
                    logging.debug(f"Path '{path}' parsed as remote: {remote_name}:{remote_path}")
                    return (remote_name, remote_path)

        # Local path - expand tilde for home directory
        expanded = os.path.expanduser(path)
        # Remove trailing slash (except for root '/') for consistency
        # Works on Unix, Mac, and Windows (handles both '/' and '\')
        if len(expanded) > 1:
            expanded = expanded.rstrip('/').rstrip('\\')
        return (None, expanded)

    def ls(self, path: str, remote_config: Optional[Dict] = None) -> List[Dict]:
        """
        List files and directories at path

        Args:
            path: Path to list (local, remote syntax, or with remote_config)
                  Examples: '/local/path', 'myS3:/bucket/path'
            remote_config: Optional remote configuration dict (legacy support)

        Returns:
            List of file/directory dicts with 'Name', 'Size', 'IsDir', etc.
        """
        credentials = {}
        config_arg = self.rclone_config.config_file

        # Check if path uses remote syntax (remote_name:/path)
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            # Use named remote from rclone config
            remote_path = f"{remote_name}:{clean_path}"
        elif remote_config:
            # Legacy: use provided credentials
            credentials = self._format_credentials(remote_config, 'current')
            remote_path = f"current:{path}"
            config_arg = DEVNULL  # Don't use config file with env vars
        else:
            # Local path (use expanded path with tilde resolved)
            remote_path = clean_path

        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else DEVNULL,
            'lsjson',
            '--fast-list',  # Use fast-list for better performance with cloud storage (S3, GCS, Azure, etc.)
            '--no-mimetype',  # Don't fetch MIME types - we only need Name, Size, ModTime, IsDir
            remote_path,
        ]

        self._log_command(command, credentials)

        try:
            result = self._execute(command, credentials)
            files = json.loads(result)
            return files
        except subprocess.CalledProcessError as e:
            raise RcloneException(f"Failed to list {path}: {e}")
        except json.JSONDecodeError as e:
            raise RcloneException(f"Failed to parse rclone output: {e}")

    def mkdir(self, path: str, remote_config: Optional[Dict] = None):
        """
        Create a directory

        Args:
            path: Directory path to create (local, remote syntax, or with remote_config)
                  Examples: '/local/path', 'myS3:/bucket/path'
            remote_config: Optional remote configuration dict (legacy support)
        """
        credentials = {}
        config_arg = self.rclone_config.config_file

        # Check if path uses remote syntax
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            # Use named remote from rclone config
            remote_path = f"{remote_name}:{clean_path}"
        elif remote_config:
            # Legacy: use provided credentials
            credentials = self._format_credentials(remote_config, 'current')
            remote_path = f"current:{path}"
            config_arg = '/dev/null'
        else:
            # Local path (use expanded path with tilde resolved)
            remote_path = clean_path

        # Use rclone mkdir to create directory
        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else DEVNULL,
            'mkdir',
            remote_path,
        ]

        # Add S3-specific options if needed
        if remote_config and remote_config.get('type') == 's3':
            command.extend([
                '--s3-no-check-bucket',
                '--s3-acl', 'bucket-owner-full-control',
            ])

        self._log_command(command, credentials)

        try:
            self._execute(command, credentials)
        except subprocess.CalledProcessError as e:
            raise RcloneException(f"Failed to create directory {path}: {e}")

    def copy(
        self,
        src_path: str,
        dst_path: str,
        src_config: Optional[Dict] = None,
        dst_config: Optional[Dict] = None,
        copy_links: bool = False,
    ) -> int:
        """
        Copy files/directories (async, returns job_id)

        Args:
            src_path: Source path
            dst_path: Destination path
            src_config: Optional source remote config
            dst_config: Optional destination remote config
            copy_links: Follow symlinks

        Returns:
            job_id for tracking progress
        """
        return self._transfer(
            'copy',
            src_path,
            dst_path,
            src_config,
            dst_config,
            copy_links
        )

    def move(
        self,
        src_path: str,
        dst_path: str,
        src_config: Optional[Dict] = None,
        dst_config: Optional[Dict] = None,
        copy_links: bool = False,
    ) -> int:
        """
        Move files/directories (async, returns job_id)

        Args:
            src_path: Source path
            dst_path: Destination path
            src_config: Optional source remote config
            dst_config: Optional destination remote config
            copy_links: Follow symlinks

        Returns:
            job_id for tracking progress
        """
        return self._transfer(
            'move',
            src_path,
            dst_path,
            src_config,
            dst_config,
            copy_links
        )

    def delete(self, path: str, remote_config: Optional[Dict] = None):
        """
        Delete a file or directory

        Args:
            path: Path to delete (local, remote syntax, or with remote_config)
                  Examples: '/local/path', 'myS3:/bucket/path'
            remote_config: Optional remote configuration dict (legacy support)
        """
        credentials = {}
        config_arg = self.rclone_config.config_file

        # Check if path uses remote syntax
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            # Use named remote from rclone config
            remote_path = f"{remote_name}:{clean_path}"
        elif remote_config:
            # Legacy: use provided credentials
            credentials = self._format_credentials(remote_config, 'current')
            remote_path = f"current:{path}"
            config_arg = '/dev/null'
        else:
            # Local path (use expanded path with tilde resolved)
            remote_path = clean_path

        # Check if path is a directory or file
        is_dir = self._is_directory(path, remote_config)

        if is_dir:
            # It's a directory - use purge
            command = [self.rclone_path, '--config', config_arg if config_arg else DEVNULL, 'purge', remote_path]
        else:
            # It's a file - use deletefile
            command = [self.rclone_path, '--config', config_arg if config_arg else DEVNULL, 'deletefile', remote_path]

        self._log_command(command, credentials)

        try:
            self._execute(command, credentials)
        except subprocess.CalledProcessError as e:
            raise RcloneException(f"Failed to delete {path}: {e}")

    def check(
        self,
        src_path: str,
        dst_path: str,
        src_config: Optional[Dict] = None,
        dst_config: Optional[Dict] = None,
    ) -> int:
        """
        Check integrity by comparing hashes (async, returns job_id)

        Args:
            src_path: Source path
            dst_path: Destination path
            src_config: Optional source remote config
            dst_config: Optional destination remote config

        Returns:
            job_id for tracking progress
        """
        credentials = {}
        config_arg = self.rclone_config.config_file

        # Thread-safe job ID generation
        with self._job_id_lock:
            job_id = self._next_job_id
            self._next_job_id += 1

        # Parse source path
        src_remote_name, src_clean_path = self._parse_path(src_path)
        if src_remote_name:
            # Use named remote from rclone config
            src = f"{src_remote_name}:{src_clean_path}"
        elif src_config:
            # Legacy: use provided credentials
            credentials.update(self._format_credentials(src_config, 'src'))
            src = f"src:{src_path}"
            config_arg = '/dev/null'
        else:
            # Local path (use expanded path with tilde resolved)
            src = src_clean_path

        # Parse destination path
        dst_remote_name, dst_clean_path = self._parse_path(dst_path)
        if dst_remote_name:
            # Use named remote from rclone config
            dst = f"{dst_remote_name}:{dst_clean_path}"
        elif dst_config:
            # Legacy: use provided credentials
            credentials.update(self._format_credentials(dst_config, 'dst'))
            dst = f"dst:{dst_path}"
            config_arg = '/dev/null'
        else:
            # Local path (use expanded path with tilde resolved)
            dst = dst_clean_path

        # Build command - use rclone check with hash comparison (like Motuz)
        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else DEVNULL,
            'check',
            src,
            dst,
            '--progress',
            '--stats', '2s',
        ]

        # Add logging if logs_dir is configured
        log_file_path = None
        if self.logs_dir:
            log_file_path = os.path.join(self.logs_dir, f'job_{job_id}.log')
            command.extend(['-v', '--log-file', log_file_path])
            self._job_log_files[job_id] = log_file_path
            logging.debug(f"Job {job_id} will log to: {log_file_path}")

        logging.info(f"Starting integrity check: '{src}' vs '{dst}'")

        self._log_command(command, credentials)

        # Queue the job
        try:
            self._job_queue.push(command, credentials, job_id)
        except Exception as e:
            raise RcloneException(f"Failed to start integrity check job: {e}")

        return job_id

    def sync(
        self,
        src_path: str,
        dst_path: str,
        src_config: Optional[Dict] = None,
        dst_config: Optional[Dict] = None,
    ) -> int:
        """
        Sync files/directories - DESTRUCTIVE! Deletes files at dst that don't exist at src
        (async, returns job_id)

        Args:
            src_path: Source path
            dst_path: Destination path
            src_config: Optional source remote config
            dst_config: Optional destination remote config

        Returns:
            job_id for tracking progress
        """
        return self._transfer(
            'sync',
            src_path,
            dst_path,
            src_config,
            dst_config,
            False
        )

    def size(self, path: str, remote_config: Optional[Dict] = None) -> Dict:
        """
        Get size of a path (file or directory)

        Args:
            path: Path to check (local, remote syntax, or with remote_config)
            remote_config: Optional remote configuration dict (legacy support)

        Returns:
            dict: {'bytes': <size_in_bytes>, 'count': <file_count>}
        """
        credentials = {}
        config_arg = self.rclone_config.config_file

        # Parse path to detect remote
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            # Use named remote from rclone config
            remote_path = f"{remote_name}:{clean_path}"
        elif remote_config:
            # Legacy: use provided credentials
            credentials = self._format_credentials(remote_config)
            remote_path = f":backend:{path}"
            config_arg = '/dev/null'
        else:
            # Local path
            remote_path = clean_path

        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else DEVNULL,
            'size',
            remote_path,
            '--json'
        ]

        self._log_command(command, credentials)

        try:
            output = self._execute(command, credentials)
            import json
            result = json.loads(output)
            return {
                'bytes': result.get('bytes', 0),
                'count': result.get('count', 0)
            }
        except Exception as e:
            logging.error(f"Failed to get size for {path}: {e}")
            return {'bytes': 0, 'count': 0}

    def download_to_temp(self, path: str, remote_config: Optional[Dict] = None) -> str:
        """
        Download a remote file to a temporary location

        Args:
            path: Remote path (e.g., 'remote:/path/to/file')
            remote_config: Optional remote configuration dict (legacy support)

        Returns:
            str: Path to temporary file
        """
        import tempfile

        credentials = {}
        config_arg = self.rclone_config.config_file

        # Parse path
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            remote_path = f"{remote_name}:{clean_path}"
        elif remote_config:
            credentials = self._format_credentials(remote_config)
            remote_path = f":backend:{path}"
            config_arg = '/dev/null'
        else:
            raise RcloneException("download_to_temp requires a remote path")

        # Create temp file
        fd, temp_path = tempfile.mkstemp(suffix=os.path.basename(clean_path) or '.tmp')
        os.close(fd)

        try:
            command = [
                self.rclone_path,
                '--config', config_arg if config_arg else DEVNULL,
                'copyto',
                remote_path,
                temp_path
            ]

            self._log_command(command, credentials)
            self._execute(command, credentials)

            logging.info(f"Downloaded {path} to {temp_path}")
            return temp_path

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise RcloneException(f"Failed to download {path} to temp: {e}")

    def create_download_zip_job(
        self,
        paths: List[str],
        remote_config: Optional[Dict] = None,
        estimated_size: int = 0
    ) -> int:
        """
        Create a background job to zip files/folders for download

        Args:
            paths: List of paths to include in zip
            remote_config: Optional remote configuration
            estimated_size: Estimated total size in bytes

        Returns:
            int: job_id for tracking progress
        """
        import zipfile
        import threading
        import secrets

        # Thread-safe job ID generation
        with self._job_id_lock:
            job_id = self._next_job_id
            self._next_job_id += 1

        # Generate secure random filename for zip
        zip_filename = f"download_{secrets.token_urlsafe(16)}.zip"

        # Get download cache directory
        from ..config import Config
        config = Config()  # This will use existing data_dir
        cache_dir = config.download_cache_dir

        zip_path = os.path.join(cache_dir, zip_filename)

        # Generate download token
        download_token = secrets.token_urlsafe(32)

        logging.info(f"Creating zip job {job_id} for {len(paths)} paths -> {zip_path}")

        # Create database entry
        from ..models import Database
        db = Database(config.database_path)
        db.create_job(
            job_id=job_id,
            operation='zip',
            src_path=', '.join(paths[:3]) + ('...' if len(paths) > 3 else ''),
            dst_path=zip_path
        )
        # Set initial status to pending
        db.update_job(job_id, status='pending', progress=0)

        # Worker function
        def zip_worker():
            try:
                logging.info(f"[Job {job_id}] Starting zip creation...")
                db.update_job(job_id, status='running', progress=5, log_text="Waiting for downloads to complete...")

                total_bytes_processed = 0
                temp_items_to_cleanup = []  # Track temp files/dirs to cleanup

                with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                    for idx, path in enumerate(paths):
                        try:
                            # Check if path is truly remote after resolving alias chains
                            # This handles aliases that point to local filesystem
                            # Always resolve aliases regardless of remote_config
                            local_path = self.resolve_to_local_path(path)

                            if local_path is None:
                                # Truly a remote path (or using remote_config)
                                # Still need to parse path for arcname purposes
                                remote_name, clean_path = self._parse_path(path)

                                # Keep progress low during download phase
                                # The internal copy job shows real progress
                                db.update_job(job_id, progress=5, log_text="Waiting for downloads to complete...")

                                # Check if it's a file or directory
                                is_file = self._is_remote_file(path, remote_config)

                                if is_file:
                                    # Download remote file to temp WITH PROGRESS TRACKING
                                    logging.info(f"[Job {job_id}] Downloading remote file: {path}")

                                    # Phase 1 is handled inside _download_file_to_temp_with_progress
                                    temp_path = self._download_file_to_temp_with_progress(path, job_id, remote_config)
                                    temp_items_to_cleanup.append(temp_path)

                                    # Phase 2: Compress to ZIP
                                    db.update_job(job_id, progress=95, log_text="Compressing to ZIP...")
                                    logging.info(f"[Job {job_id}] Starting compression to ZIP...")

                                    # Verify temp file exists and has content
                                    if not os.path.exists(temp_path):
                                        raise Exception(f"Temp file does not exist: {temp_path}")
                                    file_size = os.path.getsize(temp_path)
                                    logging.info(f"[Job {job_id}] Adding temp file to zip: {temp_path} (size: {file_size} bytes)")
                                    if file_size == 0:
                                        logging.warning(f"[Job {job_id}] Temp file is empty: {temp_path}")

                                    # Add to zip
                                    arcname = os.path.basename(clean_path) or f"file_{idx}"
                                    zf.write(temp_path, arcname=arcname)
                                else:
                                    # Download remote directory to temp WITH PROGRESS TRACKING
                                    logging.info(f"[Job {job_id}] Downloading remote directory: {path}")

                                    # Phase 1 is handled inside _download_dir_to_temp_with_progress
                                    temp_dir = self._download_dir_to_temp_with_progress(path, job_id, remote_config)
                                    temp_items_to_cleanup.append(temp_dir)

                                    # Phase 2: Compress to ZIP
                                    db.update_job(job_id, progress=95, log_text="Compressing to ZIP...")
                                    logging.info(f"[Job {job_id}] Starting compression to ZIP...")

                                    # Verify temp directory exists
                                    if not os.path.exists(temp_dir):
                                        raise Exception(f"Temp directory does not exist: {temp_dir}")
                                    if not os.path.isdir(temp_dir):
                                        raise Exception(f"Temp path is not a directory: {temp_dir}")

                                    # Add directory contents to zip
                                    base_name = os.path.basename(clean_path.rstrip('/')) or 'folder'
                                    file_count = 0
                                    for root, dirs, files in os.walk(temp_dir):
                                        for file in files:
                                            file_path = os.path.join(root, file)
                                            # Calculate relative path for archive
                                            rel_path = os.path.relpath(file_path, temp_dir)
                                            arcname = os.path.join(base_name, rel_path)
                                            zf.write(file_path, arcname=arcname)
                                            file_count += 1
                                    logging.info(f"[Job {job_id}] Added {file_count} files from directory {temp_dir} to zip")
                                    if file_count == 0:
                                        logging.warning(f"[Job {job_id}] Temp directory is empty: {temp_dir}")

                            else:
                                # Local path (resolved through alias chain if necessary)
                                # No download needed - directly compress
                                db.update_job(job_id, progress=95, log_text="Compressing to ZIP...")
                                logging.info(f"[Job {job_id}] Compressing local path: {local_path}")

                                if os.path.isfile(local_path):
                                    # Single file
                                    arcname = os.path.basename(local_path)
                                    zf.write(local_path, arcname=arcname)
                                elif os.path.isdir(local_path):
                                    # Directory - add recursively
                                    base_name = os.path.basename(local_path.rstrip('/'))
                                    for root, dirs, files in os.walk(local_path):
                                        for file in files:
                                            file_path = os.path.join(root, file)
                                            # Calculate relative path for archive
                                            rel_path = os.path.relpath(file_path, os.path.dirname(local_path))
                                            zf.write(file_path, arcname=rel_path)

                            # Keep progress at 95% during compression (we can't track zip progress)
                            # Don't update per file as it causes UI flickering

                        except Exception as e:
                            logging.error(f"[Job {job_id}] Error processing {path}: {e}")
                            # Continue with other files

                logging.info(f"[Job {job_id}] Zip creation complete: {zip_path}")

                # Clean up temp files/directories
                for temp_item in temp_items_to_cleanup:
                    try:
                        if os.path.isfile(temp_item):
                            os.remove(temp_item)
                        elif os.path.isdir(temp_item):
                            import shutil
                            shutil.rmtree(temp_item)
                    except Exception as e:
                        logging.warning(f"[Job {job_id}] Failed to cleanup temp item {temp_item}: {e}")

                # Check if job was cancelled while we were working
                current_job = db.get_job(job_id)
                if current_job and current_job['status'] == 'interrupted':
                    logging.info(f"[Job {job_id}] Job was cancelled, cleaning up ZIP")
                    try:
                        if os.path.exists(zip_path):
                            safe_remove(zip_path)
                    except Exception as e:
                        logging.warning(f"[Job {job_id}] Failed to cleanup cancelled ZIP: {e}")
                    return  # Don't mark as completed

                # Mark job as completed with download token and zip info
                db.update_job(
                    job_id,
                    status='completed',
                    progress=100,
                    download_token=download_token,
                    zip_path=zip_path,
                    zip_filename=zip_filename
                )

            except Exception as e:
                logging.error(f"[Job {job_id}] Zip creation failed: {e}")
                db.update_job(
                    job_id,
                    status='failed',
                    error_text=str(e)
                )
                # Clean up partial zip
                if os.path.exists(zip_path):
                    try:
                        safe_remove(zip_path)
                    except:
                        pass

        # Start worker thread
        thread = threading.Thread(target=zip_worker, daemon=True, name=f"ZipJob-{job_id}")
        thread.start()

        return job_id

    def _is_remote_file(self, path: str, remote_config: Optional[Dict] = None) -> bool:
        """
        Check if a remote path is a file (not a directory)

        Args:
            path: Remote path to check
            remote_config: Optional remote configuration

        Returns:
            True if it's a file, False if it's a directory
        """
        try:
            remote_name, clean_path = self._parse_path(path)

            # Get parent directory listing
            parent_path = os.path.dirname(clean_path.rstrip('/'))
            basename = os.path.basename(clean_path.rstrip('/'))

            if not parent_path or parent_path == '.':
                parent_path = '/'

            if remote_name:
                full_parent = f"{remote_name}:{parent_path}"
            else:
                full_parent = parent_path

            # List parent directory
            result = self.ls(full_parent, remote_config)

            # Find the item in the listing
            for item in result:
                if item.get('Name') == basename:
                    # Check if it's a file (has Size) or directory (IsDir=True)
                    return not item.get('IsDir', False)

            # If not found, assume it's a directory
            return False

        except Exception as e:
            logging.warning(f"Could not determine if {path} is file: {e}")
            # Default to file for single items
            return True

    def _download_file_to_temp_with_progress(
        self,
        path: str,
        download_job_id: int,
        remote_config: Optional[Dict] = None
    ) -> str:
        """
        Download a remote file to temp with full progress tracking

        Creates a regular rclone job and monitors it, relaying progress
        to the download job so users see detailed transfer statistics.

        Args:
            path: Remote file path
            download_job_id: The download job ID to update with progress
            remote_config: Optional remote configuration

        Returns:
            str: Path to temporary file

        Raises:
            RcloneException: If download fails or is interrupted
        """
        import shutil
        import time

        from ..models import Database
        from ..config import Config

        config = Config()
        db = Database(config.database_path)

        # Parse path
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            remote_path = path
        elif remote_config:
            remote_path = path
        else:
            raise RcloneException("_download_file_to_temp_with_progress requires a remote path")

        # Create temp file in cache directory (NOT /tmp)
        temp_dir = os.path.join(config.download_cache_dir, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

        # Generate unique temp filename
        import secrets
        temp_filename = f"download_temp_{secrets.token_urlsafe(8)}_{os.path.basename(clean_path) or 'file'}"
        temp_file = os.path.join(temp_dir, temp_filename)

        try:
            logging.info(f"[Job {download_job_id}] Starting rclone copy job for file {path}")

            # Create a regular rclone copy job (this gives us progress tracking)
            # Use the copy method which will use 'copyto' for single files
            copy_job_id = self.copy(remote_path, temp_file, src_config=remote_config)

            # IMPORTANT: Create database entry for the copy job
            # (The copy() method doesn't create a DB entry when called internally)
            db.create_job(
                job_id=copy_job_id,
                operation='copy',
                src_path=remote_path,
                dst_path=temp_file,
                src_config=remote_config,
                dst_config=None
            )

            logging.info(f"[Job {download_job_id}] Created copy job {copy_job_id} for file download")

            # Monitor the copy job and relay its progress
            while True:
                time.sleep(0.5)  # Poll every 500ms

                # Check if download job was cancelled
                download_job = db.get_job(download_job_id)
                if download_job and download_job['status'] == 'interrupted':
                    logging.info(f"[Job {download_job_id}] Download cancelled, stopping copy job {copy_job_id}")
                    # Stop the copy job
                    self.job_stop(copy_job_id)
                    # Clean up temp file
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    raise RcloneException("Download cancelled by user")

                # Get live progress from rclone job queue
                if copy_job_id in self.get_running_jobs():
                    progress = self.job_percent(copy_job_id)
                    text = self.job_text(copy_job_id)

                    # Relay progress and text to download job (Phase 1 = 0-80%)
                    db.update_job(
                        download_job_id,
                        progress=int(progress * 0.8),  # Scale to 80%
                    )

                    # Update log with Phase 1 header + copy progress
                    log_text = "Phase 1/2: Downloading from remote...\n\n" + text
                    db.update_job(download_job_id, log_text=log_text)
                else:
                    # Job no longer in running list - check if it finished successfully
                    finished = self.job_finished(copy_job_id)
                    exit_status = self.job_exitstatus(copy_job_id)
                    error_text = self.job_error_text(copy_job_id)

                    if not finished:
                        # Still pending/queued - continue waiting
                        continue

                    # Job finished - check exit status
                    if exit_status == 0:
                        logging.info(f"[Job {download_job_id}] Copy job {copy_job_id} completed successfully")
                        # Update database status
                        db.update_job(copy_job_id, status='completed', progress=100)
                        break
                    else:
                        logging.error(f"[Job {download_job_id}] Copy job {copy_job_id} failed with exit status {exit_status}")
                        # Update database status
                        db.update_job(copy_job_id, status='failed', error_text=error_text or f"Exit status: {exit_status}")
                        # Clean up temp file
                        if os.path.exists(temp_file):
                            os.remove(temp_file)
                        raise RcloneException(f"Remote download failed: {error_text or f'Exit status {exit_status}'}")

            return temp_file

        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_file):
                os.remove(temp_file)
            raise

    def _download_dir_to_temp_with_progress(
        self,
        path: str,
        download_job_id: int,
        remote_config: Optional[Dict] = None
    ) -> str:
        """
        Download a remote directory to temp with full progress tracking

        Creates a regular rclone job and monitors it, relaying progress
        to the download job so users see detailed transfer statistics.

        Args:
            path: Remote directory path
            download_job_id: The download job ID to update with progress
            remote_config: Optional remote configuration

        Returns:
            str: Path to temporary directory

        Raises:
            RcloneException: If download fails or is interrupted
        """
        import shutil
        import time

        from ..models import Database
        from ..config import Config

        config = Config()
        db = Database(config.database_path)

        # Parse path
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            remote_path = path
        elif remote_config:
            remote_path = path
        else:
            raise RcloneException("_download_dir_to_temp_with_progress requires a remote path")

        # Add trailing slash to source to copy contents (not the directory itself)
        # This prevents creating an extra path level in the zip
        if not remote_path.endswith('/'):
            remote_path += '/'

        # Create temp directory in cache (NOT /tmp)
        temp_base_dir = os.path.join(config.download_cache_dir, 'temp')
        os.makedirs(temp_base_dir, exist_ok=True)

        # Generate unique temp directory name
        import secrets
        temp_dir_name = f"download_temp_{secrets.token_urlsafe(8)}"
        temp_dir = os.path.join(temp_base_dir, temp_dir_name)
        os.makedirs(temp_dir, exist_ok=True)

        try:
            logging.info(f"[Job {download_job_id}] Starting rclone copy job for {path}")

            # Create a regular rclone copy job (this gives us progress tracking)
            copy_job_id = self.copy(remote_path, temp_dir, src_config=remote_config)

            # IMPORTANT: Create database entry for the copy job
            # (The copy() method doesn't create a DB entry when called internally)
            db.create_job(
                job_id=copy_job_id,
                operation='copy',
                src_path=remote_path,
                dst_path=temp_dir,
                src_config=remote_config,
                dst_config=None
            )

            logging.info(f"[Job {download_job_id}] Created copy job {copy_job_id}")

            # Monitor the copy job and relay its progress
            while True:
                time.sleep(0.5)  # Poll every 500ms

                # Check if download job was cancelled
                download_job = db.get_job(download_job_id)
                if download_job and download_job['status'] == 'interrupted':
                    logging.info(f"[Job {download_job_id}] Download cancelled, stopping copy job {copy_job_id}")
                    # Stop the copy job
                    self.job_stop(copy_job_id)
                    # Clean up temp directory
                    if os.path.exists(temp_dir):
                        shutil.rmtree(temp_dir)
                    raise RcloneException("Download cancelled by user")

                # Get live progress from rclone job queue
                if copy_job_id in self.get_running_jobs():
                    progress = self.job_percent(copy_job_id)
                    text = self.job_text(copy_job_id)

                    # Relay progress and text to download job (Phase 1 = 0-80%)
                    db.update_job(
                        download_job_id,
                        progress=int(progress * 0.8),  # Scale to 80%
                    )

                    # Update log with Phase 1 header + copy progress
                    log_text = "Phase 1/2: Downloading from remote...\n\n" + text
                    db.update_job(download_job_id, log_text=log_text)
                else:
                    # Job no longer in running list - check if it finished successfully
                    finished = self.job_finished(copy_job_id)
                    exit_status = self.job_exitstatus(copy_job_id)
                    error_text = self.job_error_text(copy_job_id)

                    if not finished:
                        # Still pending/queued - continue waiting
                        continue

                    # Job finished - check exit status
                    if exit_status == 0:
                        logging.info(f"[Job {download_job_id}] Copy job {copy_job_id} completed successfully")
                        # Update database status
                        db.update_job(copy_job_id, status='completed', progress=100)
                        break
                    else:
                        logging.error(f"[Job {download_job_id}] Copy job {copy_job_id} failed with exit status {exit_status}")
                        # Update database status
                        db.update_job(copy_job_id, status='failed', error_text=error_text or f"Exit status: {exit_status}")
                        # Clean up temp directory
                        if os.path.exists(temp_dir):
                            shutil.rmtree(temp_dir)
                        raise RcloneException(f"Remote download failed: {error_text or f'Exit status {exit_status}'}")

            return temp_dir

        except Exception as e:
            # Clean up on error
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise

    def _download_dir_to_temp(self, path: str, remote_config: Optional[Dict] = None) -> str:
        """
        Download a remote directory to a temporary location

        Args:
            path: Remote directory path
            remote_config: Optional remote configuration

        Returns:
            str: Path to temporary directory
        """
        import tempfile
        import shutil

        credentials = {}
        config_arg = self.rclone_config.config_file

        # Parse path
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            remote_path = f"{remote_name}:{clean_path}"
        elif remote_config:
            credentials = self._format_credentials(remote_config)
            remote_path = f":backend:{path}"
            config_arg = '/dev/null'
        else:
            raise RcloneException("_download_dir_to_temp requires a remote path")

        # Create temp directory
        temp_dir = tempfile.mkdtemp(prefix='motus_download_')

        try:
            command = [
                self.rclone_path,
                '--config', config_arg if config_arg else DEVNULL,
                'copy',
                remote_path,
                temp_dir
            ]

            self._log_command(command, credentials)
            self._execute(command, credentials)

            logging.info(f"Downloaded directory {path} to {temp_dir}")
            return temp_dir

        except Exception as e:
            # Clean up temp directory on error
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise RcloneException(f"Failed to download directory {path} to temp: {e}")

    def _path_exists(self, path: str, remote_config: Optional[Dict] = None) -> bool:
        """
        Check if a path exists (local or remote)

        Args:
            path: Path to check (can include remote syntax like 'remote:/path')
            remote_config: Optional remote configuration dict (legacy support)

        Returns:
            True if path exists, False otherwise
        """
        try:
            # Parse path to detect remote
            remote_name, clean_path = self._parse_path(path)

            if remote_name or remote_config:
                # Remote path - try to get parent directory listing
                parent_path = os.path.dirname(clean_path.rstrip('/'))
                basename = os.path.basename(clean_path.rstrip('/'))

                # Handle root directory
                if not parent_path or parent_path == '.':
                    parent_path = '/'

                # Reconstruct full parent path
                if remote_name:
                    full_parent = f"{remote_name}:{parent_path}"
                else:
                    full_parent = parent_path

                # List parent directory
                files = self.ls(full_parent, remote_config)
                return any(f['Name'] == basename for f in files)
            else:
                # Local path
                return os.path.exists(clean_path)
        except Exception as e:
            logging.debug(f"Path exists check failed for '{path}': {e}")
            return False

    def _is_directory(self, path: str, remote_config: Optional[Dict] = None) -> bool:
        """
        Check if a path is a directory (local or remote)

        Args:
            path: Path to check (can include remote syntax like 'remote:/path')
            remote_config: Optional remote configuration dict (legacy support)

        Returns:
            True if path is a directory, False otherwise
        """
        try:
            # Parse path to detect remote
            remote_name, clean_path = self._parse_path(path)

            if remote_name or remote_config:
                # Remote path - try to get parent directory listing
                parent_path = os.path.dirname(clean_path.rstrip('/'))
                basename = os.path.basename(clean_path.rstrip('/'))

                # Handle root directory
                if not parent_path or parent_path == '.':
                    parent_path = '/'

                # Reconstruct full parent path
                if remote_name:
                    full_parent = f"{remote_name}:{parent_path}"
                else:
                    full_parent = parent_path

                # List parent directory
                files = self.ls(full_parent, remote_config)
                for f in files:
                    if f['Name'] == basename:
                        return f.get('IsDir', False)
                return False
            else:
                # Local path
                return os.path.isdir(clean_path)
        except Exception as e:
            logging.debug(f"Directory check failed for '{path}': {e}")
            return False

    def _transfer(
        self,
        operation: str,  # 'copy', 'move', or 'sync'
        src_path: str,
        dst_path: str,
        src_config: Optional[Dict],
        dst_config: Optional[Dict],
        copy_links: bool,
    ) -> int:
        """
        Internal method for copy/move/sync operations with rsync-like semantics

        Implements rsync trailing slash convention:
        - Source with trailing /: copy contents (directories only)
        - Source without /: copy by name
        - Destination with trailing /: must be a directory (created if needed)
        - Destination without /: depends on what exists

        Supports both named remotes and legacy remote_config
        Examples:
            - Local to local: ('/src/file', '/dst/', None, None)
            - Remote to local: ('myS3:/bucket/file', '/dst/', None, None)
            - Local to remote: ('/src/file', 'myS3:/bucket/', None, None)
            - Legacy with config: ('/file', '/dst/', src_config, dst_config)
        """
        credentials = {}
        config_arg = self.rclone_config.config_file

        # Thread-safe job ID generation
        with self._job_id_lock:
            job_id = self._next_job_id
            self._next_job_id += 1

        # Parse trailing slashes (rsync convention)
        src_has_slash = src_path.endswith('/')
        dst_has_slash = dst_path.endswith('/')
        src_path_clean = src_path.rstrip('/')
        dst_path_clean = dst_path.rstrip('/')

        # Parse source path
        src_remote_name, src_clean_path = self._parse_path(src_path_clean)
        if src_remote_name:
            # Use named remote from rclone config
            src = f"{src_remote_name}:{src_clean_path}"
        elif src_config:
            # Legacy: use provided credentials
            credentials.update(self._format_credentials(src_config, 'src'))
            src = f"src:{src_path_clean}"
            config_arg = '/dev/null'
        else:
            # Local path (use expanded path with tilde resolved)
            src = src_clean_path

        # Parse destination path
        dst_remote_name, dst_clean_path = self._parse_path(dst_path_clean)
        if dst_remote_name:
            # Use named remote from rclone config
            dst = f"{dst_remote_name}:{dst_clean_path}"
        elif dst_config:
            # Legacy: use provided credentials
            credentials.update(self._format_credentials(dst_config, 'dst'))
            dst = f"dst:{dst_path_clean}"
            config_arg = '/dev/null'
        else:
            # Local path (use expanded path with tilde resolved)
            dst = dst_clean_path

        # Inspect source
        src_is_dir = self._is_directory(src_path_clean, src_config)
        src_basename = os.path.basename(src_clean_path)

        # Inspect destination (only if no trailing slash)
        if dst_has_slash:
            dst_is_file = False  # Assume directory
            dst_exists = None    # Don't need to check
        else:
            dst_exists = self._path_exists(dst_path_clean, dst_config)
            dst_is_file = dst_exists and not self._is_directory(dst_path_clean, dst_config)

        logging.info(f"{operation.capitalize()}: '{src_path}' -> '{dst_path}'")

        # Determine rclone command and actual paths based on rsync semantics
        rclone_cmd = None
        actual_src = src
        actual_dst = dst
        needs_mkdir = False
        mkdir_path = None
        cleanup_dir_after = None  # For directory rename cleanup

        if operation == 'sync':
            # Sync always uses 'sync' command
            rclone_cmd = 'sync'
        elif operation == 'copy':
            # COPY LOGIC
            if dst_is_file:
                # Rule 1: Destination is existing file → overwrite with copyto
                rclone_cmd = 'copyto'
            elif src_is_dir and not src_has_slash:
                # Rule 2: Source is directory without / → "copy by name"
                # Create dst/basename(src) and copy into it
                mkdir_path = f"{dst_path_clean}/{src_basename}"
                actual_dst = f"{dst}/{src_basename}"
                needs_mkdir = True
                rclone_cmd = 'copy'
            elif not dst_exists and not dst_has_slash:
                # Rule 3: Destination doesn't exist (and no /) → use copyto
                rclone_cmd = 'copyto'
            else:
                # Rule 4: Normal copy (file into dir, or dir with / copying contents)
                rclone_cmd = 'copy'
                # Preserve trailing slashes for rclone
                if src_has_slash:
                    actual_src = src + '/'
                if dst_has_slash:
                    actual_dst = dst + '/'
        elif operation == 'move':
            # MOVE LOGIC
            if dst_is_file:
                # Rule 1: Destination is existing file → overwrite with moveto
                rclone_cmd = 'moveto'
            elif not dst_exists and not dst_has_slash:
                # Rule 2: Destination doesn't exist (and no /) → rename operation
                if src_is_dir:
                    # For directory renames, use 'move' with trailing slashes
                    # This is more reliable than 'moveto' for large directories
                    # We'll create the destination and move contents, then cleanup
                    mkdir_path = dst_path_clean
                    needs_mkdir = True
                    actual_src = src + '/'
                    actual_dst = dst + '/'
                    rclone_cmd = 'move'
                    cleanup_dir_after = src_clean_path
                else:
                    # For file renames, use moveto
                    rclone_cmd = 'moveto'
            elif src_is_dir and not src_has_slash:
                # Rule 3: Source is directory without / → "move by name"
                # Create dst/basename(src) and move into it
                mkdir_path = f"{dst_path_clean}/{src_basename}"
                actual_dst = f"{dst}/{src_basename}"
                needs_mkdir = True
                rclone_cmd = 'move'
            else:
                # Rule 4: Normal move
                rclone_cmd = 'move'
                # Preserve trailing slashes for rclone
                if src_has_slash:
                    actual_src = src + '/'
                if dst_has_slash:
                    actual_dst = dst + '/'
        else:
            raise ValueError(f"Invalid operation: {operation}")

        # Create destination directory if needed (for "copy/move by name")
        if needs_mkdir and mkdir_path:
            logging.info(f"Creating destination directory: {mkdir_path}")
            try:
                # Reconstruct path with remote syntax if needed
                if dst_remote_name:
                    mkdir_full_path = f"{dst_remote_name}:{mkdir_path}"
                else:
                    mkdir_full_path = mkdir_path
                self.mkdir(mkdir_full_path, dst_config)
            except Exception as e:
                logging.warning(f"Failed to create directory {mkdir_path}: {e}")
                # Continue anyway, rclone might handle it

        # Build command (like Motuz: use --progress with --stats)
        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else DEVNULL,
            rclone_cmd,
            actual_src,
            actual_dst,
            '--progress',
            '--stats', '2s',
            '--contimeout=5m',
        ]

        # Add logging if logs_dir is configured
        log_file_path = None
        if self.logs_dir:
            log_file_path = os.path.join(self.logs_dir, f'job_{job_id}.log')
            command.extend(['-v', '--log-file', log_file_path])
            self._job_log_files[job_id] = log_file_path
            logging.debug(f"Job {job_id} will log to: {log_file_path}")

        # Add S3-specific options (for legacy mode only)
        if (src_config and src_config.get('type') == 's3') or \
           (dst_config and dst_config.get('type') == 's3'):
            command.extend([
                '--s3-disable-checksum',
                '--s3-no-check-bucket',
                '--s3-acl', 'bucket-owner-full-control',
            ])

        # Handle symlinks
        if copy_links:
            command.append('--copy-links')

        # Exclude .snapshot directories (NFS) - only for local sources
        if not src_remote_name and not src_config:
            if os.path.isdir(actual_src.rstrip('/')):
                command.append('--exclude=.snapshot/')

        self._log_command(command, credentials)

        # Queue the job
        try:
            self._job_queue.push(command, credentials, job_id)
        except Exception as e:
            raise RcloneException(f"Failed to start {operation} job: {e}")

        # For directory renames, wait for completion and cleanup synchronously
        # This ensures the source directory is removed only after all files are moved
        if cleanup_dir_after:
            logging.info(f"Directory rename - will wait for completion and cleanup")

            # Poll job status until completion (no timeout - large directories may take time)
            while True:
                if self._job_queue.is_finished(job_id):
                    break
                time.sleep(0.2)

            # Job is finished - process has exited, safe to cleanup
            exit_status = self._job_queue.get_exitstatus(job_id)
            if exit_status == 0:
                # Job succeeded - remove empty source directory
                logging.info(f"Move completed successfully, cleaning up source: {cleanup_dir_after}")
                try:
                    if src_remote_name or src_config:
                        # Remote path - use rclone rmdir (safer than purge)
                        cleanup_cmd = [
                            self.rclone_path,
                            '--config', config_arg if config_arg else DEVNULL,
                            'rmdir',
                            actual_src
                        ]
                        subprocess.run(cleanup_cmd, env={**os.environ, **credentials},
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     timeout=30)
                    else:
                        # Local path - use os.rmdir (only removes if empty)
                        os.rmdir(cleanup_dir_after)
                        logging.info(f"Successfully removed source directory: {cleanup_dir_after}")
                except OSError as e:
                    logging.warning(f"Could not remove directory {cleanup_dir_after}: {e}")
                except Exception as e:
                    logging.error(f"Failed to cleanup directory: {e}")
            else:
                logging.warning(f"Move job failed with exit status {exit_status}, skipping cleanup")

        return job_id

    # Job status methods
    def job_text(self, job_id: int) -> str:
        return self._job_queue.get_text(job_id)

    def job_error_text(self, job_id: int) -> str:
        return self._job_queue.get_error_text(job_id)

    def job_percent(self, job_id: int) -> int:
        return self._job_queue.get_percent(job_id)

    def job_log_text(self, job_id: int) -> Optional[str]:
        """Get the log file content for a job"""
        log_file = self._job_log_files.get(job_id)
        if not log_file or not os.path.exists(log_file):
            return None

        try:
            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()
        except Exception as e:
            logging.error(f"Failed to read log file for job {job_id}: {e}")
            return None

    def job_cleanup_log(self, job_id: int):
        """Delete the log file for a job after it's been stored in the database"""
        log_file = self._job_log_files.get(job_id)
        if log_file and os.path.exists(log_file):
            try:
                os.remove(log_file)
                logging.debug(f"Deleted log file for job {job_id}: {log_file}")
                # Remove from tracking dict
                del self._job_log_files[job_id]
            except Exception as e:
                logging.warning(f"Failed to delete log file for job {job_id}: {e}")

    def job_stop(self, job_id: int):
        self._job_queue.stop(job_id)

    def job_finished(self, job_id: int) -> bool:
        return self._job_queue.is_finished(job_id)

    def job_exitstatus(self, job_id: int) -> int:
        return self._job_queue.get_exitstatus(job_id)

    def job_delete(self, job_id: int):
        self._job_queue.delete(job_id)

    def get_running_jobs(self) -> List[int]:
        """Get list of currently running job IDs"""
        return self._job_queue.get_running_jobs()

    def shutdown(self):
        """Shutdown gracefully, stopping all running jobs"""
        return self._job_queue.shutdown_all()

    def _format_credentials(self, config: Dict, name: str) -> Dict[str, str]:
        """
        Format remote config as rclone environment variables

        Environment variables follow pattern:
        RCLONE_CONFIG_{NAME}_{KEY}=value
        """
        prefix = f"RCLONE_CONFIG_{name.upper()}"
        credentials = {}

        # All remotes need a type
        if 'type' not in config:
            raise ValueError("Remote config must have 'type' field")

        credentials[f'{prefix}_TYPE'] = config['type']

        # S3 credentials
        if config['type'] == 's3':
            self._add_credential(credentials, prefix, config, 'region', 'REGION')
            self._add_credential(credentials, prefix, config, 'access_key_id', 'ACCESS_KEY_ID')
            self._add_credential(credentials, prefix, config, 'secret_access_key', 'SECRET_ACCESS_KEY')
            self._add_credential(credentials, prefix, config, 'session_token', 'SESSION_TOKEN')
            self._add_credential(credentials, prefix, config, 'endpoint', 'ENDPOINT')

            if config.get('endpoint'):
                credentials[f'{prefix}_PROVIDER'] = 'Other'
            else:
                credentials[f'{prefix}_PROVIDER'] = 'AWS'

        # SFTP credentials
        elif config['type'] == 'sftp':
            credentials[f'{prefix}_SET_MODTIME'] = 'false'
            self._add_credential(credentials, prefix, config, 'host', 'HOST')
            self._add_credential(credentials, prefix, config, 'port', 'PORT')
            self._add_credential(credentials, prefix, config, 'user', 'USER')
            self._add_credential(credentials, prefix, config, 'pass', 'PASS')
            self._add_credential(credentials, prefix, config, 'key_file', 'KEY_FILE')

        # Azure Blob credentials
        elif config['type'] == 'azureblob':
            self._add_credential(credentials, prefix, config, 'account', 'ACCOUNT')
            self._add_credential(credentials, prefix, config, 'key', 'KEY')
            self._add_credential(credentials, prefix, config, 'sas_url', 'SAS_URL')

        # Add more backend types as needed...

        return credentials

    def _add_credential(
        self,
        creds: Dict[str, str],
        prefix: str,
        config: Dict,
        config_key: str,
        env_key: str
    ):
        """Helper to add credential if present in config"""
        if config_key in config and config[config_key]:
            creds[f'{prefix}_{env_key}'] = str(config[config_key])

    def _log_command(self, command: List[str], credentials: Dict[str, str]):
        """Log command with sanitized credentials"""
        sanitized = {}
        for key, value in credentials.items():
            # Log full value for non-sensitive keys
            if any(key.endswith(suffix) for suffix in [
                '_TYPE', '_REGION', '_ENDPOINT', '_HOST', '_PORT', '_USER', '_ACCOUNT'
            ]):
                sanitized[key] = value
            # Log last 4 chars for semi-sensitive keys
            elif '_ACCESS_KEY_ID' in key or '_CLIENT_ID' in key:
                sanitized[key] = '***' + value[-4:] if len(value) > 4 else '***'
            # Hide fully sensitive keys
            else:
                sanitized[key] = '***'

        env_str = ' '.join(f"{k}='{v}'" for k, v in sanitized.items())
        cmd_str = ' '.join(command)
        logging.info(f"Running: {env_str} {cmd_str}")

    def _execute(self, command: List[str], env: Optional[Dict[str, str]] = None) -> str:
        """Execute rclone command synchronously"""
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            result = subprocess.run(
                command,
                env=full_env,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout for ls/mkdir operations
            )

            if result.returncode != 0:
                stderr = result.stderr.strip()
                raise RcloneException(stderr if stderr else f"Command failed with code {result.returncode}")

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            raise RcloneException("Command timed out")
        except Exception as e:
            raise RcloneException(f"Command execution failed: {e}")
