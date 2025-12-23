#!/usr/bin/env python3
"""
Development helper for Vue frontend
Ensures backend is running and opens Vue dev server with token
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

# Add src to path to import backend modules
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Import XDG logic from backend - single source of truth
from motus.backend.config import get_xdg_runtime_dir

# Global references for cleanup
npm_process = None
backend_process = None  # Popen object (if we started the backend)
backend_monitor_thread = None

def normalize_backend_args(backend_args):
    """
    Normalize backend arguments to a list.
    Handles both quoted (single string) and unquoted (multiple args) formats.
    """
    import shlex

    if not backend_args:
        return []

    if isinstance(backend_args, list):
        # If single element with spaces, it was quoted - split it
        if len(backend_args) == 1 and ' ' in backend_args[0]:
            return shlex.split(backend_args[0])
        # Otherwise use as-is
        return backend_args
    else:
        # If it's a string, split it
        return shlex.split(backend_args)


def parse_data_dir_from_args(backend_args):
    """Parse data directory from backend arguments (for legacy mode detection)"""
    args = normalize_backend_args(backend_args)

    # Look for -d or --data-dir
    i = 0
    while i < len(args):
        if args[i] in ['-d', '--data-dir']:
            if i + 1 < len(args):
                return args[i + 1]
        i += 1

    # None means use XDG mode
    return None


def get_connection_info(data_dir=None):
    """
    Read connection info from existing backend instance

    Args:
        data_dir: If specified, look in this directory (legacy mode)
                 If None, look in XDG runtime dir (XDG mode)
    """
    if data_dir is None:
        # XDG mode: check runtime directory
        # Use the backend's XDG function - single source of truth
        runtime_dir = get_xdg_runtime_dir() / 'motus'
        connection_file = runtime_dir / 'connection.json'
    else:
        # Legacy mode: check data directory
        connection_file = Path(data_dir) / 'connection.json'

    if connection_file.exists():
        try:
            with open(connection_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    return None

def is_process_running(pid, popen_obj=None):
    """
    Check if a process with given PID is running (cross-platform)

    If popen_obj is provided (we started the process), use .poll() to properly
    reap zombies. Otherwise fall back to os.kill signal check.
    """
    if popen_obj is not None:
        # We have the Popen object - use .poll() to reap zombies (cross-platform)
        return popen_obj.poll() is None
    else:
        # Backend was already running - use signal check
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

def monitor_backend(backend_pid, backend_popen=None):
    """Monitor backend process and trigger cleanup when it stops"""
    # Note: The Node.js dev-server.js now handles backend monitoring
    # This is kept as a backup in case the Node.js monitoring fails
    print(f"  [Python Monitor] Backup monitor active (PID: {backend_pid})")

    while True:
        time.sleep(5)  # Check less frequently since Node handles primary monitoring

        # Pass the Popen object to properly reap zombies (cross-platform)
        if not is_process_running(backend_pid, backend_popen):
            print("\n\n  [Python Monitor] Backend has stopped")
            print("  [Python Monitor] Shutting down Vite...")

            # Terminate npm gracefully - let the cleanup handler do its job
            global npm_process
            if npm_process:
                try:
                    npm_process.terminate()
                    npm_process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    npm_process.kill()
                except:
                    pass

            print("  [Python Monitor] Shutdown complete")
            sys.exit(0)  # Use sys.exit instead of os._exit for cleaner shutdown
            break

def ensure_backend_running(backend_args):
    """Ensure backend is running, start if needed"""
    global backend_process

    # Parse data directory from backend args
    data_dir = parse_data_dir_from_args(backend_args)

    conn = get_connection_info(data_dir)

    if conn:
        # Check if the backend process is actually running
        pid = conn.get('pid')
        if pid and is_process_running(pid):
            print(f"✓ Backend already running on port {conn['port']}")
            # Backend was already running - we don't have a Popen object
            backend_process = None
            return conn
        else:
            # Stale connection file - backend is dead
            print(f"⚠ Found stale connection file (backend PID {pid} not running)")
            # Clean up stale connection.json
            if data_dir is None:
                runtime_dir = get_xdg_runtime_dir() / 'motus'
                connection_file = runtime_dir / 'connection.json'
            else:
                connection_file = Path(data_dir) / 'connection.json'

            try:
                connection_file.unlink()
                print(f"  Cleaned up {connection_file}")
            except:
                pass
            # Fall through to start new backend

    print("Starting backend...")
    # Format backend_args for display
    if isinstance(backend_args, list):
        args_str = ' '.join(backend_args)
    else:
        args_str = backend_args
    if args_str:
        print(f"  (with args: {args_str})")
    print("=" * 70)
    print()

    # Start backend in background (don't suppress output for debugging)
    backend_cmd = [sys.executable, 'run.py', '--no-browser']
    if backend_args:
        # Normalize and extend with backend args
        backend_cmd.extend(normalize_backend_args(backend_args))

    backend_process = subprocess.Popen(
        backend_cmd,
        cwd=Path(__file__).parent
    )

    # Wait for backend to start with progress indicator
    print("Waiting for backend to initialize", end='', flush=True)
    for i in range(30):  # 30 seconds max
        time.sleep(1)
        print('.', end='', flush=True)
        conn = get_connection_info(data_dir)
        if conn:
            print()  # New line after dots
            print(f"✓ Backend started on port {conn['port']}")
            print()
            return conn

    print()
    print("✗ Backend failed to start within 30 seconds", file=sys.stderr)
    print("  Check the error messages above for details", file=sys.stderr)
    sys.exit(1)

def get_dev_port_info():
    """Read the actual port info written by dev-server.js"""
    data_dir = Path.home() / '.motus'
    dev_port_file = data_dir / 'dev-port.json'

    if dev_port_file.exists():
        try:
            with open(dev_port_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    return None

def main():
    parser = argparse.ArgumentParser(
        description='Development helper for Vue frontend'
    )
    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Do not open browser automatically'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=3000,
        help='Vue dev server port (default: 3000, may use next available if in use)'
    )
    parser.add_argument(
        '--backend-args',
        nargs=argparse.REMAINDER,
        default=[],
        help='Additional arguments to pass to backend (e.g., --backend-args -e -d /tmp/motus or --backend-args "-e -d /tmp/motus")'
    )

    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  Motus Vue.js Development Helper")
    print("=" * 70)
    print()

    # Ensure backend is running
    conn = ensure_backend_running(args.backend_args)

    # Determine where connection.json is located based on mode
    data_dir = parse_data_dir_from_args(args.backend_args)
    if data_dir is None:
        # XDG mode
        connection_dir = str(get_xdg_runtime_dir() / 'motus')
    else:
        # Legacy mode with -d
        connection_dir = data_dir

    # Set environment variables for Vite and dev-server.js
    os.environ['MOTUS_PORT'] = str(conn['port'])
    os.environ['VITE_PORT'] = str(args.port)
    os.environ['MOTUS_CONNECTION_DIR'] = connection_dir  # Tell dev-server.js where to look

    # Open browser to Vue dev server with token (will determine actual port after Vite starts)
    if not args.no_browser:
        def open_browser():
            # Wait for Vite to start and write port info
            print("  Waiting for Vite to start", end='', flush=True)
            for i in range(30):  # 30 seconds max
                time.sleep(1)
                print('.', end='', flush=True)
                port_info = get_dev_port_info()
                if port_info:
                    actual_port = port_info['port']
                    print()  # New line after dots
                    vue_url = f"http://localhost:{actual_port}?token={conn['token']}"
                    print()
                    print(f"  Opening browser to: {vue_url}")
                    if actual_port != args.port:
                        print(f"  (Note: Port {args.port} was in use, using {actual_port})")
                    print()
                    try:
                        webbrowser.open(vue_url)
                    except:
                        pass
                    return

            # Timeout - open with requested port anyway
            print()
            print("  Warning: Could not determine actual Vite port, using requested port")
            vue_url = f"http://localhost:{args.port}?token={conn['token']}"
            try:
                webbrowser.open(vue_url)
            except:
                pass

        threading.Thread(target=open_browser, daemon=True).start()

    print()
    print("  Backend Info:")
    print(f"    URL: {conn['url']}")
    print(f"    Token: {conn['token']}")
    print(f"    PID: {conn['pid']}")
    print()
    print(f"  Vue Dev Server:")
    print(f"    Requested port: {args.port}")
    print(f"    Proxy to backend: port {conn['port']}")
    print()
    print("  Starting Vite dev server...")
    print("  (Token will be saved automatically on first visit)")
    print("  (Will auto-shutdown when backend quits)")
    print()
    print("=" * 70)
    print()

    # Setup signal handlers for cleanup
    # IMPORTANT: When we started the backend, DON'T handle SIGINT!
    # The backend and dev-vue.py are in the same process group, so backend
    # will receive SIGINT directly and handle it with its job-aware logic.
    # We'll catch KeyboardInterrupt in the main loop instead.
    def cleanup_sigterm(signum, frame):
        """Handle SIGTERM - actively shut down both processes"""
        global npm_process, backend_process

        print("\n\n[dev-vue.py] SIGTERM received - shutting down...")

        # Stop Vite first
        if npm_process:
            print("  Stopping Vite dev server...")
            try:
                npm_process.terminate()
                npm_process.wait(timeout=5)
                print("  ✓ Vite stopped")
            except subprocess.TimeoutExpired:
                npm_process.kill()
                print("  ✓ Vite stopped (forced)")
            except:
                pass

        # Stop backend if we started it
        if backend_process:
            print("  Stopping backend...")
            try:
                backend_process.terminate()
                backend_process.wait(timeout=5)
                print("  ✓ Backend stopped")
            except subprocess.TimeoutExpired:
                backend_process.kill()
                print("  ✓ Backend stopped (forced)")
            except:
                pass

        print("  Shutdown complete")
        sys.exit(0)

    # Only handle SIGTERM - let SIGINT raise KeyboardInterrupt naturally
    signal.signal(signal.SIGTERM, cleanup_sigterm)

    # Start backend monitoring thread
    global backend_monitor_thread, backend_process
    backend_monitor_thread = threading.Thread(
        target=monitor_backend,
        args=(conn['pid'], backend_process),
        daemon=True
    )
    backend_monitor_thread.start()

    # Start Vite dev server
    try:
        global npm_process
        npm_process = subprocess.Popen(
            ['npm', 'run', 'dev:watch'],
            cwd=Path(__file__).parent / 'frontend',
            env=os.environ.copy(),
            start_new_session=True  # Run in separate process group to avoid SIGINT from Ctrl-C
        )
        npm_process.wait()
    except KeyboardInterrupt:
        # Ctrl-C pressed - backend received SIGINT too and is handling it
        print("\n\n[dev-vue.py] Ctrl-C received")

        if backend_process:
            # We started the backend - wait for it to complete its graceful shutdown
            # (it has job-aware logic that might require user confirmation)
            print("  Backend is handling shutdown (checking for running jobs)...")
            print("  (Vite will stay running until backend finishes)")

            try:
                # Wait for backend to exit - no timeout, respect its shutdown logic
                backend_process.wait()
                print("  Backend has exited")
            except:
                pass

        # Now stop Vite
        if npm_process:
            print("  Stopping Vite dev server...")
            try:
                npm_process.terminate()
                npm_process.wait(timeout=5)
                print("  ✓ Vite stopped")
            except subprocess.TimeoutExpired:
                npm_process.kill()
                print("  ✓ Vite stopped (forced)")
            except:
                pass

        print("  Shutdown complete")

if __name__ == '__main__':
    main()
