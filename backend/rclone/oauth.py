"""
OAuth token refresh functionality for rclone remotes
"""
import logging
import re
import subprocess
import threading
import time
from typing import Dict, Optional, Tuple


def is_oauth_remote(remote_config: Dict[str, str]) -> bool:
    """
    Check if a remote uses OAuth authentication by checking for token field

    This is more maintainable than hardcoding provider types, as it works
    with any rclone version and only shows refresh button when there's
    actually a token to refresh.

    Args:
        remote_config: The remote's configuration dict

    Returns:
        True if the remote has a token field (OAuth-based), False otherwise
    """
    return 'token' in remote_config


class OAuthRefreshManager:
    """
    Manages OAuth token refresh operations for rclone remotes
    """

    def __init__(self, rclone_path: str, rclone_config_file: str):
        """
        Initialize OAuth refresh manager

        Args:
            rclone_path: Path to rclone executable
            rclone_config_file: Path to rclone config file
        """
        self.rclone_path = rclone_path
        self.rclone_config_file = rclone_config_file
        self._active_sessions: Dict[str, Dict] = {}
        self._lock = threading.Lock()

    def start_oauth_refresh(self, remote_name: str, callback_url: str) -> Tuple[bool, str, Optional[str]]:
        """
        Start an OAuth token refresh for a remote

        Args:
            remote_name: Name of the remote to refresh
            callback_url: The callback URL that should be used (e.g., https://motus-server/api/oauth/callback)

        Returns:
            Tuple of (success, message, auth_url)
            - success: True if started successfully
            - message: Status or error message
            - auth_url: The OAuth URL to redirect the user to (None on error)
        """
        # Clean up any existing session for this remote first
        # This prevents "address already in use" errors from leftover processes
        with self._lock:
            if remote_name in self._active_sessions:
                session = self._active_sessions[remote_name]
                if session.get('status') == 'pending':
                    # Already in progress, return existing URL
                    return True, 'OAuth refresh already in progress', session.get('auth_url')
                else:
                    # Old session exists, clean it up first (inline to avoid deadlock)
                    logging.info(f"Cleaning up old OAuth session for {remote_name}")
                    process = session.get('process')
                    if process and process.poll() is None:
                        # Process still running, kill it
                        try:
                            process.kill()
                            process.wait(timeout=5)
                        except Exception as e:
                            logging.warning(f"Failed to kill old OAuth process: {e}")
                    del self._active_sessions[remote_name]

        # Build rclone command
        command = [
            self.rclone_path,
            'config',
            'update',
            remote_name,
            'config_refresh_token',
            'true',
        ]

        if self.rclone_config_file:
            command.extend(['--config', self.rclone_config_file])

        logging.info(f"Starting OAuth refresh for remote: {remote_name}")
        logging.debug(f"Command: {' '.join(command)}")

        try:
            # Prepare environment to prevent rclone from auto-opening browser
            import os
            env = os.environ.copy()
            # Tell rclone not to auto-open browser (it should just print the URL)
            env['BROWSER'] = '/bin/false'  # Set browser to a no-op command
            # Unset DISPLAY to make rclone think it's running headless
            # This prevents auto-opening browser even on systems with GUI
            if 'DISPLAY' in env:
                del env['DISPLAY']
            # Also unset other display-related variables
            for var in ['WAYLAND_DISPLAY', 'MIR_SOCKET', 'XDG_SESSION_TYPE']:
                if var in env:
                    del env[var]

            # Start the process
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )

            # Wait and read output to get the OAuth URL
            # rclone might take a few seconds to start the OAuth server
            auth_url = None
            local_port = None
            output_lines = []

            # Try to read output multiple times with increasing wait
            for attempt in range(5):  # Try for up to 5 seconds
                time.sleep(1.0)

                try:
                    import select
                    import sys

                    # Read available output from both stdout and stderr
                    if sys.platform != 'win32':
                        # Unix-like systems - use select to check for available data
                        for stream in [process.stdout, process.stderr]:
                            while True:
                                readable, _, _ = select.select([stream], [], [], 0.1)
                                if not readable:
                                    break
                                line = stream.readline()
                                if not line:
                                    break
                                output_lines.append(line)
                                logging.debug(f"rclone output: {line.strip()}")
                                # Check if we found the OAuth URL
                                if 'http://127.0.0.1:' in line or 'http://localhost:' in line:
                                    break
                    else:
                        # Windows - try to read what's available
                        for stream in [process.stdout, process.stderr]:
                            for _ in range(20):  # Try to read up to 20 lines
                                line = stream.readline()
                                if line:
                                    output_lines.append(line)
                                    logging.debug(f"rclone output: {line.strip()}")
                                    if 'http://127.0.0.1:' in line or 'http://localhost:' in line:
                                        break
                                else:
                                    break

                    # Check if we found the OAuth URL
                    for line in output_lines:
                        if 'http://127.0.0.1:' in line or 'http://localhost:' in line:
                            # Found it! Break out of retry loop
                            break
                    else:
                        # Not found yet, continue to next attempt
                        continue

                    # If we get here, we found the URL
                    break

                except Exception as e:
                    logging.warning(f"Error reading rclone output (attempt {attempt+1}): {e}")
                    continue

            # Log all output for debugging
            logging.info(f"rclone output ({len(output_lines)} lines):")
            for line in output_lines:
                logging.info(f"  {line.strip()}")

            # Parse output to extract OAuth URL and local port
            for line in output_lines:
                # Look for the OAuth URL in the format:
                # "If your browser doesn't open automatically go to the following link: http://127.0.0.1:PORT/auth?state=..."
                if 'http://127.0.0.1:' in line or 'http://localhost:' in line:
                    # Extract the URL
                    match = re.search(r'(http://(?:127\.0\.0\.1|localhost):(\d+)/[^\s]+)', line)
                    if match:
                        local_url = match.group(1)
                        local_port = int(match.group(2))

                        # Extract the path and query from the local URL
                        # e.g., http://127.0.0.1:53682/auth?state=xxx -> /auth?state=xxx
                        path_match = re.search(r'http://[^/]+(/.+)', local_url)
                        if path_match:
                            local_path = path_match.group(1)
                            # Construct the proxied auth URL using the callback_url
                            # callback_url should be something like http://host:port/api/oauth/callback
                            auth_url = f"{callback_url}/{remote_name}{local_path}"
                        break

            if not auth_url or not local_port:
                # Kill the process
                process.kill()
                process.wait(timeout=5)
                return False, "Failed to extract OAuth URL from rclone output", None

            # Give rclone a brief moment to fully start its HTTP server
            # Don't test the server (might interfere with OAuth state)
            # The retry logic in proxy_callback will handle any remaining delays
            logging.info(f"Waiting 0.5 seconds for rclone HTTP server to initialize on port {local_port}...")
            time.sleep(0.5)

            # Store session info
            with self._lock:
                self._active_sessions[remote_name] = {
                    'process': process,
                    'auth_url': auth_url,
                    'local_port': local_port,
                    'status': 'pending',
                    'start_time': time.time(),
                }

            logging.info(f"OAuth refresh started for {remote_name}, local port: {local_port}")
            logging.info(f"Auth URL: {auth_url}")

            return True, 'OAuth refresh started', auth_url

        except Exception as e:
            logging.error(f"Failed to start OAuth refresh: {e}")
            return False, f"Failed to start OAuth refresh: {str(e)}", None

    def proxy_callback(self, remote_name: str, callback_path: str, callback_base_url: str) -> Dict:
        """
        Proxy an OAuth callback to the local rclone server

        This method handles the OAuth flow by proxying requests to rclone's temporary server.
        When rclone returns a redirect to the OAuth provider, we intercept it and rewrite
        the redirect_uri parameter to point back to our Motus server instead of localhost.

        Args:
            remote_name: Name of the remote
            callback_path: The callback path with query parameters (e.g., /auth?state=xxx&code=yyy)
            callback_base_url: The base URL for OAuth callbacks (e.g., http://motus:8889/api/oauth/callback)

        Returns:
            Dict with keys:
            - type: 'redirect' | 'response'
            - For 'redirect': 'url' with the redirect URL
            - For 'response': 'status' and 'message'
        """
        with self._lock:
            if remote_name not in self._active_sessions:
                return {'type': 'response', 'status': 404, 'message': "No active OAuth session for this remote"}

            session = self._active_sessions[remote_name]
            local_port = session.get('local_port')

            if not local_port:
                return {'type': 'response', 'status': 500, 'message': "OAuth session missing port information"}

        # Make request to local rclone server with retries
        # rclone may take a moment to start its HTTP server even after outputting the URL
        try:
            import requests
            from requests.exceptions import ConnectionError, Timeout
            from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

            local_url = f"http://127.0.0.1:{local_port}{callback_path}"
            logging.info(f"Proxying OAuth callback to: {local_url}")

            # Retry with exponential backoff if rclone server isn't ready yet
            # For the initial request, rclone needs time to start the HTTP server
            max_retries = 10
            retry_delays = [0.5, 0.5, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0, 4.0, 5.0]  # Total: ~22 seconds max

            response = None
            last_error = None

            for attempt in range(max_retries):
                try:
                    response = requests.get(local_url, timeout=10, allow_redirects=False)
                    # Success! Break out of retry loop
                    break
                except (ConnectionError, Timeout) as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        delay = retry_delays[attempt]
                        logging.debug(f"rclone server not ready yet (attempt {attempt+1}/{max_retries}), retrying in {delay}s...")
                        time.sleep(delay)
                    else:
                        # Last attempt failed
                        logging.error(f"Failed to connect to rclone server after {max_retries} attempts: {e}")
                        raise

            if response is None:
                # Should not happen, but just in case
                raise last_error or Exception("Failed to get response from rclone server")

            # Check if this is a redirect to the OAuth provider
            if response.status_code in (301, 302, 303, 307, 308):
                redirect_url = response.headers.get('Location', '')
                logging.info(f"rclone returned redirect to: {redirect_url}")

                # Parse the redirect URL to rewrite redirect_uri
                parsed = urlparse(redirect_url)
                query_params = parse_qs(parsed.query)

                # Check if redirect_uri parameter exists
                if 'redirect_uri' in query_params:
                    original_redirect = query_params['redirect_uri'][0]
                    logging.info(f"Original redirect_uri: {original_redirect}")

                    # Extract components from the original redirect_uri
                    # e.g., http://localhost:53682/ -> we want to keep 'localhost' and '/'
                    original_parsed = urlparse(original_redirect)
                    original_hostname = original_parsed.hostname  # 'localhost' or '127.0.0.1'
                    original_path = original_parsed.path or '/'  # Usually just '/'

                    logging.debug(f"Original hostname: {original_hostname}, path: {original_path}")

                    # Parse our callback_base_url to get the port
                    # e.g., http://127.0.0.1:8889/api/oauth/callback
                    callback_parsed = urlparse(callback_base_url)
                    callback_port = callback_parsed.port

                    # Construct new redirect_uri preserving ONLY hostname and path from original
                    # Change ONLY the port to Motus port
                    # This keeps Azure happy (it expects http://localhost:*/)
                    new_redirect_uri = f"{callback_parsed.scheme}://{original_hostname}:{callback_port}{original_path}"

                    # Add the remote name as a query parameter so we can route it correctly
                    # e.g., http://localhost:8889/?remote=onedrive&state=xxx
                    if '?' in new_redirect_uri:
                        new_redirect_uri += f"&_motus_remote={remote_name}"
                    else:
                        new_redirect_uri += f"?_motus_remote={remote_name}"

                    query_params['redirect_uri'] = [new_redirect_uri]

                    logging.info(f"Rewritten redirect_uri: {new_redirect_uri}")

                    # Rebuild the query string
                    new_query = urlencode(query_params, doseq=True)

                    # Rebuild the full URL
                    rewritten_url = urlunparse((
                        parsed.scheme,
                        parsed.netloc,
                        parsed.path,
                        parsed.params,
                        new_query,
                        parsed.fragment
                    ))

                    logging.info(f"Rewritten redirect URL: {rewritten_url}")

                    return {
                        'type': 'redirect',
                        'url': rewritten_url,
                    }
                else:
                    # No redirect_uri to rewrite, just pass through the redirect
                    logging.warning(f"Redirect has no redirect_uri parameter: {redirect_url}")
                    return {
                        'type': 'redirect',
                        'url': redirect_url,
                    }

            # Not a redirect - this is the final callback with the authorization code
            # Wait a bit for rclone to finish processing
            time.sleep(1.0)

            # Check if process has finished
            with self._lock:
                if remote_name in self._active_sessions:
                    process = self._active_sessions[remote_name]['process']
                    return_code = process.poll()

                    if return_code is not None:
                        # Process finished
                        stdout, stderr = process.communicate(timeout=5)
                        self._active_sessions[remote_name]['status'] = 'completed' if return_code == 0 else 'failed'
                        self._active_sessions[remote_name]['return_code'] = return_code
                        self._active_sessions[remote_name]['stdout'] = stdout
                        self._active_sessions[remote_name]['stderr'] = stderr

                        logging.info(f"OAuth refresh completed with code {return_code}")

                        if return_code == 0:
                            return {'type': 'response', 'status': 200, 'message': "OAuth token refresh successful"}
                        else:
                            return {'type': 'response', 'status': 500, 'message': f"OAuth token refresh failed: {stderr}"}
                    else:
                        # Still running, might need more time
                        return {'type': 'response', 'status': 200, 'message': "OAuth callback received, waiting for completion"}

            return {'type': 'response', 'status': 200, 'message': "OAuth callback processed"}

        except Exception as e:
            logging.error(f"Failed to proxy OAuth callback: {e}")
            return {'type': 'response', 'status': 500, 'message': f"Failed to proxy OAuth callback: {str(e)}"}

    def get_session_status(self, remote_name: str) -> Optional[Dict]:
        """
        Get the status of an OAuth session

        Args:
            remote_name: Name of the remote

        Returns:
            Session status dict or None if no session exists
        """
        with self._lock:
            if remote_name not in self._active_sessions:
                return None

            session = self._active_sessions[remote_name].copy()
            # Remove process object from returned dict
            session.pop('process', None)
            return session

    def cleanup_session(self, remote_name: str):
        """
        Clean up an OAuth session

        Args:
            remote_name: Name of the remote
        """
        with self._lock:
            if remote_name in self._active_sessions:
                session = self._active_sessions[remote_name]
                process = session.get('process')

                if process and process.poll() is None:
                    # Process still running, kill it
                    try:
                        process.kill()
                        process.wait(timeout=5)
                    except Exception as e:
                        logging.warning(f"Failed to kill OAuth process: {e}")

                del self._active_sessions[remote_name]
                logging.info(f"Cleaned up OAuth session for {remote_name}")

    def cleanup_old_sessions(self, max_age_seconds: int = 600):
        """
        Clean up OAuth sessions older than max_age_seconds

        Args:
            max_age_seconds: Maximum age of sessions to keep (default: 10 minutes)
        """
        current_time = time.time()

        with self._lock:
            remotes_to_cleanup = []

            for remote_name, session in self._active_sessions.items():
                age = current_time - session.get('start_time', 0)
                if age > max_age_seconds:
                    remotes_to_cleanup.append(remote_name)

            for remote_name in remotes_to_cleanup:
                logging.info(f"Cleaning up old OAuth session for {remote_name}")
                self.cleanup_session(remote_name)

    def start_oauth_refresh_interactive(self, remote_name: str, remote_type: str) -> Dict:
        """
        Start OAuth token refresh using rclone's non-interactive state machine

        This uses the --non-interactive mode which works as a question/answer flow.
        The user runs `rclone authorize` on their laptop and pastes the result.

        Args:
            remote_name: Name of the remote to refresh
            remote_type: Type of the remote (e.g., 'onedrive', 'drive')

        Returns:
            Dict with:
            - status: 'needs_token' | 'error' | 'complete'
            - authorize_command: Command for user to run (if needs_token)
            - session_id: ID to use when submitting token (if needs_token)
            - message: Error or success message
            - state: Current state (for continuing flow)
        """
        from .config_state_machine import RcloneConfigStateMachine

        # Clean up any old session
        with self._lock:
            if remote_name in self._active_sessions:
                old_session = self._active_sessions[remote_name]
                if old_session.get('status') == 'pending':
                    # Already in progress
                    return {
                        'status': 'needs_token',
                        'authorize_command': old_session.get('authorize_command'),
                        'session_id': remote_name,
                        'message': 'OAuth refresh already in progress',
                        'state': old_session.get('current_state'),
                    }
                # Clean up old session
                del self._active_sessions[remote_name]

        # Create state machine
        state_machine = RcloneConfigStateMachine(self.rclone_path, self.rclone_config_file)

        # Start the flow
        success, response, error = state_machine.start(remote_name, config_refresh_token='true')

        if not success:
            return {
                'status': 'error',
                'message': f'Failed to start OAuth refresh: {error}',
            }

        # Process the state machine response
        return self._process_state_machine_response(
            remote_name, remote_type, state_machine, response
        )

    def continue_oauth_refresh(self, remote_name: str, token: str) -> Dict:
        """
        Continue OAuth refresh after user has pasted the token

        Args:
            remote_name: Name of the remote
            token: The token string from `rclone authorize`

        Returns:
            Dict with status and message
        """
        from .config_state_machine import RcloneConfigStateMachine

        with self._lock:
            if remote_name not in self._active_sessions:
                return {
                    'status': 'error',
                    'message': 'No active OAuth session found',
                }

            session = self._active_sessions[remote_name]
            current_state = session.get('current_state')
            remote_type = session.get('remote_type')

        # Create state machine
        state_machine = RcloneConfigStateMachine(self.rclone_path, self.rclone_config_file)

        # Continue with the token
        success, response, error = state_machine.continue_flow(remote_name, current_state, token)

        if not success:
            with self._lock:
                if remote_name in self._active_sessions:
                    del self._active_sessions[remote_name]
            return {
                'status': 'error',
                'message': f'Failed to continue OAuth refresh: {error}',
            }

        # Process the response
        return self._process_state_machine_response(
            remote_name, remote_type, state_machine, response
        )

    def _process_state_machine_response(
        self, remote_name: str, remote_type: str, state_machine, response: Dict
    ) -> Dict:
        """
        Process a response from the rclone state machine

        Args:
            remote_name: Name of the remote
            remote_type: Type of remote (e.g., 'onedrive')
            state_machine: The RcloneConfigStateMachine instance
            response: The parsed JSON response from rclone

        Returns:
            Dict with status, message, and any required actions
        """
        # Check if complete
        if state_machine.is_complete(response):
            with self._lock:
                if remote_name in self._active_sessions:
                    del self._active_sessions[remote_name]
            return {
                'status': 'complete',
                'message': 'OAuth token refresh successful',
            }

        # Get current state
        current_state = response.get('State', '')
        option = response.get('Option', {})

        # Handle special states
        if current_state == '*oauth-islocal,choose_type,,':
            # Answer "false" (not local) and continue automatically
            logging.info("Answering oauth-islocal=false (remote machine)")
            success, next_response, error = state_machine.continue_flow(
                remote_name, current_state, 'false'
            )

            if not success:
                return {
                    'status': 'error',
                    'message': f'Failed to continue: {error}',
                }

            # Recursively process next response
            return self._process_state_machine_response(
                remote_name, remote_type, state_machine, next_response
            )

        elif current_state == '*oauth-authorize,choose_type,,':
            # Extract the authorize command from the help text
            help_text = option.get('Help', '')
            authorize_command = None

            # Parse the command from help text
            # Example: "rclone authorize \"onedrive\" \"BASE64_STRING\""
            import re
            match = re.search(r'rclone authorize "([^"]+)" "([^"]+)"', help_text)
            if match:
                provider = match.group(1)
                config_blob = match.group(2)
                authorize_command = f'rclone authorize "{provider}" "{config_blob}"'
            else:
                return {
                    'status': 'error',
                    'message': 'Failed to extract authorize command from rclone output',
                }

            # Store session info
            with self._lock:
                self._active_sessions[remote_name] = {
                    'status': 'pending',
                    'current_state': current_state,
                    'remote_type': remote_type,
                    'authorize_command': authorize_command,
                    'start_time': time.time(),
                }

            return {
                'status': 'needs_token',
                'authorize_command': authorize_command,
                'session_id': remote_name,
                'message': 'Please run the command on your laptop and paste the token',
                'state': current_state,
            }

        else:
            # For other states, use default answer and continue automatically
            default_answer = state_machine.get_default_answer(response)

            if default_answer is None:
                return {
                    'status': 'error',
                    'message': f'No default answer for state: {current_state}',
                }

            logging.info(f"Auto-answering state '{current_state}' with default: {default_answer}")
            success, next_response, error = state_machine.continue_flow(
                remote_name, current_state, default_answer
            )

            if not success:
                return {
                    'status': 'error',
                    'message': f'Failed to continue: {error}',
                }

            # Recursively process next response
            return self._process_state_machine_response(
                remote_name, remote_type, state_machine, next_response
            )

