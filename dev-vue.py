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

# Global references for cleanup
npm_process = None
backend_process = None  # Popen object (if we started the backend)
backend_monitor_thread = None

def parse_data_dir_from_args(backend_args):
    """Parse data directory from backend arguments (for legacy mode detection)"""
    import shlex

    # If backend_args is a list (from nargs), join it
    if isinstance(backend_args, list):
        args = backend_args
    else:
        # If it's a string, split it
        args = shlex.split(backend_args) if backend_args else []

    # Look for -d or --data-dir
    i = 0
    while i < len(args):
        if args[i] in ['-d', '--data-dir']:
            if i + 1 < len(args):
                return args[i + 1]
        i += 1

    # None means use XDG mode
    return None

def get_xdg_runtime_dir():
    """Get XDG runtime directory (same logic as backend)"""
    xdg_runtime = os.environ.get('XDG_RUNTIME_DIR')
    if xdg_runtime:
        return Path(xdg_runtime)
    # Fallback: /tmp/motus-{uid}
    uid = os.getuid() if hasattr(os, 'getuid') else os.getpid()
    return Path(f'/tmp/motus-{uid}')

def get_connection_info(data_dir=None):
    """
    Read connection info from existing backend instance

    Args:
        data_dir: If specified, look in this directory (legacy mode)
                 If None, look in XDG runtime dir (XDG mode)
    """
    if data_dir is None:
        # XDG mode: check runtime directory
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
            print("\n\n  [Python Monitor] Backend has stopped (Node monitor may have missed it)")
            print("  [Python Monitor] Terminating npm process...")

            # Just terminate npm - the Node.js script should have already handled Vite gracefully
            global npm_process
            if npm_process:
                try:
                    npm_process.terminate()
                    time.sleep(1)
                    if npm_process.poll() is None:
                        npm_process.kill()
                except:
                    pass

            os._exit(0)
            break

def ensure_backend_running(backend_args):
    """Ensure backend is running, start if needed"""
    global backend_process

    # Parse data directory from backend args
    data_dir = parse_data_dir_from_args(backend_args)

    conn = get_connection_info(data_dir)

    if conn:
        print(f"✓ Backend already running on port {conn['port']}")
        # Backend was already running - we don't have a Popen object
        backend_process = None
        return conn

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
        # backend_args is now a list from nargs=REMAINDER
        if isinstance(backend_args, list):
            backend_cmd.extend(backend_args)
        else:
            # Fallback if it's still a string
            import shlex
            backend_cmd.extend(shlex.split(backend_args))

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
        help='Additional arguments to pass to backend (e.g., --backend-args -e -d /tmp/motus)'
    )

    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  Motus Vue.js Development Helper")
    print("=" * 70)
    print()

    # Ensure backend is running
    conn = ensure_backend_running(args.backend_args)

    # Set environment variables for Vite
    os.environ['MOTUS_PORT'] = str(conn['port'])
    os.environ['VITE_PORT'] = str(args.port)

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

    # Setup signal handler for cleanup
    def cleanup(signum=None, frame=None):
        """Clean up npm process on exit"""
        global npm_process
        if npm_process:
            print("\n\nShutting down Vite dev server...")
            try:
                # Terminate npm gracefully - the Node.js script will handle Vite shutdown
                npm_process.terminate()
                npm_process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                # If it doesn't exit in 3 seconds, kill it
                npm_process.kill()
            except:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)

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
            env=os.environ.copy()
        )
        npm_process.wait()
    except KeyboardInterrupt:
        cleanup()

if __name__ == '__main__':
    main()
