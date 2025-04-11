class CortexAgentError(Exception):
    """
    Base exception class for all Cortex Agent-related errors.
    """
    pass

class CortexAgentAPIError(CortexAgentError):
    """
    Exception raised when the Cortex Agent REST API returns an error.

    Attributes:
        error_code (int or str): The error code returned by the API.
        message (str): A descriptive error message.
        request_id (str): The unique identifier of the request that caused the error.
    """
    def __init__(self, error_code, message, request_id):
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.request_id = request_id

    def __str__(self):
        return (
            f"{self.__class__.__name__}: Snowflake Cortex Agent REST API returned an error. "
            f"Error Code: {self.error_code} "
            f'Error Message: "{self.message}" '
            f"Request-ID: {self.request_id}"
        )
    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"error_code={self.error_code}, "
            f"message={self.message!r}, "
            f"request_id={self.request_id!r})"
        )
