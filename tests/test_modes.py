"""Tests for list-structure preservation logic.

Mode definitions now live in default_config.toml (single source of truth).
Default mode loading is tested in test_config.py::TestConfigDefaults.
"""

from prosefmt.modes import (
    has_list_structure,
    restore_list_prefixes,
    strip_list_prefixes,
)


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

    def test_has_list_after_plain_text(self):
        """Lists not on line 1 must still be detected (re.MULTILINE fix)."""
        assert has_list_structure("Header line\n- bullet one\n- bullet two")

    def test_has_list_numbered_after_header(self):
        assert has_list_structure("My list:\n1. first item\n2. second item")

    def test_parenthesised_numbers(self):
        """Support ``1)`` style numbering."""
        text = "1) first\n2) second"
        assert has_list_structure(text)
        prefixes, stripped = strip_list_prefixes(text)
        assert prefixes == ["1) ", "2) "]
        assert stripped == "first\nsecond"
