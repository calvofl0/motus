"""
Configuration management for Motus
Handles environment variables, config files, and defaults

XDG Base Directory Specification Support:
- Respects XDG_CONFIG_HOME, XDG_DATA_HOME, XDG_CACHE_HOME, XDG_RUNTIME_DIR
- Each directory can be overridden independently:
  - Config: MOTUS_CONFIG_DIR env var > config_dir in config file > XDG_CONFIG_HOME/motus
  - Cache: MOTUS_CACHE_DIR env var > cache_dir in config file > XDG_CACHE_HOME/motus
  - Runtime: MOTUS_RUNTIME_DIR env var > runtime_dir in config file > XDG_RUNTIME_DIR/motus
  - Data: Always XDG_DATA_HOME/motus in XDG mode
- Priority: CLI flags > MOTUS_* env vars > Config file > XDG_* env vars > Defaults
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

        Priority: CLI args > MOTUS_* env vars > Config file > XDG_* env vars > Defaults

        XDG Mode (default when no --data-dir, MOTUS_DATA_DIR, or data_dir in config):
        - Config: MOTUS_CONFIG_DIR > config_dir in config file > XDG_CONFIG_HOME/motus (~/.config/motus)
        - Data: XDG_DATA_HOME/motus (~/.local/share/motus)
        - Cache: MOTUS_CACHE_DIR > cache_dir in config file > XDG_CACHE_HOME/motus (~/.cache/motus)
        - Runtime: MOTUS_RUNTIME_DIR > runtime_dir in config file > XDG_RUNTIME_DIR/motus (/run/user/{uid}/motus)

        Legacy Mode (if --data-dir, MOTUS_DATA_DIR, or data_dir in config file is set):
        - Everything goes to the specified data_dir by default
        - But individual directories can still be overridden:
          - Config: MOTUS_CONFIG_DIR > config_dir in config file > data_dir
          - Runtime: MOTUS_RUNTIME_DIR > runtime_dir in config file > data_dir
          - Cache: MOTUS_CACHE_DIR > cache_dir in config file > data_dir/cache
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
            # Each can be overridden independently via MOTUS_* env vars or config file
            # (except data_dir - setting MOTUS_DATA_DIR triggers legacy mode instead)

            # Config directory (for preferences.json, etc.)
            config_override = self._get_config(
                'config_dir',
                env_var='MOTUS_CONFIG_DIR',
                default=None
            )
            if config_override:
                self.config_dir = config_override
            else:
                self.config_dir = str(get_xdg_config_home() / 'motus')

            # Data directory (for database, etc.) - always XDG in XDG mode
            self.data_dir = str(get_xdg_data_home() / 'motus')

            # Runtime directory (for connection.json, PID files, etc.)
            runtime_override = self._get_config(
                'runtime_dir',
                env_var='MOTUS_RUNTIME_DIR',
                default=None
            )
            if runtime_override:
                self.runtime_dir = runtime_override
            else:
                self.runtime_dir = str(get_xdg_runtime_dir() / 'motus')

            # Cache directory (for temporary files, logs, etc.)
            cache_override = self._get_config(
                'cache_dir',
                env_var='MOTUS_CACHE_DIR',
                default=None
            )
            if cache_override:
                self.cache_dir = cache_override
            else:
                self.cache_dir = str(get_xdg_cache_home() / 'motus')
        else:
            # Legacy Mode: everything in data_dir by default
            # But individual directories can still be overridden
            self.data_dir = legacy_data_dir

            # Config directory - can be overridden even in legacy mode
            config_override = self._get_config(
                'config_dir',
                env_var='MOTUS_CONFIG_DIR',
                default=None
            )
            self.config_dir = config_override if config_override else self.data_dir

            # Runtime directory - can be overridden even in legacy mode
            runtime_override = self._get_config(
                'runtime_dir',
                env_var='MOTUS_RUNTIME_DIR',
                default=None
            )
            self.runtime_dir = runtime_override if runtime_override else self.data_dir

            # Cache directory - can be overridden even in legacy mode
            self.cache_dir = self._get_config(
                'cache_dir',
                env_var='MOTUS_CACHE_DIR',
                default=os.path.join(self.data_dir, 'cache')
            )

        # Create directories
        os.makedirs(self.config_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.cache_dir, exist_ok=True)
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

        # Log file (in cache directory - logs are ephemeral, unless overridden)
        self.log_file = self._get_config(
            'log_file',
            env_var='MOTUS_LOG_FILE',
            default=os.path.join(self.cache_dir, 'motus.log')
        )

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
        # Relative paths are resolved against config_dir
        self.extra_remotes_file = self._get_config(
            'extra_remotes_file',
            env_var='MOTUS_EXTRA_REMOTES',
            default=None
        )
        if self.extra_remotes_file and not os.path.isabs(self.extra_remotes_file):
            self.extra_remotes_file = os.path.join(self.config_dir, self.extra_remotes_file)

        # Startup remote - Default remote to show on both panes at startup
        self.startup_remote = self._get_config(
            'startup_remote',
            env_var='MOTUS_STARTUP_REMOTE',
            default=None
        )

        # Local filesystem entry name - Name for local filesystem remote in UI
        # Default: "Local Filesystem", empty string hides it from the list
        self.local_fs = self._get_config(
            'local_fs',
            env_var='MOTUS_LOCAL_FS',
            default='Local Filesystem'
        )

        # Absolute paths mode - Show absolute filesystem paths for local aliases
        # Implies non-empty local_fs
        self.absolute_paths = self._get_config(
            'absolute_paths',
            env_var='MOTUS_ABSOLUTE_PATHS',
            default='false'
        ).lower() == 'true'

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
        # Relative paths are resolved against config_dir
        self.remote_templates_file = self._get_config(
            'remote_templates_file',
            env_var='MOTUS_REMOTE_TEMPLATES',
            default=None
        )

        # Resolve relative paths against config_dir
        if self.remote_templates_file and not os.path.isabs(self.remote_templates_file):
            self.remote_templates_file = os.path.join(self.config_dir, self.remote_templates_file)

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
        # Supports: 'true', 'false', ISO timestamps, relative times (5h, 30min, 45s)
        auto_cleanup_str = self._get_config(
            'auto_cleanup_db',
            env_var='MOTUS_AUTO_CLEANUP_DB',
            default='false'
        )
        self.auto_cleanup_db = self._parse_cleanup_time(auto_cleanup_str)

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

        # Specific cache subdirectories (computed from cache_dir)
        self.download_cache_dir = os.path.join(self.cache_dir, 'download')
        self.upload_cache_dir = os.path.join(self.cache_dir, 'upload')
        self.log_cache_dir = os.path.join(self.cache_dir, 'log')

        # Create cache subdirectories
        os.makedirs(self.download_cache_dir, exist_ok=True)
        os.makedirs(self.upload_cache_dir, exist_ok=True)
        os.makedirs(self.log_cache_dir, exist_ok=True)

    def _parse_cleanup_time(self, value: str):
        """
        Parse auto_cleanup_db time value. Returns one of:
        - None: cleanup disabled
        - True: cleanup all completed jobs
        - datetime: cleanup jobs completed before this absolute timestamp
        - timedelta: cleanup jobs completed more than this duration ago

        Supported formats:
        - 'false', 'no', '0': disabled
        - 'true', 'yes', '1': cleanup all completed jobs
        - ISO timestamp: '2006-08-14T02:34:56+01:00' or '2006-08-14'
        - Relative time: '5h', '30min', '45s', '2d', '1 hour', '3 days', '1 month', '2 years'
        """
        from datetime import datetime, timedelta
        import re

        value = value.strip().lower()

        # Boolean: false/disabled
        if value in ('false', 'no', '0', ''):
            return None

        # Boolean: true/enabled (cleanup all)
        if value in ('true', 'yes', '1'):
            return True

        # Try parsing as ISO timestamp
        try:
            # Try full ISO format with timezone
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            pass

        try:
            # Try date-only format (assume start of day UTC)
            if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
                return datetime.fromisoformat(value + 'T00:00:00+00:00')
        except ValueError:
            pass

        # Try parsing as relative time (e.g., "5h", "1 day", "3 months", "2 years")
        # Allow optional whitespace between number and unit
        time_pattern = r'^(\d+(?:\.\d+)?)\s*(s|sec|seconds?|m|min|minutes?|h|hr|hours?|d|days?|mo|mon|months?|y|yr|years?)$'
        match = re.match(time_pattern, value)
        if match:
            amount = float(match.group(1))
            unit = match.group(2)

            if unit in ('s', 'sec', 'second', 'seconds'):
                return timedelta(seconds=amount)
            elif unit in ('m', 'min', 'minute', 'minutes'):
                return timedelta(minutes=amount)
            elif unit in ('h', 'hr', 'hour', 'hours'):
                return timedelta(hours=amount)
            elif unit in ('d', 'day', 'days'):
                return timedelta(days=amount)
            elif unit in ('mo', 'mon', 'month', 'months'):
                # Approximate: 1 month = 30 days
                return timedelta(days=amount * 30)
            elif unit in ('y', 'yr', 'year', 'years'):
                # Approximate: 1 year = 365 days
                return timedelta(days=amount * 365)

        # Invalid format - log warning and disable
        import logging
        logging.warning(f"Invalid auto_cleanup_db value '{value}' - disabling cleanup. "
                       f"Use 'true', ISO timestamp, or relative time (e.g., '5h', '1 day', '3 months')")
        return None

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
