class ProviderError(RuntimeError):
    """Safe, user-facing upstream error; never include URLs, keys or response bodies."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


class OperationConflict(RuntimeError):
    pass
