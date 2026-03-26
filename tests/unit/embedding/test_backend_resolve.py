"""Tests for embedder backend auto-detection."""

from unittest.mock import MagicMock, patch

import pytest

from coderay.embedding.backend_resolve import resolved_embedder_backend


def test_explicit_fastembed():
    assert resolved_embedder_backend("fastembed") == "fastembed"
    assert resolved_embedder_backend("FASTEMBED") == "fastembed"


def test_explicit_mlx():
    assert resolved_embedder_backend("mlx") == "mlx"


def test_auto_defaults_to_fastembed_on_non_darwin():
    with patch("coderay.embedding.backend_resolve.sys.platform", "linux"):
        assert resolved_embedder_backend("auto") == "fastembed"


def test_auto_defaults_to_fastembed_on_intel_mac():
    with patch("coderay.embedding.backend_resolve.sys.platform", "darwin"):
        with patch(
            "coderay.embedding.backend_resolve.platform.machine",
            return_value="x86_64",
        ):
            assert resolved_embedder_backend("auto") == "fastembed"


def test_auto_mlx_when_apple_silicon_and_mlx_installed():
    with patch("coderay.embedding.backend_resolve.sys.platform", "darwin"):
        with patch(
            "coderay.embedding.backend_resolve.platform.machine",
            return_value="arm64",
        ):
            with patch(
                "coderay.embedding.backend_resolve.importlib.util.find_spec",
                return_value=MagicMock(),
            ):
                assert resolved_embedder_backend("auto") == "mlx"


def test_auto_fastembed_when_mlx_not_installed():
    with patch("coderay.embedding.backend_resolve.sys.platform", "darwin"):
        with patch(
            "coderay.embedding.backend_resolve.platform.machine",
            return_value="arm64",
        ):
            with patch(
                "coderay.embedding.backend_resolve.importlib.util.find_spec",
                return_value=None,
            ):
                assert resolved_embedder_backend("auto") == "fastembed"


def test_unknown_backend_raises():
    with pytest.raises(ValueError, match="Unknown embedder.backend"):
        resolved_embedder_backend("cuda")
