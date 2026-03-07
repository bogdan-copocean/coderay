"""
Timing utilities: decorator for debug-only phase timing.

Use @timed("phase_name") to log elapsed seconds at DEBUG level.
Useful for measuring discover, read, chunk, embed, store separately.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., object])


def timed(phase: str) -> Callable[[F], F]:
    """
    Decorator that times the wrapped function and logs at DEBUG.

    Log message: "phase_name: X.XXs"
    Only visible when log level is DEBUG (e.g. CLI -v/--verbose).
    """

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: object, **kwargs: object) -> object:
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - t0
                logger.debug("%s: %.3fs", phase, elapsed)

        return wrapper  # type: ignore[return-value]

    return decorator


class timed_phase:
    """
    Context manager for timing a block; logs at DEBUG on exit.

    Use::
        with timed_phase("read"):
            ...
    """

    def __init__(self, phase: str) -> None:
        self.phase = phase
        self.t0: float = 0.0

    def __enter__(self) -> timed_phase:
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        elapsed = time.perf_counter() - self.t0
        logger.info("%s: %.3fs", self.phase, elapsed)
