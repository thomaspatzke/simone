"""Tests for sigma_output module."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from sigma_ai.tools.sigma_output import (
    extract_sigma_filename,
    find_next_available_path,
    save_rule,
)


class TestExtractSigmaFilename:
    """Test sigma filename extraction from rule YAML."""

    def test_simple_title(self) -> None:
        """Test extraction with a simple title."""
        rule_yaml = """
title: Process Creation Detection
id: 12345678-1234-1234-1234-123456789012
status: experimental
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\\\\cmd.exe'
    condition: selection
"""
        assert extract_sigma_filename(rule_yaml) == "process_creation_detection.yml"

    def test_title_with_special_characters(self) -> None:
        """Test extraction with special characters in title."""
        rule_yaml = """
title: Windows: Registry Event (HKCU\\Software\\Classes)
id: 12345678-1234-1234-1234-123456789012
status: experimental
"""
        filename = extract_sigma_filename(rule_yaml)
        assert filename == "windows_registry_event_hkcusofdwareclass.yml"

    def test_title_with_spaces(self) -> None:
        """Test extraction with multiple spaces."""
        rule_yaml = """
title: Multiple   Spaces   Here
id: 12345678-1234-1234-1234-123456789012
"""
        assert extract_sigma_filename(rule_yaml) == "multiple_spaces_here.yml"

    def test_missing_title_raises_error(self) -> None:
        """Test that missing title raises ValueError."""
        rule_yaml = """
id: 12345678-1234-1234-1234-123456789012
status: experimental
"""
        with pytest.raises(ValueError, match="must contain a 'title' field"):
            extract_sigma_filename(rule_yaml)

    def test_empty_title_raises_error(self) -> None:
        """Test that empty title raises ValueError."""
        rule_yaml = """
title: ""
id: 12345678-1234-1234-1234-123456789012
"""
        with pytest.raises(ValueError, match="title cannot be empty"):
            extract_sigma_filename(rule_yaml)

    def test_invalid_yaml_raises_error(self) -> None:
        """Test that invalid YAML raises ValueError."""
        rule_yaml = "{ invalid yaml ]"
        with pytest.raises(ValueError, match="Invalid YAML"):
            extract_sigma_filename(rule_yaml)


class TestFindNextAvailablePath:
    """Test finding next available file path with indexing."""

    def test_file_does_not_exist(self) -> None:
        """Test when file doesn't exist, return as-is."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = find_next_available_path(output_dir, "new_rule.yml")
            assert result == output_dir / "new_rule.yml"
            assert not result.exists()

    def test_file_exists_single_index(self) -> None:
        """Test when file exists, append index -2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            existing_file = output_dir / "rule.yml"
            existing_file.write_text("# existing rule")

            result = find_next_available_path(output_dir, "rule.yml")
            assert result == output_dir / "rule-2.yml"
            assert not result.exists()

    def test_file_exists_multiple_indices(self) -> None:
        """Test when multiple indexed versions exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Create rule.yml, rule-2.yml, rule-3.yml
            (output_dir / "rule.yml").write_text("# v1")
            (output_dir / "rule-2.yml").write_text("# v2")
            (output_dir / "rule-3.yml").write_text("# v3")

            result = find_next_available_path(output_dir, "rule.yml")
            assert result == output_dir / "rule-4.yml"
            assert not result.exists()

    def test_creates_directory_if_needed(self) -> None:
        """Test that directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nonexistent" / "nested" / "dir"
            assert not output_dir.exists()

            result = find_next_available_path(output_dir, "rule.yml")
            assert output_dir.exists()
            assert result == output_dir / "rule.yml"


class TestSaveRule:
    """Test saving rules to files."""

    def test_save_rule_creates_file(self) -> None:
        """Test that save_rule creates a file with correct content."""
        rule_yaml = """
title: Test Detection Rule
id: 12345678-1234-1234-1234-123456789012
status: experimental
description: Test rule
logsource:
    category: process_creation
    product: windows
detection:
    selection:
        Image|endswith: '\\\\cmd.exe'
    condition: selection
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = save_rule(rule_yaml, output_dir)

            assert result.startswith("✅ Rule saved to:")
            assert "test_detection_rule.yml" in result

            saved_file = output_dir / "test_detection_rule.yml"
            assert saved_file.exists()
            assert saved_file.read_text() == rule_yaml

    def test_save_rule_appends_index_on_duplicate(self) -> None:
        """Test that duplicate rules get indexed."""
        rule_yaml = """
title: Duplicate Test
id: 12345678-1234-1234-1234-123456789012
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)

            # Save first copy
            result1 = save_rule(rule_yaml, output_dir)
            assert "duplicate_test.yml" in result1

            # Save second copy with same content
            result2 = save_rule(rule_yaml, output_dir)
            assert "duplicate_test-2.yml" in result2

            # Save third copy
            result3 = save_rule(rule_yaml, output_dir)
            assert "duplicate_test-3.yml" in result3

            # Verify all files exist and have correct content
            assert (output_dir / "duplicate_test.yml").exists()
            assert (output_dir / "duplicate_test-2.yml").exists()
            assert (output_dir / "duplicate_test-3.yml").exists()

    def test_save_rule_invalid_yaml(self) -> None:
        """Test that invalid YAML raises error."""
        invalid_yaml = "{ invalid yaml ["
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with pytest.raises(ValueError):
                save_rule(invalid_yaml, output_dir)

    def test_save_rule_missing_title(self) -> None:
        """Test that rule without title raises error."""
        rule_yaml = """
id: 12345678-1234-1234-1234-123456789012
status: experimental
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            with pytest.raises(ValueError):
                save_rule(rule_yaml, output_dir)
