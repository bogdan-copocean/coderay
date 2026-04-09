"""Tests for graph target string helpers."""

from __future__ import annotations

import pytest

from coderay.graph.refs import (
    FILE_QUAL_SEP,
    infer_call_target_kind,
    infer_import_target_kind,
    infer_inherits_target_kind,
    join_file_qual,
    split_file_qual,
    target_starts_with_known_file,
)


class TestSplitAndJoinFileQual:
    """split_file_qual / join_file_qual behavior."""

    @pytest.mark.parametrize(
        "s,expected",
        [
            ("a.py::Foo.bar", ("a.py", "Foo.bar")),
            ("x::y", ("x", "y")),
            ("path/to/m.py::C", ("path/to/m.py", "C")),
        ],
    )
    def test_split_ok(self, s: str, expected: tuple[str, str]) -> None:
        """Split at first separator; remainder may contain dots."""
        assert split_file_qual(s) == expected

    @pytest.mark.parametrize(
        "s",
        [
            "no_separator",
            "",
            "::",
            "only::",
            "::tail",
        ],
    )
    def test_split_none(self, s: str) -> None:
        """Return None when separator missing or side empty."""
        assert split_file_qual(s) is None

    def test_join_round_trip(self) -> None:
        """join_file_qual inverts split for valid pairs."""
        fp, tail = "src/a.py", "Outer.Inner"
        joined = join_file_qual(fp, tail)
        assert FILE_QUAL_SEP in joined
        assert split_file_qual(joined) == (fp, tail)


class TestTargetStartsWithKnownFile:
    """target_starts_with_known_file."""

    @pytest.mark.parametrize(
        "target,known,expected",
        [
            ("pkg/a.py", {"pkg/a.py"}, True),
            ("pkg/a.py::Foo", {"pkg/a.py"}, True),
            ("other.py::Foo", {"pkg/a.py"}, False),
            ("phantom", {"pkg/a.py"}, False),
            ("mod.ref", {"pkg/a.py"}, False),
        ],
    )
    def test_known_prefix(self, target: str, known: set[str], expected: bool) -> None:
        """Bare file id or file::qual prefix must match indexed paths."""
        assert target_starts_with_known_file(target, known) is expected


class TestInferCallTargetKind:
    """infer_call_target_kind."""

    @pytest.mark.parametrize(
        "target,kind",
        [
            ("f.py::X", "resolved_node"),
            ("a.b.c", "module_ref"),
            ("len", "phantom"),
        ],
    )
    def test_matrix(self, target: str, kind: str) -> None:
        """Classify CALLS: file-qualified, dotted module ref, or bare name."""
        assert infer_call_target_kind(target) == kind


class TestInferImportTargetKind:
    """infer_import_target_kind."""

    @pytest.mark.parametrize(
        "target,kind",
        [
            ("m.py::fn", "resolved_node"),
            ("pkg/mod.py", "resolved_node"),
            ("foo.ts", "resolved_node"),
            ("dotted.name", "module_ref"),
        ],
    )
    def test_matrix(self, target: str, kind: str) -> None:
        """Extension or file:: is resolved; else module ref."""
        assert infer_import_target_kind(target) == kind


class TestInferInheritsTargetKind:
    """infer_inherits_target_kind."""

    @pytest.mark.parametrize(
        "target,kind",
        [
            ("m.py::Base", "resolved_node"),
            ("pkg.Base", "module_ref"),
            ("Base", "phantom"),
        ],
    )
    def test_matrix(self, target: str, kind: str) -> None:
        """Align dotted vs bare with inheritance lowering."""
        assert infer_inherits_target_kind(target) == kind
