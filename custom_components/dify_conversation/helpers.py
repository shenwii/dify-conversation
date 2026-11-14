"""Helper utilities for Dify Conversation."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Mapping
import json
import re
from string import Template
import time
from typing import Any

from .const import CONVERSATION_CACHE_MAX_SIZE, CONVERSATION_CACHE_TTL_SECONDS

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_UNCLOSED_THINK_RE = re.compile(r"<think>.*$", re.IGNORECASE | re.DOTALL)
_CODE_FENCE_RE = re.compile(r"^\s*```.*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s+", re.MULTILINE)
_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}>\s?", re.MULTILINE)
_LIST_BULLET_RE = re.compile(r"^\s*[-*+]\s+", re.MULTILINE)
_HRULE_RE = re.compile(r"^\s*(?:[-*_]){3,}\s*$", re.MULTILINE)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_BOLD_ITALIC_RE = re.compile(r"\*\*\*(.+?)\*\*\*|___(.+?)___")
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")
_ITALIC_RE = re.compile(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)|(?<!_)_(?!_)(.+?)(?<!_)_(?!_)")
_STRIKETHROUGH_RE = re.compile(r"~~(.+?)~~")
_MULTI_BLANK_LINES_RE = re.compile(r"\n{3,}")

_THINK_OPEN_TAG = "<think>"
_THINK_CLOSE_TAG = "</think>"


class InvalidJsonError(ValueError):
    """Raised when a custom inputs string is not valid JSON."""

    def __init__(self, error_key: str) -> None:
        """Initialize the error with a translation error key."""
        super().__init__(error_key)
        self.error_key = error_key


def validate_custom_inputs_json(raw_json: str | None) -> dict[str, Any]:
    """Parse and validate the custom inputs JSON configuration string."""
    if raw_json is None or not raw_json.strip():
        return {}

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as err:
        raise InvalidJsonError("invalid_json") from err

    if not isinstance(parsed, dict):
        raise InvalidJsonError("invalid_json_object")

    return parsed


def _substitute_value(value: Any, variables: Mapping[str, str]) -> Any:
    """Recursively substitute template variables inside JSON values."""
    if isinstance(value, str):
        return Template(value).safe_substitute(variables)
    if isinstance(value, list):
        return [_substitute_value(item, variables) for item in value]
    if isinstance(value, dict):
        return {k: _substitute_value(v, variables) for k, v in value.items()}
    return value


def render_custom_inputs(
    template_inputs: Mapping[str, Any],
    variables: Mapping[str, str],
    query: str,
) -> dict[str, Any]:
    """Render template variables into Dify inputs and force-override query if present."""
    rendered: dict[str, Any] = _substitute_value(dict(template_inputs), variables)
    if "query" in rendered:
        rendered["query"] = query
    return rendered


def strip_thinking_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from text."""
    cleaned = _THINK_BLOCK_RE.sub("", text)
    return _UNCLOSED_THINK_RE.sub("", cleaned)


def strip_markdown(text: str) -> str:
    """Strip common Markdown syntax to make responses cleaner for TTS."""
    cleaned = _CODE_FENCE_RE.sub("", text)
    cleaned = _HRULE_RE.sub("", cleaned)
    cleaned = _HEADING_RE.sub("", cleaned)
    cleaned = _BLOCKQUOTE_RE.sub("", cleaned)
    cleaned = _LIST_BULLET_RE.sub("", cleaned)
    cleaned = _IMAGE_RE.sub(r"\1", cleaned)
    cleaned = _LINK_RE.sub(r"\1", cleaned)
    cleaned = _INLINE_CODE_RE.sub(r"\1", cleaned)
    cleaned = _BOLD_ITALIC_RE.sub(lambda m: m.group(1) or m.group(2), cleaned)
    cleaned = _BOLD_RE.sub(lambda m: m.group(1) or m.group(2), cleaned)
    cleaned = _ITALIC_RE.sub(lambda m: m.group(1) or m.group(2), cleaned)
    cleaned = _STRIKETHROUGH_RE.sub(r"\1", cleaned)
    return _MULTI_BLANK_LINES_RE.sub("\n\n", cleaned)


def clean_response_text(text: str) -> str:
    """Remove thinking tags and Markdown formatting from a full response."""
    return strip_markdown(strip_thinking_tags(text)).strip()


def should_continue_conversation(text: str) -> bool:
    """Return True when the trimmed response ends with an ASCII or full-width question mark."""
    return text.rstrip().endswith(("?", "？"))


def _partial_tag_suffix_len(text: str, tag: str) -> int:
    """Return length of the longest suffix of text that is a non-empty prefix of tag."""
    lowered = text.lower()
    max_check = min(len(lowered), len(tag) - 1)
    for length in range(max_check, 0, -1):
        if lowered.endswith(tag[:length]):
            return length
    return 0


