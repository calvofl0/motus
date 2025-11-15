"""
Configuration management for OOD-Motuz
Handles environment variables, config files, and defaults
"""
import os
import secrets
import yaml
from pathlib import Path
from typing import Optional


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

        # Data directory (default: ~/.motuz)
        self.data_dir = self._get_config(
            'data_dir',
            env_var='MOTUZ_DATA_DIR',
            default=str(Path.home() / '.motuz')
        )
        os.makedirs(self.data_dir, exist_ok=True)

        # Port configuration (like Jupyter)
        self.port = int(self._get_config(
            'port',
            env_var='MOTUZ_PORT',
            default=8888
        ))

        # Port search range for fallback
        self.port_retries = int(self._get_config(
            'port_retries',
            env_var='MOTUZ_PORT_RETRIES',
            default=100
        ))

        # Authentication token
        self.token = self._get_config(
            'token',
            env_var='MOTUZ_TOKEN',
            default=None
        )

        # Auto-generate token if not provided
        if not self.token:
            self.token = self._generate_token()
            self.token_auto_generated = True
        else:
            self.token_auto_generated = False

        # Database path
        self.database_path = os.path.join(self.data_dir, 'motuz.db')

        # Log level
        self.log_level = self._get_config(
            'log_level',
            env_var='MOTUZ_LOG_LEVEL',
            default='WARNING'
        ).upper()

        # Log file
        self.log_file = os.path.join(self.data_dir, 'motuz.log')

        # Flask secret key (for sessions)
        self.secret_key = self._get_config(
            'secret_key',
            env_var='MOTUZ_SECRET_KEY',
            default=None
        )
        if not self.secret_key:
            self.secret_key = secrets.token_hex(32)

        # Allow CORS (for development)
        self.allow_cors = self._get_config(
            'allow_cors',
            env_var='MOTUZ_ALLOW_CORS',
            default='false'
        ).lower() == 'true'

        # Rclone path
        self.rclone_path = self._get_config(
            'rclone_path',
            env_var='MOTUZ_RCLONE_PATH',
            default=None
        )

        # Rclone config file path
        # Priority: RCLONE_CONFIG env var > motuz config > rclone default
        self.rclone_config_file = self._get_config(
            'rclone_config_file',
            env_var='RCLONE_CONFIG',
            default=None
        )

        # Base URL (for reverse proxy setups)
        self.base_url = self._get_config(
            'base_url',
            env_var='MOTUZ_BASE_URL',
            default=''
        ).rstrip('/')

        # Host to bind to
        self.host = self._get_config(
            'host',
            env_var='MOTUZ_HOST',
            default='127.0.0.1'
        )

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
