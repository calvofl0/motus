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
    print("Warning: psutil not installed. Multi-instance detection will be limited.")
    print("Install with: pip install psutil")

# Add src to path for development (when not installed)
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from motus.backend.config import Config, parse_size
from motus.backend.app import create_app, get_instance_status, setup_logging

# Global lock socket for instance detection
_lock_socket = None
_get_backend_status = None  # Callback to get backend status (set after app creation)


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


def has_unix_sockets() -> bool:
    """Check if Unix domain sockets are supported on this platform"""
    return hasattr(socket, 'AF_UNIX')


def check_via_socket(config: Config) -> dict:
    """
    Check if instance is running using socket-based locking with status protocol

    Protocol:
    - Connect to lock socket
    - Receive status: "running", "grace_period", or "startup"
    - If "running": instance is active, exit
    - If "grace_period": instance is waiting for re-registration (F5), poll and wait
    - If "startup": instance is starting up, no frontends yet, exit

    This method is robust against PID namespace issues in containers
    and auto-cleans up on process crashes.

    Returns:
        dict with connection info if running, None otherwise
    """
    if not has_unix_sockets():
        return None  # Fall back to PID checking

    runtime_dir = Path(config.runtime_dir)
    lock_socket_path = runtime_dir / 'motus.lock'
    connection_file = runtime_dir / 'connection.json'

    # If lock socket doesn't exist, no instance is running
    if not lock_socket_path.exists():
        return None

    # Try to connect and get status
    max_wait_time = 15  # Maximum time to wait for grace period (should be > 10s grace period)
    poll_interval = 1   # Check every second
    start_time = time.time()

    while True:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(str(lock_socket_path))

            # Receive status from backend
            sock.settimeout(2.0)
            try:
                status = sock.recv(1024).decode('utf-8').strip()
            except socket.timeout:
                status = "running"  # Default if no response (backward compat)

            sock.close()

            # Handle different statuses
            if status == "grace_period":
                elapsed = time.time() - start_time
                if elapsed < max_wait_time:
                    logging.info(f"Instance in grace period, waiting... ({elapsed:.1f}s / {max_wait_time}s)")
                    time.sleep(poll_interval)
                    continue  # Poll again
                else:
                    logging.info("Grace period wait timeout, treating as stale")
                    return None  # Timeout - let us start

            elif status in ("running", "startup"):
                # Instance is running or starting up
                # Read connection info
                if connection_file.exists():
                    try:
                        with open(connection_file, 'r') as f:
                            conn_info = json.load(f)
                        logging.debug(f"Found running instance via socket (status: {status}): {conn_info.get('url')}")
                        return conn_info
                    except (json.JSONDecodeError, FileNotFoundError) as e:
                        logging.warning(f"Running instance found but connection file corrupted: {e}")
                        return {'running': True}  # Running but no connection info

                return {'running': True}

            else:
                # Unknown status, treat as running
                logging.warning(f"Unknown instance status: {status}")
                return {'running': True}

        except (ConnectionRefusedError, FileNotFoundError, OSError) as e:
            # Socket exists but can't connect = stale socket from crash
            logging.debug(f"Stale lock socket detected: {e}")
            try:
                lock_socket_path.unlink()
                logging.debug("Removed stale lock socket")
            except Exception as unlink_err:
                logging.warning(f"Could not remove stale lock socket: {unlink_err}")
            return None
        except Exception as e:
            logging.warning(f"Unexpected error checking lock socket: {e}")
            return None
        finally:
            try:
                sock.close()
            except:
                pass


def set_backend_status_callback(callback):
    """Set callback to query backend status for lock socket protocol"""
    global _get_backend_status
    _get_backend_status = callback


