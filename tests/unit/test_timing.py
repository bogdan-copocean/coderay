"""Tests for indexer.core.timing."""

import time

from indexer.core.timing import timed, timed_phase


class TestTimed:
    def test_decorator_returns_result(self):
        @timed("test_op")
        def add(a, b):
            return a + b

        assert add(1, 2) == 3


class TestTimedPhase:
    def test_context_manager(self):
        with timed_phase("test_phase"):
            time.sleep(0.01)
