"""Module with __all__ for wildcard import tests."""

__all__ = ["join", "split"]


def join(a: str, b: str) -> str:
    """Join two strings."""
    return a + b


def split(s: str) -> list[str]:
    """Split a string."""
    return s.split()
