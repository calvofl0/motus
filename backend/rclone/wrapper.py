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

        # Verify rclone is installed
        self._verify_rclone()

        # Discover rclone config file path if not provided
        if not self.rclone_config_file:
            self.rclone_config_file = self._get_rclone_config_path()

        logging.info(f"Using rclone config: {self.rclone_config_file}")

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
            path: Path string (e.g., 'myS3:/bucket/file' or '/local/path')

        Returns:
            Tuple of (remote_name, path) where remote_name is None for local paths
            Examples:
                'myS3:/bucket/file' -> ('myS3', '/bucket/file')
                '/local/path' -> (None, '/local/path')
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
                    return (remote_name, remote_path)

        # Local path
        return (None, path)

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
            # Local path
            remote_path = path

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
            # Local path
            remote_path = path

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
            # Local path
            remote_path = path

        # Check if path exists and is a directory
        try:
            info = self.ls(path, remote_config)
            # If ls succeeds, it's a directory
            command = [self.rclone_path, '--config', config_arg if config_arg else '/dev/null', 'purge', remote_path]
        except:
            # Assume it's a file
            command = [self.rclone_path, '--config', config_arg if config_arg else '/dev/null', 'deletefile', remote_path]

        self._log_command(command, credentials)

        try:
            self._execute(command, credentials)
        except subprocess.CalledProcessError as e:
            raise RcloneException(f"Failed to delete {path}: {e}")

    def _transfer(
        self,
        operation: str,  # 'copy' or 'move'
        src_path: str,
        dst_path: str,
        src_config: Optional[Dict],
        dst_config: Optional[Dict],
        copy_links: bool,
    ) -> int:
        """
        Internal method for copy/move operations

        Supports both named remotes and legacy remote_config
        Examples:
            - Local to local: ('/src/file', '/dst/file', None, None)
            - Remote to local: ('myS3:/bucket/file', '/dst/file', None, None)
            - Local to remote: ('/src/file', 'myS3:/bucket/file', None, None)
            - Legacy with config: ('/file', '/file', src_config, dst_config)
        """
        credentials = {}
        config_arg = self.rclone_config_file
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
            # Local path
            src = src_path

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
            # Local path
            dst = dst_path

        # Build command
        rclone_cmd = 'copyto' if operation == 'copy' else 'moveto'
        command = [
            self.rclone_path,
            '--config', config_arg if config_arg else '/dev/null',
            rclone_cmd,
            src,
            dst,
            '--progress',
            '--stats', '2s',
            '--contimeout=5m',
        ]

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
            if os.path.isdir(src_path):
                command.append('--exclude=.snapshot/')

        self._log_command(command, credentials)

        # Queue the job
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
