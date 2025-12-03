"""
Custom exceptions for rclone operations
"""


class RcloneException(Exception):
    """Base exception for rclone operations"""
    pass


class RcloneNotFoundError(RcloneException):
    """Raised when rclone executable is not found"""
    pass


class RcloneConnectionError(RcloneException):
    """Raised when rclone fails to connect to a remote"""
    pass
