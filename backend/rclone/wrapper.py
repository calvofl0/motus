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
from typing import Dict, List, Optional

from .exceptions import RcloneException, RcloneNotFoundError
from .job_queue import JobQueue


class RcloneWrapper:
    """
    Wrapper around rclone command-line tool for file operations.
    Supports local filesystem and cloud backends (S3, SFTP, etc.)
    """

    def __init__(self, rclone_path: str = None, rclone_config_file: str = None):
        """
        Initialize rclone wrapper

        Args:
            rclone_path: Path to rclone executable (default: searches PATH)
            rclone_config_file: Path to rclone config file (default: rclone default)
        """
        self.rclone_path = rclone_path or self._find_rclone()
        self.rclone_config_file = rclone_config_file
        self._job_queue = JobQueue()
        self._next_job_id = 1
        self._job_id_lock = __import__('threading').Lock()  # Thread-safe job ID generation

        # Verify rclone is installed
        self._verify_rclone()

        # Discover rclone config file path if not provided
        if not self.rclone_config_file:
            self.rclone_config_file = self._get_rclone_config_path()

        logging.info(f"Using rclone config: {self.rclone_config_file}")

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

            # Use custom config file if specified
            if self.rclone_config_file:
                command.extend(['--config', self.rclone_config_file])

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
        if path != expanded:
            logging.info(f"Expanded tilde path '{path}' -> '{expanded}'")
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
        config_arg = self.rclone_config_file

        # Check if path uses remote syntax (remote_name:/path)
        remote_name, clean_path = self._parse_path(path)

        if remote_name:
            # Use named remote from rclone config
            remote_path = f"{remote_name}:{clean_path}"
        elif remote_config:
            # Legacy: use provided credentials
            credentials = self._format_credentials(remote_config, 'current')
            remote_path = f"current:{path}"
            config_arg = '/dev/null'  # Don't use config file with env vars
        else:
            # Local path (use expanded path with tilde resolved)
            remote_path = clean_path

        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else '/dev/null',
            'lsjson',
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
        config_arg = self.rclone_config_file

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

        # Use rclone touch to create a .keep file (creates dir implicitly)
        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else '/dev/null',
            'touch',
            f"{remote_path}/.motuz_keep",
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
        config_arg = self.rclone_config_file

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
            command = [self.rclone_path, '--config', config_arg if config_arg else '/dev/null', 'purge', remote_path]
        else:
            # It's a file - use deletefile
            command = [self.rclone_path, '--config', config_arg if config_arg else '/dev/null', 'deletefile', remote_path]

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
        config_arg = self.rclone_config_file

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

        # Build command - use rclone check with hash comparison
        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else '/dev/null',
            'check',
            src,
            dst,
            '--progress',
            '--stats', '2s',
        ]

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
        config_arg = self.rclone_config_file

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

        logging.info(f"Starting {operation}: '{src_path}' -> '{dst_path}'")
        logging.debug(f"Source: is_dir={src_is_dir}, has_slash={src_has_slash}")
        logging.debug(f"Destination: is_file={dst_is_file}, has_slash={dst_has_slash}, exists={dst_exists}")

        # Determine rclone command and actual paths based on rsync semantics
        rclone_cmd = None
        actual_src = src
        actual_dst = dst
        needs_mkdir = False
        mkdir_path = None
        needs_src_cleanup = False  # For directory moveto operations

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
                # Rule 2: Destination doesn't exist (and no /) → moveto (handles rename!)
                rclone_cmd = 'moveto'
                # For directory moveto, we need to cleanup source directory after move
                if src_is_dir:
                    needs_src_cleanup = True
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

        # Build command
        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else '/dev/null',
            rclone_cmd,
            actual_src,
            actual_dst,
            '--progress',
            '--stats', '2s',
            '--contimeout=5m',
        ]

        logging.info(f"Executing: rclone {rclone_cmd} '{actual_src}' '{actual_dst}'")

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

        # For directory moveto, we need to cleanup the source directory after move
        # because rclone moveto leaves it empty
        if operation == 'move' and needs_src_cleanup:
            # Build cleanup command to remove empty source directory
            cleanup_cmd = [
                self.rclone_path,
                '--config', config_arg if config_arg else '/dev/null',
                'rmdirs',
                actual_src,
                '--leave-root',  # Don't delete the root directory itself
            ]

            # Chain the commands using shell
            # This ensures cleanup happens after the move completes
            command_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in command)
            cleanup_str = ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in cleanup_cmd)

            # Use bash to chain commands with &&
            chained_command = [
                'bash', '-c',
                f'{command_str} && {cleanup_str}'
            ]

            logging.info(f"Chaining moveto with cleanup: {chained_command[-1]}")

            # Queue the chained command
            try:
                self._job_queue.push(chained_command, credentials, job_id)
            except Exception as e:
                raise RcloneException(f"Failed to start {operation} job: {e}")
        else:
            # Queue the job normally
            try:
                self._job_queue.push(command, credentials, job_id)
            except Exception as e:
                raise RcloneException(f"Failed to start {operation} job: {e}")

        return job_id

    # Job status methods
    def job_text(self, job_id: int) -> str:
        return self._job_queue.get_text(job_id)

    def job_error_text(self, job_id: int) -> str:
        return self._job_queue.get_error_text(job_id)

    def job_percent(self, job_id: int) -> int:
        return self._job_queue.get_percent(job_id)

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
