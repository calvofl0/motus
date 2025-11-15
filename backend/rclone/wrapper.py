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

    def __init__(self, rclone_path: str = None):
        """
        Initialize rclone wrapper

        Args:
            rclone_path: Path to rclone executable (default: searches PATH)
        """
        self.rclone_path = rclone_path or self._find_rclone()
        self._job_queue = JobQueue()
        self._next_job_id = 1

        # Verify rclone is installed
        self._verify_rclone()

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

    def ls(self, path: str, remote_config: Optional[Dict] = None) -> List[Dict]:
        """
        List files and directories at path

        Args:
            path: Path to list (local or remote)
            remote_config: Optional remote configuration dict

        Returns:
            List of file/directory dicts with 'Name', 'Size', 'IsDir', etc.
        """
        credentials = {}
        remote_path = path

        if remote_config:
            credentials = self._format_credentials(remote_config, 'current')
            remote_path = f"current:{path}"

        command = [
            self.rclone_path,
            '--config=/dev/null',
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
            path: Directory path to create
            remote_config: Optional remote configuration dict
        """
        credentials = {}
        remote_path = path

        if remote_config:
            credentials = self._format_credentials(remote_config, 'current')
            remote_path = f"current:{path}"

        # Use rclone touch to create a .keep file (creates dir implicitly)
        command = [
            self.rclone_path,
            '--config=/dev/null',
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
            path: Path to delete
            remote_config: Optional remote configuration dict
        """
        credentials = {}
        remote_path = path

        if remote_config:
            credentials = self._format_credentials(remote_config, 'current')
            remote_path = f"current:{path}"

        # Check if path exists and is a directory
        try:
            info = self.ls(path, remote_config)
            # If ls succeeds, it's a directory
            command = [self.rclone_path, '--config=/dev/null', 'purge', remote_path]
        except:
            # Assume it's a file
            command = [self.rclone_path, '--config=/dev/null', 'deletefile', remote_path]

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
        """Internal method for copy/move operations"""
        credentials = {}
        job_id = self._next_job_id
        self._next_job_id += 1

        # Format source
        if src_config:
            credentials.update(self._format_credentials(src_config, 'src'))
            src = f"src:{src_path}"
        else:
            src = src_path

        # Format destination
        if dst_config:
            credentials.update(self._format_credentials(dst_config, 'dst'))
            dst = f"dst:{dst_path}"
        else:
            dst = dst_path

        # Build command
        rclone_cmd = 'copyto' if operation == 'copy' else 'moveto'
        command = [
            self.rclone_path,
            '--config=/dev/null',
            rclone_cmd,
            src,
            dst,
            '--progress',
            '--stats', '2s',
            '--contimeout=5m',
        ]

        # Add S3-specific options
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

        # Exclude .snapshot directories (NFS)
        if not src_config:  # Local source
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
