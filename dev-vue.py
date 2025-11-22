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
    print(f"  [Monitor] Watching backend process (PID: {backend_pid})")

    while True:
        time.sleep(2)  # Check every 2 seconds

        if not is_process_running(backend_pid):
            print("\n\n  [Monitor] Backend has stopped")
            print("  [Monitor] Auto-shutting down Vite dev server...")
            # Send SIGTERM to our own process to trigger cleanup
            os.kill(os.getpid(), signal.SIGTERM)
            break

def ensure_backend_running():
    """Ensure backend is running, start if needed"""
    conn = get_connection_info()

    if conn:
        print(f"✓ Backend already running on port {conn['port']}")
        return conn

    print("Starting backend...")
    print("=" * 70)
    print()

    # Start backend in background (don't suppress output for debugging)
    backend_process = subprocess.Popen(
        [sys.executable, 'run.py', '--no-browser'],
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

    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  Motus Vue.js Development Helper")
    print("=" * 70)
    print()

    # Ensure backend is running
    conn = ensure_backend_running()

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
                # Use SIGKILL to forcefully kill the process group (Vite is resilient to SIGTERM)
                os.killpg(os.getpgid(npm_process.pid), signal.SIGKILL)
            except (ProcessLookupError, AttributeError):
                try:
                    npm_process.kill()  # SIGKILL instead of terminate()
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
            ['npm', 'run', 'dev'],
            cwd=Path(__file__).parent / 'frontend-vue',
            env=os.environ.copy(),
            # Create new process group so we can kill all children
            preexec_fn=os.setsid if hasattr(os, 'setsid') else None
        )
        npm_process.wait()
    except KeyboardInterrupt:
        cleanup()

if __name__ == '__main__':
    main()
