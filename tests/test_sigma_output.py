"""Tests for saving rules without overwriting."""
from __future__ import annotations

from pathlib import Path

import pytest

from simone.tools.sigma_output import check_filename, find_next_available_path, save_rule

RULE = """
title: Process Creation Detection
id: 12345678-1234-1234-1234-123456789012
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\\cmd.exe'
    condition: selection
"""


class TestCheckFilename:
    def test_valid(self) -> None:
        assert check_filename("proc_creation_win_test_rule.yml") == "proc_creation_win_test_rule.yml"

    @pytest.mark.parametrize(
        "name",
        [
            "../escape.yml",
            "sub/dir.yml",
            "/abs/path.yml",
            "Upper_Case.yml",
            "with-hyphen.yml",
            "rule.yaml",
            "rule",
            "",
        ],
    )
    def test_invalid(self, name: str) -> None:
        with pytest.raises(ValueError, match="Invalid file name"):
            check_filename(name)


class TestFindNextAvailablePath:
    def test_free_name(self, tmp_path: Path) -> None:
        assert find_next_available_path(tmp_path, "rule_name.yml") == tmp_path / "rule_name.yml"

    def test_appends_underscore_index(self, tmp_path: Path) -> None:
        (tmp_path / "rule_name.yml").write_text("x")
        (tmp_path / "rule_name_2.yml").write_text("x")
        assert find_next_available_path(tmp_path, "rule_name.yml") == tmp_path / "rule_name_3.yml"

    def test_creates_directory(self, tmp_path: Path) -> None:
        target = tmp_path / "a" / "b"
        assert find_next_available_path(target, "rule_name.yml").parent == target
        assert target.is_dir()


class TestSaveRule:
    def test_saves(self, tmp_path: Path) -> None:
        message = save_rule(RULE, "proc_creation_win_test.yml", tmp_path)
        saved = tmp_path / "proc_creation_win_test.yml"
        assert saved.read_text(encoding="utf-8") == RULE
        assert saved.as_posix() in message

    def test_never_overwrites(self, tmp_path: Path) -> None:
        save_rule(RULE, "proc_creation_win_test.yml", tmp_path)
        save_rule(RULE.replace("Process", "Other"), "proc_creation_win_test.yml", tmp_path)
        assert "Process Creation" in (tmp_path / "proc_creation_win_test.yml").read_text()
        assert "Other Creation" in (tmp_path / "proc_creation_win_test_2.yml").read_text()

    def test_invalid_filename_writes_nothing(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError):
            save_rule(RULE, "../outside.yml", tmp_path)
        assert not (tmp_path.parent / "outside.yml").exists()

    @pytest.mark.parametrize(("text", "message"), [("a: [b", "Invalid YAML"), ("", "empty"), ("---\n", "empty")])
    def test_invalid_yaml(self, tmp_path: Path, text: str, message: str) -> None:
        with pytest.raises(ValueError, match=message):
            save_rule(text, "proc_creation_win_test.yml", tmp_path)
        assert list(tmp_path.iterdir()) == []