class StreamingResponseCleaner:
    """Incrementally separate <think> blocks and optionally clean Markdown per line."""

    def __init__(self, clean_response: bool) -> None:
        """Initialize streaming cleaner."""
        self._clean_response = clean_response
        self._in_think = False
        self._tag_buffer = ""
        self._line_buffer = ""
        self._emitted_visible = False

    def feed(self, chunk: str) -> tuple[str, str]:
        """Process an incoming chunk and return (visible_delta, thinking_delta)."""
        if not chunk:
            return "", ""

        if not self._clean_response:
            return chunk, ""

        raw_visible, thinking = self._extract_think_segments(chunk)
        if not raw_visible:
            return "", thinking

        self._line_buffer += raw_visible
        if "\n" not in self._line_buffer:
            return "", thinking

        complete_part, self._line_buffer = self._line_buffer.rsplit("\n", 1)
        cleaned = self._clean_segment(complete_part + "\n", is_final=False)
        return cleaned, thinking

    def finish(self) -> tuple[str, str]:
        """Flush any remaining buffered text at stream completion."""
        if not self._clean_response:
            return "", ""

        thinking = ""
        raw_visible = ""
        if self._tag_buffer:
            if self._in_think:
                thinking = self._tag_buffer
            else:
                raw_visible = self._tag_buffer
            self._tag_buffer = ""

        self._line_buffer += raw_visible
        cleaned = ""
        if self._line_buffer:
            cleaned = self._clean_segment(self._line_buffer, is_final=True)
            self._line_buffer = ""

        return cleaned, thinking

    def _clean_segment(self, segment: str, is_final: bool) -> str:
        """Clean a visible segment while preserving spacing between streamed chunks."""
        cleaned = strip_markdown(segment)
        if not self._emitted_visible:
            cleaned = cleaned.lstrip()
        if is_final:
            cleaned = cleaned.rstrip()
        if cleaned:
            self._emitted_visible = True
        return cleaned

    def _extract_think_segments(self, chunk: str) -> tuple[str, str]:
        """Split a chunk into visible text and <think> reasoning text across boundaries."""
        data = self._tag_buffer + chunk
        self._tag_buffer = ""
        visible_parts: list[str] = []
        thinking_parts: list[str] = []

        while data:
            if self._in_think:
                idx = data.lower().find(_THINK_CLOSE_TAG)
                if idx != -1:
                    thinking_parts.append(data[:idx])
                    data = data[idx + len(_THINK_CLOSE_TAG) :]
                    self._in_think = False
                else:
                    hold = _partial_tag_suffix_len(data, _THINK_CLOSE_TAG)
                    if hold:
                        thinking_parts.append(data[:-hold])
                        self._tag_buffer = data[-hold:]
                    else:
                        thinking_parts.append(data)
                    break
            else:
                idx = data.lower().find(_THINK_OPEN_TAG)
                if idx != -1:
                    visible_parts.append(data[:idx])
                    data = data[idx + len(_THINK_OPEN_TAG) :]
                    self._in_think = True
                else:
                    hold = _partial_tag_suffix_len(data, _THINK_OPEN_TAG)
                    if hold:
                        visible_parts.append(data[:-hold])
                        self._tag_buffer = data[-hold:]
                    else:
                        visible_parts.append(data)
                    break

        return "".join(visible_parts), "".join(thinking_parts)


class ConversationMappingCache:
    """Bounded LRU + TTL mapping between HA conversation IDs and Dify conversation IDs."""

    def __init__(
        self,
        max_size: int = CONVERSATION_CACHE_MAX_SIZE,
        ttl_seconds: float = CONVERSATION_CACHE_TTL_SECONDS,
    ) -> None:
        """Initialize the conversation mapping cache."""
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._entries: OrderedDict[str, tuple[str, float]] = OrderedDict()

    def get(self, ha_conversation_id: str) -> str | None:
        """Retrieve a Dify conversation ID if present and not expired."""
        item = self._entries.get(ha_conversation_id)
        if item is None:
            return None

        dify_id, updated_at = item
        now = time.monotonic()
        if now - updated_at > self._ttl_seconds:
            del self._entries[ha_conversation_id]
            return None

        self._entries.move_to_end(ha_conversation_id)
        self._entries[ha_conversation_id] = (dify_id, now)
        return dify_id

    def set(self, ha_conversation_id: str, dify_conversation_id: str) -> None:
        """Store or refresh a mapping between HA and Dify conversation IDs."""
        if not ha_conversation_id or not dify_conversation_id:
            return

        now = time.monotonic()
        if ha_conversation_id in self._entries:
            self._entries.move_to_end(ha_conversation_id)
        self._entries[ha_conversation_id] = (dify_conversation_id, now)

        while len(self._entries) > self._max_size:
            self._entries.popitem(last=False)

    def delete(self, ha_conversation_id: str) -> None:
        """Remove a mapping entry if it exists."""
        self._entries.pop(ha_conversation_id, None)
