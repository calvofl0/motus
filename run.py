#!/usr/bin/env python3
"""
Motus startup script
Handles port allocation, token generation, and server startup
"""
import argparse
import json
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

try:
    import psutil
except ImportError:
    psutil = None
    print("Warning: psutil not installed. Multi-instance detection disabled.")
    print("Install with: pip install psutil")

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.config import Config
from backend.app import create_app


def is_port_in_use(host: str, port: int) -> bool:
    """Check if a port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def find_available_port(host: str, start_port: int, max_retries: int = 100) -> int:
    """
    Find an available port starting from start_port

    Args:
        host: Host to bind to
        start_port: Initial port to try
        max_retries: Maximum number of ports to try

    Returns:
        Available port number

    Raises:
        RuntimeError: If no available port found
    """
    for offset in range(max_retries):
        port = start_port + offset
        if not is_port_in_use(host, port):
            return port

    raise RuntimeError(
        f"Could not find available port in range {start_port}-{start_port + max_retries}"
    )


def print_banner(config: Config, original_port: int = None):
    """Print startup banner with access information"""
    print("\n" + "=" * 70)
    print("  Motus et bouche cousue — A Web-based File Transfer Interface")
    print("=" * 70)
    print()

    if original_port and original_port != config.port:
        print(f"  Note: Port {original_port} was in use")
        print(f"  Using fallback port: {config.port}")
        print()

    url = config.get_url(token=True)
    url_no_token = config.get_url(token=False)

    print(f"  Access URL (with token):")
    print(f"    {url}")
    print()
    print(f"  Or copy and paste one of these URLs:")
    print(f"    {url_no_token}")
    print(f"    http://127.0.0.1:{config.port}{config.base_url}")
    print()

    if config.token_auto_generated:
        print(f"  Access Token (auto-generated):")
        print(f"    {config.token}")
        print()
    else:
        print(f"  Access Token:")
        print(f"    {config.token}")
        print()

    print(f"  Data directory: {config.data_dir}")
    print(f"  Log file: {config.log_file}")
    print(f"  Log level: {config.log_level}")
    print()
    print("=" * 70)
    print()
    print("  Press Ctrl+C to stop the server")
    print()


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running"""
    if psutil is None:
        return False  # Can't check without psutil

    try:
        return psutil.Process(pid).is_running()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def check_existing_instance(config: Config) -> dict:
    """
    Check if an instance is already running on this data directory

    Returns:
        dict with connection info if running, None otherwise
    """
    if psutil is None:
        return None  # Skip check if psutil not available

    data_dir = Path(config.data_dir)
    pid_file = data_dir / 'motus.pid'
    connection_file = data_dir / 'connection.json'

    if not pid_file.exists():
        return None  # No PID file = no running instance

    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())

        if not is_process_running(pid):
            # Stale PID file from crash
            pid_file.unlink()
            if connection_file.exists():
                connection_file.unlink()
            return None

        # Process is running, read connection info
        if connection_file.exists():
            with open(connection_file, 'r') as f:
                return json.load(f)

        return None  # Process running but no connection file (shouldn't happen)

    except (ValueError, FileNotFoundError, json.JSONDecodeError) as e:
        # Corrupted files, clean up
        logging.warning(f"Corrupted instance files: {e}")
        try:
            pid_file.unlink()
        except:
            pass
        try:
            connection_file.unlink()
        except:
            pass
        return None


