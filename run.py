#!/usr/bin/env python3
"""
OOD-Motuz startup script
Handles port allocation, token generation, and server startup
"""
import argparse
import logging
import socket
import sys
import webbrowser
from pathlib import Path

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
    print("  OOD-Motuz - Web-based File Transfer Interface")
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


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='OOD-Motuz - Web-based File Transfer Interface'
    )
    parser.add_argument(
        '--port',
        type=int,
        help='Port to run on (default: 8888, or MOTUZ_PORT env var)'
    )
    parser.add_argument(
        '--host',
        type=str,
        help='Host to bind to (default: 127.0.0.1, or MOTUZ_HOST env var)'
    )
    parser.add_argument(
        '--token',
        type=str,
        help='Access token (default: auto-generated, or MOTUZ_TOKEN env var)'
    )
    parser.add_argument(
        '--data-dir',
        type=str,
        help='Data directory (default: ~/.motuz, or MOTUZ_DATA_DIR env var)'
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
        help='Log level (default: WARNING, or MOTUZ_LOG_LEVEL env var)'
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

    # Print banner
    print_banner(config, original_port if original_port != config.port else None)

    # Open browser if requested
    if not args.no_browser:
        try:
            webbrowser.open(config.get_url(token=True))
        except:
            pass  # Ignore browser open failures

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
