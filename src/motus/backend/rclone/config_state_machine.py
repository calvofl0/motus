"""
Rclone config state machine for handling interactive configuration flows

This module provides a generic way to handle rclone's --non-interactive mode
which works as a state machine with questions and answers.
"""
import json
import logging
import subprocess
from typing import Dict, Optional, Tuple, Any


class RcloneConfigStateMachine:
    """
    Handles rclone config update flows using the --non-interactive state machine
    """

    def __init__(self, rclone_path: str, rclone_config_file: str, operation: str = 'update', remote_type: str = None):
        """
        Initialize the state machine

        Args:
            rclone_path: Path to rclone executable
            rclone_config_file: Path to rclone config file
            operation: Either 'update' or 'create' (default: 'update')
            remote_type: Remote type (required for 'create' operation, e.g., 's3', 'drive')
        """
        self.rclone_path = rclone_path
        self.rclone_config_file = rclone_config_file
        self.operation = operation  # 'update' or 'create'
        self.remote_type = remote_type  # Only needed for 'create' operation

    def start(self, remote_name: str, **kwargs) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Start a config update flow

        Args:
            remote_name: Name of the remote to update
            **kwargs: Config parameters (e.g., config_refresh_token='true')

        Returns:
            Tuple of (success, response_dict, error_message)
            - success: True if command executed successfully
            - response_dict: Parsed JSON response from rclone
            - error_message: Error message if success is False
        """
        # Build command with config parameters
        command = [
            self.rclone_path,
            'config',
            self.operation,  # Use 'update' or 'create' based on initialization
            '--non-interactive',
            remote_name,
        ]

        # Add config parameters as key=value
        for key, value in kwargs.items():
            command.append(f'{key}={value}')

        if self.rclone_config_file:
            command.extend(['--config', self.rclone_config_file])

        logging.info(f"Starting rclone config state machine: {' '.join(command)}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode != 0:
                logging.error(f"rclone config start failed: {result.stderr}")
                return False, {}, f"rclone command failed: {result.stderr}"

            # Parse JSON response
            response = json.loads(result.stdout)
            logging.debug(f"rclone response: {json.dumps(response, indent=2)}")

            return True, response, None

        except subprocess.TimeoutExpired:
            return False, {}, "rclone command timed out"
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse rclone JSON output: {e}")
            logging.error(f"Output was: {result.stdout}")
            return False, {}, f"Failed to parse rclone output: {e}"
        except Exception as e:
            logging.error(f"Failed to start rclone config: {e}")
            return False, {}, str(e)

    def continue_flow(
        self, remote_name: str, state: str, result: str
    ) -> Tuple[bool, Dict[str, Any], Optional[str]]:
        """
        Continue the config flow with an answer to the current question

        Args:
            remote_name: Name of the remote
            state: The State value from previous response
            result: The answer to provide

        Returns:
            Tuple of (success, response_dict, error_message)
        """
        command = [
            self.rclone_path,
            'config',
            self.operation,  # Use 'update' or 'create' based on initialization
            remote_name,
        ]

        # For 'create' operation, we need to include the remote type
        if self.operation == 'create' and self.remote_type:
            command.append(self.remote_type)

        command.extend([
            '--continue',
            '--state',
            state,
            '--result',
            result,
        ])

        if self.rclone_config_file:
            command.extend(['--config', self.rclone_config_file])

        logging.info(f"Continuing rclone config: state={state}, result={result[:50]}...")

        try:
            process_result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if process_result.returncode != 0:
                logging.error(f"rclone config continue failed: {process_result.stderr}")
                return False, {}, f"rclone command failed: {process_result.stderr}"

            # Parse JSON response
            response = json.loads(process_result.stdout)
            logging.debug(f"rclone response: {json.dumps(response, indent=2)}")

            # Check for errors in response
            if response.get('Error'):
                return False, response, response['Error']

            return True, response, None

        except subprocess.TimeoutExpired:
            return False, {}, "rclone command timed out"
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse rclone JSON output: {e}")
            logging.error(f"Output was: {process_result.stdout}")
            return False, {}, f"Failed to parse rclone output: {e}"
        except Exception as e:
            logging.error(f"Failed to continue rclone config: {e}")
            return False, {}, str(e)

    def get_default_answer(self, response: Dict[str, Any]) -> Optional[str]:
        """
        Extract the default answer from a response

        Args:
            response: The parsed JSON response from rclone

        Returns:
            The default value as a string, or None if no default
        """
        option = response.get('Option')
        if not option:
            return None

        # Get the default value
        default = option.get('Default')
        if default is not None:
            # Convert to string
            if isinstance(default, bool):
                return 'true' if default else 'false'
            return str(default)

        return None

    def is_complete(self, response: Dict[str, Any]) -> bool:
        """
        Check if the config flow is complete

        Args:
            response: The parsed JSON response from rclone

        Returns:
            True if State is empty (flow complete), False otherwise
        """
        state = response.get('State', '')
        return state == ''