def create_lock_socket(config: Config):
    """
    Create and bind lock socket to prevent multiple instances

    The socket implements a status protocol:
    - Accepts connections
    - Sends status: "running", "grace_period", or "startup"
    - Closes connection

    Returns:
        Socket object if successful, None otherwise
    """
    global _lock_socket

    if not has_unix_sockets():
        logging.debug("Unix domain sockets not supported, skipping socket lock")
        return None

    runtime_dir = Path(config.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)
    lock_socket_path = runtime_dir / 'motus.lock'

    logging.debug(f"Creating lock socket at: {lock_socket_path}")
    logging.debug(f"Runtime directory exists: {runtime_dir.exists()}")
    logging.debug(f"Runtime directory is writable: {os.access(runtime_dir, os.W_OK)}")

    # Remove stale socket if exists
    if lock_socket_path.exists():
        try:
            lock_socket_path.unlink()
            logging.debug("Removed existing lock socket")
        except Exception as e:
            logging.warning(f"Could not remove existing lock socket: {e}")
            return None

    # Create socket
    try:
        _lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        _lock_socket.bind(str(lock_socket_path))
        _lock_socket.listen(1)

        # Verify socket file was created
        if lock_socket_path.exists():
            logging.debug(f"Created lock socket at {lock_socket_path}")
        else:
            logging.error(f"Socket bind succeeded but file not created at {lock_socket_path}")
            logging.error(f"Socket details: {_lock_socket}")
            # Continue anyway - socket might still work

        # Handle connections in background thread with status protocol
        def handle_socket_connections():
            while True:
                try:
                    conn, _ = _lock_socket.accept()

                    # Get backend status
                    if _get_backend_status:
                        status = _get_backend_status()
                    else:
                        status = "startup"  # Default before backend is ready

                    # Send status to client
                    try:
                        conn.sendall(status.encode('utf-8'))
                    except Exception as send_err:
                        logging.debug(f"Error sending status: {send_err}")

                    conn.close()

                except Exception as e:
                    # Socket closed or error - thread should exit
                    logging.debug(f"Lock socket handler exiting: {e}")
                    break

        thread = threading.Thread(target=handle_socket_connections, daemon=True)
        thread.start()

        return _lock_socket

    except Exception as e:
        logging.warning(f"Could not create lock socket: {e}")
        _lock_socket = None
        return None


def cleanup_lock_socket(config: Config):
    """Remove lock socket on shutdown"""
    global _lock_socket

    if _lock_socket:
        try:
            _lock_socket.close()
            logging.debug("Closed lock socket")
        except Exception as e:
            logging.warning(f"Error closing lock socket: {e}")
        finally:
            _lock_socket = None

    lock_socket_path = Path(config.runtime_dir) / 'motus.lock'
    try:
        if lock_socket_path.exists():
            lock_socket_path.unlink()
            logging.debug(f"Removed lock socket file: {lock_socket_path}")
    except Exception as e:
        logging.warning(f"Could not remove lock socket file: {e}")


