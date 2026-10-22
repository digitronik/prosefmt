"""Tests for modes and list-structure preservation."""

from reword.modes import (
    BUILTIN_MODES,
    has_list_structure,
    restore_list_prefixes,
    strip_list_prefixes,
)


class TestBuiltinModes:
    def test_all_modes_have_required_fields(self):
        for name, mode in BUILTIN_MODES.items():
            assert "name" in mode, f"{name} missing 'name'"
            assert "prompt" in mode, f"{name} missing 'prompt'"
            assert "label" in mode, f"{name} missing 'label'"
            assert "preserve_structure" in mode, f"{name} missing 'preserve_structure'"

    def test_fix_mode_preserves_structure(self):
        assert BUILTIN_MODES["fix"]["preserve_structure"] is True

    def test_summarize_does_not_preserve_structure(self):
        assert BUILTIN_MODES["summarize"]["preserve_structure"] is False

    def test_email_does_not_preserve_structure(self):
        assert BUILTIN_MODES["email"]["preserve_structure"] is False


class TestListStructure:
    def test_has_list_structure_bullets(self):
        assert has_list_structure("- item one\n- item two")

    def test_has_list_structure_numbers(self):
        assert has_list_structure("1. first\n2. second")

    def test_has_list_structure_plain(self):
        assert not has_list_structure("just some plain text\nwith multiple lines")

    def test_has_list_structure_unicode_bullet(self):
        assert has_list_structure("\u2022 bullet point")

    def test_strip_and_restore_bullets(self):
        text = "- first item\n- second item\n- third item"
        prefixes, stripped = strip_list_prefixes(text)

        assert len(prefixes) == 3
        assert all(p == "- " for p in prefixes)
        assert "- " not in stripped

        restored = restore_list_prefixes(stripped, prefixes)
        assert restored == text

    def test_strip_and_restore_numbered(self):
        text = "1. first\n2. second\n3. third"
        prefixes, stripped = strip_list_prefixes(text)

        assert prefixes == ["1. ", "2. ", "3. "]
        assert stripped == "first\nsecond\nthird"

        restored = restore_list_prefixes(stripped, prefixes)
        assert restored == text

    def test_strip_mixed_content(self):
        text = "Header line\n- bullet one\n- bullet two\nPlain line"
        prefixes, _stripped = strip_list_prefixes(text)

        assert prefixes[0] == ""
        assert prefixes[1] == "- "
        assert prefixes[2] == "- "
        assert prefixes[3] == ""

    def test_restore_with_different_line_count(self):
        """If the model changes line count, return text as-is."""
        prefixes = ["- ", "- ", "- "]
        text = "one\ntwo"
        assert restore_list_prefixes(text, prefixes) == text

    def test_restore_with_no_prefixes(self):
        prefixes = ["", "", ""]
        text = "a\nb\nc"
        assert restore_list_prefixes(text, prefixes) == text

    def test_indented_bullets(self):
        text = "  - indented\n  - also indented"
        prefixes, stripped = strip_list_prefixes(text)
        assert prefixes == ["  - ", "  - "]
        assert stripped == "indented\nalso indented"

    def test_asterisk_bullets(self):
        text = "* star one\n* star two"
        prefixes, _stripped = strip_list_prefixes(text)
        assert prefixes == ["* ", "* "]
