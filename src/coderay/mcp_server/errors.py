_DEFAULT_MSG = (
    "Index not built. Ask the user to run 'coderay build' in their terminal, "
    "then retry."
)


class IndexNotBuiltError(Exception):
    """Raised when a tool requires a coderay index that has not been built."""

    def __init__(self, message: str = _DEFAULT_MSG) -> None:
        super().__init__(message)
