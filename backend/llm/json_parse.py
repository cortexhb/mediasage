"""Recovering JSON from prose an LLM wrapped around it.

Models fence their JSON, prepend explanations, use smart quotes, and trail
commas. `parse_json` strips those in order and falls back to `json_repair`.
Entry point: `parse_json`; `extract_json_bounds` is exposed for tests.

This stays separate from the client because it is string handling, not
transport: nothing here knows which provider produced the text.

TODO: Convert to structured responses later
"""

import json
import logging
from typing import Any

from json_repair import repair_json

from backend.llm.constants import (
    ANY_FENCE,
    ERROR_PREVIEW_CHARS,
    JSON_FENCE,
    SMART_QUOTES,
)

logger = logging.getLogger(__name__)


class JSONParseError(ValueError):
    """Raised when no strategy recovers JSON from a response."""


def extract_json_bounds(content: str) -> str | None:
    """Return the first complete JSON array or object embedded in `content`.

    Tracks bracket depth while skipping over string literals, so a bracket
    inside a title does not close the structure early. Returns None when no
    balanced structure is found.
    """
    openers = {"[": "]", "{": "}"}

    start_idx = next((i for i, c in enumerate(content) if c in openers), None)
    if start_idx is None:
        return None

    open_char = content[start_idx]
    close_char = openers[open_char]

    depth = 0
    in_string = False
    escape_next = False

    for i in range(start_idx, len(content)):
        c = content[i]

        if escape_next:
            escape_next = False
        elif c == "\\" and in_string:
            escape_next = True
        elif c == '"':
            in_string = not in_string
        elif in_string:
            continue
        elif c == open_char:
            depth += 1
        elif c == close_char:
            depth -= 1
            if depth == 0:
                return content[start_idx : i + 1]

    return None


def strip_fences(content: str) -> str:
    """Return the contents of a fenced code block, or `content` unchanged."""
    match = JSON_FENCE.search(content) or ANY_FENCE.search(content)
    return match.group(1).strip() if match else content


def parse_json(content: str) -> Any:
    """Parse JSON out of raw model output.

    Args:
        content: The model's reply, possibly fenced or wrapped in prose

    Returns:
        The decoded JSON value

    Raises:
        JSONParseError: If no strategy recovers valid JSON
    """
    content = content.strip()
    if not content:
        raise JSONParseError(
            "LLM returned an empty response. This may happen if the context "
            "window is too small. Try reducing 'Max Tracks to AI' in filters."
        )

    content = strip_fences(content).translate(SMART_QUOTES)

    try:
        return json.loads(content)
    except json.JSONDecodeError as original:
        extracted = extract_json_bounds(content)
        if extracted is not None:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                logger.debug("Bounded extraction did not yield valid JSON")

        try:
            repaired = repair_json(content, return_objects=True)
        except (ValueError, TypeError, RecursionError) as repair_error:
            logger.debug("json_repair failed: %s", repair_error)
        else:
            # Repair never raises; prose comes back as "", not a result.
            if repaired not in ("", None):
                logger.debug("JSON repair succeeded for malformed LLM response")
                return repaired
            logger.debug("json_repair found no structure to recover")

        preview = content[:ERROR_PREVIEW_CHARS]
        if len(content) > ERROR_PREVIEW_CHARS:
            preview += "..."
        raise JSONParseError(
            f"Failed to parse LLM response as JSON: {original}\n"
            f"Response preview: {preview}"
        ) from original
