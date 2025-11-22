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

# Global reference to npm process for cleanup
npm_process = None
backend_monitor_thread = None

def get_connection_info():
    """Read connection info from existing backend instance"""
    data_dir = Path.home() / '.motus'  # Fixed: was .motuz, should be .motus
    connection_file = data_dir / 'connection.json'

    if connection_file.exists():
        try:
            with open(connection_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    return None

def is_process_running(pid):
    """Check if a process with given PID is running"""
    try:
        # Send signal 0 - doesn't actually send a signal, just checks if process exists
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False

def monitor_backend(backend_pid):
    """Monitor backend process and trigger cleanup when it stops"""
    # Note: The Node.js dev-server.js now handles backend monitoring
    # This is kept as a backup in case the Node.js monitoring fails
    print(f"  [Python Monitor] Backup monitor active (PID: {backend_pid})")

    while True:
        time.sleep(5)  # Check less frequently since Node handles primary monitoring

        if not is_process_running(backend_pid):
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

def ensure_backend_running(backend_args=''):
    """Ensure backend is running, start if needed"""
    conn = get_connection_info()

    if conn:
        print(f"✓ Backend already running on port {conn['port']}")
        return conn

    print("Starting backend...")
    if backend_args:
        print(f"  (with args: {backend_args})")
    print("=" * 70)
    print()

    # Start backend in background (don't suppress output for debugging)
    backend_cmd = [sys.executable, 'run.py', '--no-browser']
    if backend_args:
        # Split backend_args by spaces, respecting quotes
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
        conn = get_connection_info()
        if conn:
            print()  # New line after dots
            print(f"✓ Backend started on port {conn['port']}")
            print()
            return conn

    print()
    print("✗ Backend failed to start within 30 seconds", file=sys.stderr)
    print("  Check the error messages above for details", file=sys.stderr)
    sys.exit(1)

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
        help='Vue dev server port (default: 3000)'
    )
    parser.add_argument(
        '--backend-args',
        type=str,
        default='',
        help='Additional arguments to pass to backend (e.g., "--log-level DEBUG --data-dir /tmp/motus")'
    )

    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  Motus Vue.js Development Helper")
    print("=" * 70)
    print()

    # Ensure backend is running
    conn = ensure_backend_running(args.backend_args)

    # Set environment variable for Vite proxy
    os.environ['MOTUS_PORT'] = str(conn['port'])

    # Open browser to Vue dev server with token
    if not args.no_browser:
        def open_browser():
            time.sleep(2)  # Wait for Vite to start
            vue_url = f"http://localhost:{args.port}?token={conn['token']}"
            print()
            print(f"  Opening browser to: {vue_url}")
            print()
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
    print(f"    Port: {args.port}")
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
    global backend_monitor_thread
    backend_monitor_thread = threading.Thread(
        target=monitor_backend,
        args=(conn['pid'],),
        daemon=True
    )
    backend_monitor_thread.start()

    # Start Vite dev server
    try:
        global npm_process
        npm_process = subprocess.Popen(
            ['npm', 'run', 'dev:watch'],
            cwd=Path(__file__).parent / 'frontend-vue',
            env=os.environ.copy()
        )
        npm_process.wait()
    except KeyboardInterrupt:
        cleanup()

if __name__ == '__main__':
    main()
