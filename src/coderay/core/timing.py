from __future__ import annotations

import functools
import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., object])


def timed(phase: str) -> Callable[[F], F]:
    """Decorator that logs execution time at DEBUG level."""

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
    """Context manager that measures block execution time and optionally logs it."""

    def __init__(self, phase: str, *, log: bool = True) -> None:
        self.phase = phase
        self.log = log
        self.t0: float = 0.0
        self.elapsed: float = 0.0

    def __enter__(self) -> timed_phase:
        self.t0 = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.elapsed = time.perf_counter() - self.t0
        if self.log:
            logger.info("%s: %.3fs", self.phase, self.elapsed)
