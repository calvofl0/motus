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
        if current_state.startswith('*oauth-islocal,'):
            # Answer "false" (not local) and continue automatically
            # This matches any oauth-islocal state regardless of the second field
            # (choose_type, teamdrive, or other remote-specific values)
            logging.info(f"Answering oauth-islocal=false for state: {current_state}")
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

        elif current_state.startswith('*oauth-authorize,'):
            # Extract the authorize command from the help text
            # This matches any oauth-authorize state regardless of the second field
            # (choose_type, teamdrive, or other remote-specific values)
            help_text = option.get('Help', '')
            authorize_command = None

            # Parse the command from help text
            # Example 1: "rclone authorize \"onedrive\""
            # Example 2: "rclone authorize \"onedrive\" \"BASE64_STRING\""
            import re
            # Try matching with both arguments first
            match = re.search(r'rclone authorize "([^"]+)" "([^"]+)"', help_text)
            if match:
                provider = match.group(1)
                config_blob = match.group(2)
                authorize_command = f'rclone authorize "{provider}" "{config_blob}"'
            else:
                # Try matching with just provider (single argument)
                match = re.search(r'rclone authorize "([^"]+)"', help_text)
                if match:
                    provider = match.group(1)
                    authorize_command = f'rclone authorize "{provider}"'
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

