"""Tests for recovering JSON from prose an LLM wrapped around it."""

import pytest

from backend.llm import JSONParseError, extract_json_bounds, parse_json


class TestFences:
    """Tests for stripping markdown code fences."""

    def test_prefers_a_json_tagged_fence(self):
        """A tagged fence wins over an untagged one that appears first."""
        content = '```\nnot json\n```\n```json\n{"a": 1}\n```'

        assert parse_json(content) == {"a": 1}

    def test_falls_back_to_an_untagged_fence(self):
        """An untagged fence is used when no tagged one is present."""
        assert parse_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_parses_bare_json(self):
        """Unfenced JSON needs no stripping."""
        assert parse_json('{"a": 1}') == {"a": 1}


class TestSmartQuotes:
    """Tests for the typographic quotes models emit."""

    @pytest.mark.parametrize(
        "content",
        [
            '{\u201ca\u201d: 1}',
            '[{\u201ctitle\u201d: \u201cSong\u201d}]',
        ],
    )
    def test_curly_double_quotes_are_normalised(self, content):
        """Curly quotes must become straight ones or the decode fails."""
        assert parse_json(content) is not None

    def test_curly_single_quotes_are_normalised(self):
        """An apostrophe inside a value must not break the decode."""
        result = parse_json('[{"title": "Don\u2019t Stop"}]')

        assert result == [{"title": "Don't Stop"}]


class TestExtraProse:
    """Tests for JSON buried in an explanation."""

    def test_parses_json_followed_by_prose(self):
        """Trailing commentary must not defeat the decode."""
        content = '[{"a": 1}]\n\nI hope this helps!'

        assert parse_json(content) == [{"a": 1}]

    def test_parses_json_preceded_by_prose(self):
        """Leading commentary must not defeat the decode."""
        content = 'Here you go:\n[{"a": 1}]'

        assert parse_json(content) == [{"a": 1}]

    def test_handles_nested_structures(self):
        """Depth tracking must find the outermost closing bracket."""
        content = 'Result: {"a": {"b": [1, 2, {"c": 3}]}} done'

        assert parse_json(content) == {"a": {"b": [1, 2, {"c": 3}]}}


class TestExtractJsonBounds:
    """Tests for the bracket scanner."""

    def test_ignores_brackets_inside_strings(self):
        """A bracket in a track title must not close the structure early."""
        content = '[{"title": "Song [Live]"}, {"title": "Other"}]'

        assert extract_json_bounds(content) == content

    def test_ignores_escaped_quotes(self):
        """An escaped quote does not end the string it sits in."""
        content = '[{"title": "He said \\"hi\\" [x]"}]'

        assert extract_json_bounds(content) == content

    def test_returns_none_without_a_structure(self):
        """Plain prose yields nothing rather than a partial slice."""
        assert extract_json_bounds("no json here") is None

    def test_returns_none_when_unbalanced(self):
        """An unclosed structure is not a result."""
        assert extract_json_bounds('[{"a": 1}') is None


class TestRepair:
    """Tests for the json_repair fallback."""

    def test_repairs_a_trailing_comma(self):
        """Trailing commas are the most common malformation."""
        assert parse_json('[{"a": 1},]') == [{"a": 1}]

    def test_repairs_unescaped_quotes_in_a_value(self):
        """An unescaped inner quote is repaired rather than rejected."""
        result = parse_json('[{"title": "The "Best" Song"}]')

        assert isinstance(result, list)
        assert len(result) == 1

    def test_repairs_single_quoted_keys(self):
        """Single quotes are not valid JSON but models emit them."""
        assert parse_json("{'a': 1}") == {"a": 1}


class TestFailures:
    """Tests for what happens when nothing works."""

    def test_empty_response_names_the_context_window(self):
        """The likely cause is a window too small, so the message says so."""
        with pytest.raises(JSONParseError, match="context"):
            parse_json("   ")

    def test_error_carries_a_preview(self):
        """The message must show enough of the reply to identify the failure."""
        with pytest.raises(JSONParseError, match="Response preview"):
            parse_json("this is not json at all, not even close")
