"""
Custom remote creation using rclone's state machine
Handles interactive remote creation with step-by-step prompting
"""
import json
import logging
import subprocess
from typing import Dict, List, Tuple, Optional, Any

from .config_state_machine import RcloneConfigStateMachine


class CustomRemoteCreationManager:
    """
    Manages custom remote creation using rclone's --non-interactive state machine
    Similar to OAuth refresh but for creating new remotes from scratch
    """

    def __init__(self, rclone_path: str, config_file: str):
        """
        Initialize custom remote creation manager

        Args:
            rclone_path: Path to rclone executable
            config_file: Path to rclone config file
        """
        self.rclone_path = rclone_path
        self.config_file = config_file
        self.sessions = {}  # Store active creation sessions

    def get_providers(self) -> List[Dict[str, str]]:
        """
        Get list of available remote providers from rclone

        Returns:
            List of provider dicts with 'name' and 'description' keys
            Example: [{'name': 's3', 'description': 'Amazon S3'}, ...]
        """
        try:
            command = [
                self.rclone_path,
                'config',
                'providers',
            ]

            logging.debug(f"Getting providers: {' '.join(command)}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                logging.error(f"Failed to get providers: {error_msg}")
                return []

            # Parse JSON output - rclone returns array of provider objects
            # Example:
            # [
            #   {
            #     "Name": "s3",
            #     "Description": "Amazon S3 Compliant Storage Providers",
            #     "Prefix": "s3",
            #     "Options": [...]
            #   },
            #   ...
            # ]
            try:
                providers_data = json.loads(result.stdout)
                providers = []
                for provider in providers_data:
                    providers.append({
                        'name': provider.get('Name', ''),
                        'description': provider.get('Description', '')
                    })

                logging.info(f"Found {len(providers)} providers")
                return providers

            except json.JSONDecodeError as e:
                logging.error(f"Failed to parse providers JSON: {e}")
                return []

        except subprocess.TimeoutExpired:
            logging.error("Get providers command timed out")
            return []
        except Exception as e:
            logging.error(f"Failed to get providers: {e}")
            return []

    def start_creation(self, remote_name: str, remote_type: str) -> Dict[str, Any]:
        """
        Start creating a new remote with given name and type

        Args:
            remote_name: Name for the new remote
            remote_type: Type of remote (e.g., 's3', 'drive', 'dropbox')

        Returns:
            Dict with status and next question (if any)
            {
                'status': 'needs_input' | 'complete' | 'error',
                'question': {...},  // if needs_input
                'session_id': 'remote_name',  // if needs_input
                'message': 'Error or status message'
            }
        """
        try:
            logging.info(f"Starting creation of remote '{remote_name}' type '{remote_type}'")

            # Run rclone config create --non-interactive
            command = [
                self.rclone_path,
                'config',
                'create',
                remote_name,
                remote_type,
                '--non-interactive',
                '--config', self.config_file,
            ]

            logging.debug(f"Command: {' '.join(command)}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )

            # Parse JSON response
            try:
                response = json.loads(result.stdout)
            except json.JSONDecodeError:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Failed to parse rclone response"
                logging.error(f"JSON decode error: {error_msg}")
                return {
                    'status': 'error',
                    'message': error_msg
                }

            # Check for errors
            if response.get('Error'):
                logging.error(f"rclone error: {response['Error']}")
                return {
                    'status': 'error',
                    'message': response['Error']
                }

            # Initialize state machine for this session (use 'create' operation)
            state_machine = RcloneConfigStateMachine(self.rclone_path, self.config_file, operation='create')
            self.sessions[remote_name] = {
                'remote_name': remote_name,
                'remote_type': remote_type,
                'state_machine': state_machine,
                'current_response': response
            }

            # Process the response
            return self._process_state_machine_response(remote_name, response)

        except subprocess.TimeoutExpired:
            logging.error("Create command timed out")
            return {
                'status': 'error',
                'message': 'Command timed out'
            }
        except Exception as e:
            logging.error(f"Failed to start creation: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def continue_creation(self, remote_name: str, answer: str) -> Dict[str, Any]:
        """
        Continue the creation flow with an answer to the current question

        Args:
            remote_name: Session ID (remote name)
            answer: User's answer to the current question

        Returns:
            Dict with status and next question (if any)
        """
        try:
            # Get session
            session = self.sessions.get(remote_name)
            if not session:
                return {
                    'status': 'error',
                    'message': f'No active session found for {remote_name}'
                }

            state_machine = session['state_machine']
            current_response = session['current_response']
            current_state = current_response.get('State', '')

            logging.info(f"Continuing creation for '{remote_name}' with answer: {answer}")

            # Continue the flow
            success, next_response, error = state_machine.continue_flow(
                remote_name, current_state, answer
            )

            if not success:
                return {
                    'status': 'error',
                    'message': error or 'Failed to continue creation flow'
                }

            # Update session with new response
            session['current_response'] = next_response

            # Process the response
            return self._process_state_machine_response(remote_name, next_response)

        except Exception as e:
            logging.error(f"Failed to continue creation: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def _process_state_machine_response(self, remote_name: str, response: Dict) -> Dict[str, Any]:
        """
        Process a state machine response and determine next action

        Args:
            remote_name: Session ID
            response: Response dict from rclone

        Returns:
            Dict with status and next question or completion
        """
        # Check if complete (empty State means done)
        state = response.get('State', '')
        if not state:
            # Creation complete
            logging.info(f"Remote '{remote_name}' created successfully")

            # Clean up session
            if remote_name in self.sessions:
                del self.sessions[remote_name]

            return {
                'status': 'complete',
                'message': f"Remote '{remote_name}' created successfully"
            }

        # Check for auto-answer states
        # Auto-answer "*oauth-islocal" with "false" (use external OAuth, not local browser)
        if '*oauth-islocal' in state:
            logging.info(f"Auto-answering *oauth-islocal with 'false'")
            return self.continue_creation(remote_name, 'false')

        # Get the option (question) to present to user
        option = response.get('Option', {})
        if not option:
            return {
                'status': 'error',
                'message': 'No option provided by rclone'
            }

        # Extract question details
        question = {
            'name': option.get('Name', ''),
            'help': option.get('Help', ''),
            'required': option.get('Required', False),
            'type': option.get('Type', 'string'),  # string, int, bool, etc.
            'is_password': option.get('IsPassword', False),
            'default': option.get('Default', ''),
            'examples': option.get('Examples', []),
        }

        return {
            'status': 'needs_input',
            'session_id': remote_name,
            'question': question,
            'message': 'Please provide input for the next field'
        }

    def cancel_creation(self, remote_name: str):
        """
        Cancel an active creation session

        Args:
            remote_name: Session ID to cancel
        """
        if remote_name in self.sessions:
            del self.sessions[remote_name]
            logging.info(f"Cancelled creation session for '{remote_name}'")
