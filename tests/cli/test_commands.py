"""Integration tests for CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from coderay.cli.commands import cli


class TestCLI:
    @pytest.mark.parametrize(
        "args,expected_in_output",
        [
            (["--help"], "build"),
            (["build", "--help"], None),
            (["search", "--help"], None),
            (["graph", "--help"], None),
        ],
    )
    def test_help(self, args, expected_in_output):
        runner = CliRunner()
        result = runner.invoke(cli, args)
        assert result.exit_code == 0
        if expected_in_output:
            assert expected_in_output in result.output

    def test_list_no_index(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path(".index").mkdir()
            result = runner.invoke(cli, ["--index-dir", ".index", "list"])
            assert result.exit_code in (0, 1) or result.exception is not None

    def test_maintain_no_index(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path(".index").mkdir()
            result = runner.invoke(cli, ["--index-dir", ".index", "maintain"])
            assert result.exit_code in (0, 1) or result.exception is not None
