"""
Configuration management for Motus
Handles environment variables, config files, and defaults
"""
import os
import re
import secrets
import yaml
from pathlib import Path
from typing import Optional


def parse_size(size_str: str) -> int:
    """
    Parse size string to bytes

    Supports formats:
    - Plain number: "1024" = 1024 bytes
    - With unit: "50M", "50MB", "1G", "1GB", "100K", "100KB"
    - Zero/unlimited: "0", "unlimited" = 0 (no limit)

    Returns:
        int: Size in bytes, or 0 for unlimited
    """
    if not size_str:
        return 0

    size_str = str(size_str).strip().upper()

    # Check for unlimited
    if size_str in ('0', 'UNLIMITED', 'NONE', ''):
        return 0

    # Parse size with unit
    match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?B?)$', size_str)
    if not match:
        raise ValueError(f"Invalid size format: {size_str}. Use formats like: 50M, 1G, 1024")

    value = float(match.group(1))
    unit = match.group(2)

    # Convert to bytes
    multipliers = {
        '': 1,
        'B': 1,
        'K': 1024,
        'KB': 1024,
        'M': 1024 ** 2,
        'MB': 1024 ** 2,
        'G': 1024 ** 3,
        'GB': 1024 ** 3,
        'T': 1024 ** 4,
        'TB': 1024 ** 4,
    }

    return int(value * multipliers.get(unit, 1))


def format_size(size_bytes: int) -> str:
    """
    Format bytes to human-readable size

    Args:
        size_bytes: Size in bytes

    Returns:
        str: Human-readable size (e.g., "50 MB", "1.5 GB")
    """
    if size_bytes == 0:
        return "unlimited"

    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}" if size_bytes % 1 else f"{int(size_bytes)} {unit}"
        size_bytes /= 1024.0

    return f"{size_bytes:.1f} PB"


class Config:
    """Application configuration"""

    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize configuration

        Priority: CLI args > Env vars > Config file > Defaults
        """
        # Load config file if exists
        self.config_data = {}
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                self.config_data = yaml.safe_load(f) or {}

        # Data directory (default: ~/.motus)
        self.data_dir = self._get_config(
            'data_dir',
            env_var='MOTUS_DATA_DIR',
            default=str(Path.home() / '.motus')
        )
        os.makedirs(self.data_dir, exist_ok=True)

        # Port configuration (like Jupyter)
        self.port = int(self._get_config(
            'port',
            env_var='MOTUS_PORT',
            default=8888
        ))

        # Port search range for fallback
        self.port_retries = int(self._get_config(
            'port_retries',
            env_var='MOTUS_PORT_RETRIES',
            default=100
        ))

        # Authentication token
        self.token = self._get_config(
            'token',
            env_var='MOTUS_TOKEN',
            default=None
        )

        # Auto-generate token if not provided
        if not self.token:
            self.token = self._generate_token()
            self.token_auto_generated = True
        else:
            self.token_auto_generated = False

        # Database path
        self.database_path = os.path.join(self.data_dir, 'motus.db')

        # Log level
        self.log_level = self._get_config(
            'log_level',
            env_var='MOTUS_LOG_LEVEL',
            default='WARNING'
        ).upper()

        # Log file
        self.log_file = os.path.join(self.data_dir, 'motus.log')

        # Flask secret key (for sessions)
        self.secret_key = self._get_config(
            'secret_key',
            env_var='MOTUS_SECRET_KEY',
            default=None
        )
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)

        # Allow CORS (for development)
        self.allow_cors = self._get_config(
            'allow_cors',
            env_var='MOTUS_ALLOW_CORS',
            default='false'
        ).lower() == 'true'

        # Rclone path
        self.rclone_path = self._get_config(
            'rclone_path',
            env_var='MOTUS_RCLONE_PATH',
            default=None
        )

        # Rclone config file path
        # Priority: RCLONE_CONFIG env var > motus config > rclone default
        self.rclone_config_file = self._get_config(
            'rclone_config_file',
            env_var='RCLONE_CONFIG',
            default=None
        )

        # Base URL (for reverse proxy setups)
        self.base_url = self._get_config(
            'base_url',
            env_var='MOTUS_BASE_URL',
            default=''
        ).rstrip('/')

        # Host to bind to
        self.host = self._get_config(
            'host',
            env_var='MOTUS_HOST',
            default='127.0.0.1'
        )

        # Default UI mode (easy or expert)
        self.default_mode = self._get_config(
            'default_mode',
            env_var='MOTUS_DEFAULT_MODE',
            default='easy'
        ).lower()

        # Remote templates file path
        # Priority: MOTUS_REMOTE_TEMPLATES env var > motus config > default
        self.remote_templates_file = self._get_config(
            'remote_templates_file',
            env_var='MOTUS_REMOTE_TEMPLATES',
            default=None
        )

        # Max idle time (in seconds) before auto-quit
        # 0 or None means disabled
        self.max_idle_time = int(self._get_config(
            'max_idle_time',
            env_var='MOTUS_MAX_IDLE_TIME',
            default=0
        ) or 0)

        # Auto-cleanup database at startup if no failed/interrupted jobs
        self.auto_cleanup_db = self._get_config(
            'auto_cleanup_db',
            env_var='MOTUS_AUTO_CLEANUP_DB',
            default='false'
        ).lower() == 'true'

        # Max upload size (total size of all files in one upload)
        # Supports formats: 50M, 1G, 1024 (bytes), 0 or "unlimited" = no limit
        # Default: 0 (unlimited)
        max_upload_size_str = self._get_config(
            'max_upload_size',
            env_var='MOTUS_MAX_UPLOAD_SIZE',
            default='0'
        )
        try:
            self.max_upload_size = parse_size(max_upload_size_str)
        except ValueError as e:
            raise ValueError(f"Invalid max_upload_size: {e}")

    def _get_config(self, key: str, env_var: str, default: any) -> any:
        """Get config value with priority: env var > config file > default"""
        # Check environment variable first
        env_value = os.environ.get(env_var)
        if env_value is not None:
            return env_value

        # Check config file
        if key in self.config_data:
            return self.config_data[key]

        # Return default
        return default

    def _generate_token(self) -> str:
        """Generate a random authentication token (like Jupyter)"""
        return secrets.token_urlsafe(32)

    def save_config_file(self, path: Optional[str] = None):
        """Save current configuration to YAML file"""
        if path is None:
            path = os.path.join(self.data_dir, 'config.yml')

        config_dict = {
            'data_dir': self.data_dir,
            'port': self.port,
            'log_level': self.log_level,
            'base_url': self.base_url,
            'host': self.host,
            # Don't save sensitive data like tokens
        }

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False)

    def get_url(self, token: bool = True) -> str:
        """Get the application URL"""
        url = f"http://{self.host}:{self.port}{self.base_url}"
        if token and self.token:
            url += f"?token={self.token}"
        return url

    def __repr__(self):
        return (
            f"Config(data_dir={self.data_dir}, port={self.port}, "
            f"host={self.host}, base_url={self.base_url})"
        )