def write_connection_info(config: Config):
    """Write PID and connection info files"""
    data_dir = Path(config.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    pid_file = data_dir / 'motus.pid'
    connection_file = data_dir / 'connection.json'

    # Write PID
    with open(pid_file, 'w') as f:
        f.write(str(os.getpid()))

    # Write connection info
    connection_info = {
        'pid': os.getpid(),
        'url': config.get_url(token=True),
        'url_no_token': config.get_url(token=False),
        'host': config.host,
        'port': config.port,
        'token': config.token,
        'data_dir': str(config.data_dir)
    }

    with open(connection_file, 'w') as f:
        json.dump(connection_info, f, indent=2)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Motus et bouche cousue — A Web-based File Transfer Interface'
    )
    parser.add_argument(
        '--port',
        type=int,
        help='Port to run on (default: 8888, or MOTUS_PORT env var)'
    )
    parser.add_argument(
        '--host',
        type=str,
        help='Host to bind to (default: 127.0.0.1, or MOTUS_HOST env var)'
    )
    parser.add_argument(
        '--token',
        type=str,
        help='Access token (default: auto-generated, or MOTUS_TOKEN env var)'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        help='Data directory (default: ~/.motuz, or MOTUS_DATA_DIR env var)'
    )
    parser.add_argument(
        '--config',
        type=str,
        help='Path to config file (YAML)'
    )
    parser.add_argument(
        '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Log level (default: WARNING, or MOTUS_LOG_LEVEL env var)'
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not open browser automatically'
    )
    parser.add_argument(
        '--allow-cors',
        action='store_true',
        help='Enable CORS (for development)'
    )
    parser.add_argument(
        '--expert-mode',
        action='store_true',
        help='Start in Expert mode instead of Easy mode (default: Easy, or MOTUS_DEFAULT_MODE env var)'
    )

    args = parser.parse_args()

    # Create config
    config = Config(config_file=args.config)

    # Override config with CLI args
    if args.port:
        config.port = args.port
    if args.host:
        config.host = args.host
    if args.token:
        config.token = args.token
        config.token_auto_generated = False
    if args.data_dir:
        config.data_dir = args.data_dir
    if args.log_level:
        config.log_level = args.log_level
    if args.allow_cors:
        config.allow_cors = True
    if args.expert_mode:
        config.default_mode = 'expert'

    # Check for existing instance on this data directory
    existing = check_existing_instance(config)
    if existing:
        print("\n" + "=" * 70)
        print("  Motus is already running!")
        print("=" * 70)
        print(f"\n  An instance is already running on this data directory:")
        print(f"    Data dir: {existing.get('data_dir', config.data_dir)}")
        print(f"\n  Connection details:")
        print(f"    URL (with token): {existing.get('url')}")
        print(f"    URL (no token):   {existing.get('url_no_token')}")
        print(f"    Token: {existing.get('token')}")
        print(f"\n  To run a second instance, use a different data directory:")
        print(f"    python run.py --data-dir /path/to/different/dir")
        print("\n" + "=" * 70 + "\n")

        if not args.no_browser:
            try:
                webbrowser.open(existing.get('url'))
            except:
                pass  # Ignore browser failures

        sys.exit(0)

    # Find available port (with fallback like Jupyter)
    original_port = config.port
    if is_port_in_use(config.host, config.port):
        try:
            config.port = find_available_port(
                config.host,
                config.port,
                config.port_retries
            )
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    # Create Flask app
    try:
        app = create_app(config)
    except Exception as e:
        print(f"Error creating application: {e}", file=sys.stderr)
        logging.exception("Application creation failed")
        sys.exit(1)

    # Write connection info for instance detection
    try:
        write_connection_info(config)
    except Exception as e:
        logging.warning(f"Could not write connection info: {e}")

    # Print banner
    print_banner(config, original_port if original_port != config.port else None)

    # Open browser after server starts (delayed)
    if not args.no_browser:
        def open_browser():
            time.sleep(1.5)  # Wait for server to start
            try:
                webbrowser.open(config.get_url(token=True))
            except:
                pass  # Ignore browser open failures

        threading.Thread(target=open_browser, daemon=True).start()

    # Run server
    try:
        app.run(
            host=config.host,
            port=config.port,
            debug=False,
            threaded=True,
        )
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        sys.exit(0)
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr)
        logging.exception("Server error")
        sys.exit(1)


if __name__ == '__main__':
    main()
