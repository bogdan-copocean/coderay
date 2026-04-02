"""Tests for indexer.core.timing."""

import logging
import time

from coderay.core.timing import timed, timed_phase


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

    def test_elapsed_is_set(self):
        """Assert elapsed is populated after context exit."""
        with timed_phase("elapsed_test", log=False) as tp:
            time.sleep(0.02)
        assert tp.elapsed >= 0.02

    def test_log_false_skips_logging(self, caplog):
        """Assert log=False does not emit INFO for the phase."""
        with caplog.at_level(logging.INFO):
            with timed_phase("no_log_phase", log=False):
                time.sleep(0.01)
        assert "no_log_phase" not in caplog.text
