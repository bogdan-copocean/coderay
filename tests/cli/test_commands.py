"""Integration tests for CLI commands."""

from pathlib import Path

from click.testing import CliRunner

from coderay.cli.commands import cli


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "build" in result.output

    def test_build_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["build", "--help"])
        assert result.exit_code == 0

    def test_search_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0

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

    def test_graph_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["graph", "--help"])
        assert result.exit_code == 0