def is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running"""
    if psutil is None:
        return False  # Can't check without psutil

    try:
        return psutil.Process(pid).is_running()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def is_process_motus(pid: int) -> bool:
    """
    Check if a process with given PID is actually Motus

    This helps avoid false positives from PID reuse or container PID namespaces
    """
    if psutil is None:
        return True  # Can't verify, assume true (fallback to old behavior)

    try:
        proc = psutil.Process(pid)
        cmdline = ' '.join(proc.cmdline()).lower()
        name = proc.name().lower()

        # Check if process looks like Motus
        # Could be "python run.py", "python -m motus", or "motus" executable
        is_motus = (
            'motus' in cmdline or
            'motus' in name or
            ('python' in name and 'run.py' in cmdline)
        )

        if not is_motus:
            logging.debug(f"PID {pid} is running but doesn't look like Motus: {name} {cmdline}")

        return is_motus

    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    except Exception as e:
        logging.warning(f"Error checking if process is Motus: {e}")
        return True  # Can't verify, assume true


def check_existing_instance(config: Config) -> dict:
    """
    Check if an instance is already running

    Uses socket-based locking (primary) with fallback to PID checking.

    Returns:
        dict with connection info if running, None otherwise
    """
    # Primary method: Socket-based checking (works in containers)
    existing = check_via_socket(config)
    if existing is not None:
        return existing

    # Fallback method: Enhanced PID file checking with process name verification
    if psutil is None:
        return None  # Skip PID check if psutil not available

    runtime_dir = Path(config.runtime_dir)
    pid_file = runtime_dir / 'motus.pid'
    connection_file = runtime_dir / 'connection.json'

    if not pid_file.exists():
        return None  # No PID file = no running instance

    try:
        with open(pid_file, 'r') as f:
            pid = int(f.read().strip())

        if not is_process_running(pid):
            # Stale PID file from crash
            logging.debug(f"Stale PID file detected (process {pid} not running)")
            pid_file.unlink()
            if connection_file.exists():
                connection_file.unlink()
            return None

        # Process is running - verify it's actually Motus
        if not is_process_motus(pid):
            # PID reused by different process
            logging.warning(f"PID {pid} is running but is not Motus (PID reuse). Cleaning up.")
            pid_file.unlink()
            if connection_file.exists():
                connection_file.unlink()
            return None

        # Process is running and is Motus, read connection info
        if connection_file.exists():
            try:
                with open(connection_file, 'r') as f:
                    conn_info = json.load(f)
                logging.debug(f"Found running instance via PID: {conn_info.get('url')}")
                return conn_info
            except json.JSONDecodeError as e:
                logging.warning(f"Corrupted connection file: {e}")

        return {'running': True}  # Process running but no connection file

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
    """Write PID and connection info files to runtime directory"""
    runtime_dir = Path(config.runtime_dir)
    runtime_dir.mkdir(parents=True, exist_ok=True)

    pid_file = runtime_dir / 'motus.pid'
    connection_file = runtime_dir / 'connection.json'

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
        'data_dir': str(config.data_dir),
        'runtime_dir': str(config.runtime_dir),
        'config_dir': str(config.config_dir),
        'cache_dir': str(config.cache_dir),
        'use_xdg': config.use_xdg
    }

    with open(connection_file, 'w') as f:
        json.dump(connection_info, f, indent=2)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Motus et bouche cousue — A Web-based File Transfer Interface',
        allow_abbrev=False  # Require full argument names (no abbreviations)
    )
    parser.add_argument(
        '-p', '--port',
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
        '-d', '--data-dir',
        type=str,
        help='Data directory (default: ~/.motus, or MOTUS_DATA_DIR env var)'
    )
    parser.add_argument(
        '--cache-dir',
        type=str,
        help='Cache directory for temporary files (default: {data_dir}/cache, or MOTUS_CACHE_DIR env var)'
    )
    parser.add_argument(
        '-c', '--config',
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
        '--log-file',
        type=str,
        help='Path to log file (default: {cache_dir}/motus.log, or MOTUS_LOG_FILE env var)'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='count',
        default=0,
        help='Increase verbosity: -v for INFO, -vv for DEBUG (--log-level takes precedence)'
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
    parser.add_argument(
        '--remote-templates',
        type=str,
        help='Path to remote templates file (default: none, or MOTUS_REMOTE_TEMPLATES env var)'
    )
    parser.add_argument(
        '-r', '--extra-remotes',
        type=str,
        help='Path to rclone config file with remotes to add at startup (existing remotes not overwritten, MOTUS_EXTRA_REMOTES env var)'
    )
    parser.add_argument(
        '-s', '--startup-remote',
        type=str,
        help='Default remote to show on both panes at startup (default: none, or MOTUS_STARTUP_REMOTE env var)'
    )
    parser.add_argument(
        '-l', '--local-fs',
        type=str,
        help='Name for local filesystem remote (default: "Local Filesystem", or MOTUS_LOCAL_FS env var)'
    )
    parser.add_argument(
        '-H', '--hide-local-fs',
        action='store_true',
        help='Hide local filesystem from remote dropdown (can be overridden by --absolute-paths or when no startup-remote, or MOTUS_HIDE_LOCAL_FS env var)'
    )
    parser.add_argument(
        '--absolute-paths',
        action='store_true',
        help='Show absolute filesystem paths for local aliases with auto-switching (implies visible local-fs, or MOTUS_ABSOLUTE_PATHS env var)'
    )
    parser.add_argument(
        '--max-idle-time',
        type=int,
        help='Auto-quit after N seconds of inactivity (0=disabled, default: 0, or MOTUS_MAX_IDLE_TIME env var)'
    )
    parser.add_argument(
        '--auto-cleanup-db',
        action='store_true',
        help='Auto-cleanup database at startup if no failed/interrupted jobs (default: false, or MOTUS_AUTO_CLEANUP_DB env var)'
    )
    parser.add_argument(
        '--max-upload-size',
        type=str,
        help='Maximum total upload size per operation (e.g., 50M, 1G, 0=unlimited, default: 0, or MOTUS_MAX_UPLOAD_SIZE env var)'
    )
    parser.add_argument(
        '--max-uncompressed-download-size',
        type=str,
        help='Maximum uncompressed download size before zipping (e.g., 50M, 1G, default: 100M, or MOTUS_MAX_UNCOMPRESSED_DOWNLOAD_SIZE env var)'
    )
    parser.add_argument(
        '-m', '--max-download-size',
        type=str,
        help='Maximum total download size allowed (e.g., 50M, 1G, 0=unlimited, default: 0, or MOTUS_MAX_DOWNLOAD_SIZE env var)'
    )
    parser.add_argument(
        '-e', '--allow-expert-mode',
        action='store_true',
        help='Show Expert/Easy Mode toggle in UI (default: hidden, or MOTUS_ALLOW_EXPERT_MODE env var)'
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
        # CLI --data-dir overrides everything and switches to legacy mode
        config.use_xdg = False
        config.data_dir = args.data_dir
        config.config_dir = args.data_dir
        config.runtime_dir = args.data_dir
        config.database_path = os.path.join(args.data_dir, 'motus.db')
        if not args.cache_dir:
            config.cache_dir = os.path.join(args.data_dir, 'cache')
        config.log_file = os.path.join(config.cache_dir, 'motus.log')
        # Update derived cache directories
        config.download_cache_dir = os.path.join(config.cache_dir, 'download')
        config.upload_cache_dir = os.path.join(config.cache_dir, 'upload')
        config.log_cache_dir = os.path.join(config.cache_dir, 'log')
        # Update remote templates path
        default_templates_path = os.path.join(args.data_dir, 'remote_templates.conf')
        if not args.remote_templates and os.path.exists(default_templates_path):
            config.remote_templates_file = default_templates_path
        # Create directories
        os.makedirs(config.data_dir, exist_ok=True)
        os.makedirs(config.config_dir, exist_ok=True)
        os.makedirs(config.runtime_dir, exist_ok=True)
        os.makedirs(config.cache_dir, exist_ok=True)
        os.makedirs(config.download_cache_dir, exist_ok=True)
        os.makedirs(config.upload_cache_dir, exist_ok=True)
        os.makedirs(config.log_cache_dir, exist_ok=True)
    if args.cache_dir:
        config.cache_dir = args.cache_dir
        config.log_file = os.path.join(config.cache_dir, 'motus.log')
        # Update derived cache directories
        config.download_cache_dir = os.path.join(config.cache_dir, 'download')
        config.upload_cache_dir = os.path.join(config.cache_dir, 'upload')
        config.log_cache_dir = os.path.join(config.cache_dir, 'log')
        # Create cache subdirectories
        os.makedirs(config.download_cache_dir, exist_ok=True)
        os.makedirs(config.upload_cache_dir, exist_ok=True)
        os.makedirs(config.log_cache_dir, exist_ok=True)
    if args.log_level:
        config.log_level = args.log_level
    elif args.verbose == 1:
        config.log_level = 'INFO'
    elif args.verbose >= 2:
        config.log_level = 'DEBUG'
    if args.log_file:
        config.log_file = args.log_file
    if args.allow_cors:
        config.allow_cors = True
    if args.expert_mode:
        config.default_mode = 'expert'
        # Enforce --allow-expert-mode when starting in expert mode
        config.allow_expert_mode = True
    if args.remote_templates:
        # Resolve relative paths against config_dir
        if not os.path.isabs(args.remote_templates):
            config.remote_templates_file = os.path.join(config.config_dir, args.remote_templates)
        else:
            config.remote_templates_file = args.remote_templates
    if args.extra_remotes:
        # Resolve relative paths against config_dir
        if not os.path.isabs(args.extra_remotes):
            config.extra_remotes_file = os.path.join(config.config_dir, args.extra_remotes)
        else:
            config.extra_remotes_file = args.extra_remotes
    if args.startup_remote:
        config.startup_remote = args.startup_remote
    if args.local_fs is not None:  # Allow empty string to disable
        config.local_fs = args.local_fs
    if args.absolute_paths:
        config.absolute_paths = True
    if args.max_idle_time is not None:
        config.max_idle_time = args.max_idle_time
    if args.auto_cleanup_db:
        config.auto_cleanup_db = True
    if args.max_upload_size:
        try:
            config.max_upload_size = parse_size(args.max_upload_size)
        except ValueError as e:
            print(f"Error: Invalid --max-upload-size: {e}", file=sys.stderr)
            sys.exit(1)
    if args.max_uncompressed_download_size:
        try:
            config.max_uncompressed_download_size = parse_size(args.max_uncompressed_download_size)
        except ValueError as e:
            print(f"Error: Invalid --max-uncompressed-download-size: {e}", file=sys.stderr)
            sys.exit(1)
    if args.max_download_size:
        try:
            config.max_download_size = parse_size(args.max_download_size)
        except ValueError as e:
            print(f"Error: Invalid --max-download-size: {e}", file=sys.stderr)
            sys.exit(1)
    if args.allow_expert_mode:
        config.allow_expert_mode = True

    # Configure logging EARLY, before any logging calls
    # This must happen before check_existing_instance() and create_lock_socket()
    # because those functions use logging
    setup_logging(config)

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

    # Create lock socket to prevent multiple instances
    try:
        sock = create_lock_socket(config)
        if sock:
            logging.debug(f"Lock socket created successfully")
        else:
            logging.warning("Lock socket creation returned None (likely not supported)")
    except Exception as e:
        logging.error(f"Exception during lock socket creation: {e}")
        import traceback
        logging.error(traceback.format_exc())

    # Create Flask app
    try:
        app = create_app(config)
    except Exception as e:
        print(f"Error creating application: {e}", file=sys.stderr)
        logging.exception("Application creation failed")
        cleanup_lock_socket(config)
        sys.exit(1)

    # Set backend status callback for lock socket protocol
    set_backend_status_callback(get_instance_status)

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
            use_reloader=False,  # Disable Flask's signal handlers to allow custom SIGINT handling
        )
    except KeyboardInterrupt:
        print("\n\nShutting down...")
    except Exception as e:
        print(f"Error running server: {e}", file=sys.stderr)
        logging.exception("Server error")
        sys.exit(1)
    finally:
        # Cleanup lock socket on shutdown
        cleanup_lock_socket(config)


if __name__ == '__main__':
    main()
