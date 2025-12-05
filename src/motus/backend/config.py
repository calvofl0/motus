"""
Configuration management for Motus
Handles environment variables, config files, and defaults

XDG Base Directory Specification Support:
- Respects XDG_CONFIG_HOME, XDG_DATA_HOME, XDG_CACHE_HOME, XDG_RUNTIME_DIR
- Priority: CLI flags > Config file > MOTUS_* env vars > XDG_* env vars > defaults
- Legacy --data-dir overrides XDG (puts everything in one directory)
"""
import os
import re
import secrets
import yaml
from pathlib import Path
from typing import Optional


def get_xdg_config_home() -> Path:
    """Get XDG config directory"""
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))


def get_xdg_data_home() -> Path:
    """Get XDG data directory"""
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share'))


def get_xdg_cache_home() -> Path:
    """Get XDG cache directory"""
    return Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))


def get_xdg_runtime_dir() -> Path:
    """Get XDG runtime directory"""
    xdg_runtime = os.environ.get('XDG_RUNTIME_DIR')
    if xdg_runtime:
        return Path(xdg_runtime)
    # Fallback: /tmp/motus-{uid} or /var/tmp/motus-{uid}
    uid = os.getuid() if hasattr(os, 'getuid') else os.getpid()
    runtime_dir = Path(f'/tmp/motus-{uid}')
    return runtime_dir


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

        Priority: CLI args > Config file > MOTUS_* env > XDG_* env > Defaults

        XDG Mode (default):
        - Config: XDG_CONFIG_HOME/motus (default: ~/.config/motus)
        - Data: XDG_DATA_HOME/motus (default: ~/.local/share/motus)
        - Cache: XDG_CACHE_HOME/motus (default: ~/.cache/motus)
        - Runtime: XDG_RUNTIME_DIR/motus (default: /tmp/motus-{uid})

        Legacy Mode (if --data-dir is set):
        - Everything goes to the specified data_dir
        """
        # Load config file if exists
        self.config_data = {}
        if config_file and os.path.exists(config_file):
            with open(config_file, 'r') as f:
                self.config_data = yaml.safe_load(f) or {}

        # Check if data_dir is explicitly set (legacy mode)
        # Priority: MOTUS_DATA_DIR env var > config file
        # Note: CLI args are handled separately and override this
        legacy_data_dir = None
        if os.environ.get('MOTUS_DATA_DIR'):
            legacy_data_dir = os.environ.get('MOTUS_DATA_DIR')
        elif 'data_dir' in self.config_data:
            legacy_data_dir = self.config_data['data_dir']

        # Determine if we're in legacy mode or XDG mode
        self.use_xdg = legacy_data_dir is None

        if self.use_xdg:
            # XDG Mode: separate directories for config, data, cache, runtime
            self.config_dir = str(get_xdg_config_home() / 'motus')
            self.data_dir = str(get_xdg_data_home() / 'motus')
            self.runtime_dir = str(get_xdg_runtime_dir() / 'motus')

            # Cache can be overridden separately
            cache_override = self._get_config(
                'cache_path',
                env_var='MOTUS_CACHE_PATH',
                default=None
            )
            if cache_override:
                self.cache_path = cache_override
            else:
                self.cache_path = str(get_xdg_cache_home() / 'motus')
        else:
            # Legacy Mode: everything in data_dir
            self.data_dir = legacy_data_dir
            self.config_dir = self.data_dir
            self.runtime_dir = self.data_dir
            self.cache_path = self._get_config(
                'cache_path',
                env_var='MOTUS_CACHE_PATH',
                default=os.path.join(self.data_dir, 'cache')
            )

        # Create directories
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.cache_path, exist_ok=True)
        os.makedirs(self.runtime_dir, exist_ok=True)

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

        # Database path (in data directory)
        self.database_path = os.path.join(self.data_dir, 'motus.db')

        # Log level
        self.log_level = self._get_config(
            'log_level',
            env_var='MOTUS_LOG_LEVEL',
            default='WARNING'
        ).upper()

        # Log file (in cache directory - logs are ephemeral)
        self.log_file = os.path.join(self.cache_path, 'motus.log')

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

        # Additional remotes config file to merge at startup
        # Remotes from this file will be added to rclone config (existing remotes are not overwritten)
        self.extra_remotes_file = self._get_config(
            'extra_remotes_file',
            env_var='MOTUS_EXTRA_REMOTES',
            default=None
        )

        # Local filesystem alias remote
        # If set, this alias remote (which must resolve to local filesystem) replaces
        # the "Local Filesystem" option in the UI and becomes the default
        self.local_filesystem_alias = self._get_config(
            'local_filesystem_alias',
            env_var='MOTUS_LOCAL_FILESYSTEM_ALIAS',
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
        # Priority: MOTUS_REMOTE_TEMPLATES env var > motus config > config_dir/remote_templates.conf (if exists) > None
        self.remote_templates_file = self._get_config(
            'remote_templates_file',
            env_var='MOTUS_REMOTE_TEMPLATES',
            default=None
        )

        # If not specified, check for default file in config directory
        if not self.remote_templates_file:
            default_templates_path = os.path.join(self.config_dir, 'remote_templates.conf')
            if os.path.exists(default_templates_path):
                self.remote_templates_file = default_templates_path

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

        # Allow expert mode toggle in UI
        # If false, the Expert/Easy Mode toggle will be hidden
        self.allow_expert_mode = self._get_config(
            'allow_expert_mode',
            env_var='MOTUS_ALLOW_EXPERT_MODE',
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

        # Max uncompressed download size before creating zip
        # If total size exceeds this, files will be zipped
        # Supports formats: 50M, 1G, 1024 (bytes)
        # Default: 100M
        max_uncompressed_download_size_str = self._get_config(
            'max_uncompressed_download_size',
            env_var='MOTUS_MAX_UNCOMPRESSED_DOWNLOAD_SIZE',
            default='100M'
        )
        try:
            self.max_uncompressed_download_size = parse_size(max_uncompressed_download_size_str)
        except ValueError as e:
            raise ValueError(f"Invalid max_uncompressed_download_size: {e}")

        # Max total download size (before compression)
        # If total size exceeds this limit, download will be rejected
        # Supports formats: 50M, 1G, 1024 (bytes), 0 or "unlimited" = no limit
        # Default: 0 (unlimited)
        max_download_size_str = self._get_config(
            'max_download_size',
            env_var='MOTUS_MAX_DOWNLOAD_SIZE',
            default='0'
        )
        try:
            self.max_download_size = parse_size(max_download_size_str)
        except ValueError as e:
            raise ValueError(f"Invalid max_download_size: {e}")

        # Download cache max age (in seconds)
        # How long to keep zip files before cleanup
        # Default: 3600 (1 hour)
        self.download_cache_max_age = int(self._get_config(
            'download_cache_max_age',
            env_var='MOTUS_DOWNLOAD_CACHE_MAX_AGE',
            default=3600
        ) or 3600)

        # Specific cache subdirectories (computed from cache_path)
        self.download_cache_dir = os.path.join(self.cache_path, 'download')
        self.upload_cache_dir = os.path.join(self.cache_path, 'upload')
        self.log_cache_dir = os.path.join(self.cache_path, 'log')

        # Create cache subdirectories
        os.makedirs(self.download_cache_dir, exist_ok=True)
        os.makedirs(self.upload_cache_dir, exist_ok=True)
        os.makedirs(self.log_cache_dir, exist_ok=True)

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
