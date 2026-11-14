"""Unit tests for helpers module."""

from __future__ import annotations

import time
import unittest

from tests.ha_stubs import install_stubs

install_stubs()

from custom_components.dify_conversation.helpers import (  # noqa: E402
    ConversationMappingCache,
    InvalidJsonError,
    StreamingResponseCleaner,
    clean_response_text,
    render_custom_inputs,
    should_continue_conversation,
    validate_custom_inputs_json,
)


class TestCustomInputsValidationAndRendering(unittest.TestCase):
    """Tests for JSON validation and template rendering."""

    def test_validate_empty_returns_empty_dict(self) -> None:
        self.assertEqual(validate_custom_inputs_json(None), {})
        self.assertEqual(validate_custom_inputs_json("   "), {})
        self.assertEqual(validate_custom_inputs_json("{}"), {})

    def test_validate_invalid_json_raises(self) -> None:
        with self.assertRaises(InvalidJsonError) as ctx:
            validate_custom_inputs_json('{"user": "$user_id"')
        self.assertEqual(ctx.exception.error_key, "invalid_json")

    def test_validate_non_object_json_raises(self) -> None:
        for raw in ('["a", "b"]', '"hello"', "123", "true"):
            with self.assertRaises(InvalidJsonError) as ctx:
                validate_custom_inputs_json(raw)
            self.assertEqual(ctx.exception.error_key, "invalid_json_object")

    def test_render_nested_templates_and_query_override(self) -> None:
        template_inputs = {
            "user_id": "$user_id",
            "user_name": "${user_name}",
            "nested": {"device": "$device_id", "tags": ["$area_name", 42, True]},
            "price": "$100",
            "query": "user_tried_to_set_this",
        }
        variables = {
            "user_id": "alice",
            "user_name": "Alice",
            "device_id": 'dev-"1"\nline2',
            "area_name": "Living Room",
        }
        rendered = render_custom_inputs(template_inputs, variables, "Turn on the light")

        self.assertEqual(rendered["user_id"], "alice")
        self.assertEqual(rendered["user_name"], "Alice")
        self.assertEqual(rendered["nested"]["device"], 'dev-"1"\nline2')
        self.assertEqual(rendered["nested"]["tags"], ["Living Room", 42, True])
        self.assertEqual(rendered["price"], "$100")
        self.assertEqual(rendered["query"], "Turn on the light")

    def test_render_without_query_does_not_add_query_key(self) -> None:
        rendered = render_custom_inputs({"user_id": "$user_id"}, {"user_id": ""}, "hi")
        self.assertEqual(rendered, {"user_id": ""})
        self.assertNotIn("query", rendered)


class TestResponseCleaningAndContinueConversation(unittest.TestCase):
    """Tests for thinking/markdown cleanup and trailing question detection."""

    def test_should_continue_conversation(self) -> None:
        self.assertTrue(should_continue_conversation("Would you like me to turn it on?"))
        self.assertTrue(should_continue_conversation("请确认是否继续？\n  "))
        self.assertTrue(should_continue_conversation("次はどうしますか？ "))
        self.assertFalse(should_continue_conversation("Done."))
        self.assertFalse(should_continue_conversation("好的，已经打开了；"))
        self.assertFalse(should_continue_conversation(""))

    def test_clean_response_text(self) -> None:
        raw = "<think>internal reasoning\nwith **bold**</think>\n# Title\n**Hello** [Home](https://ha.local) `ok`\n- item 1"
        cleaned = clean_response_text(raw)
        self.assertEqual(cleaned, "Title\nHello Home ok\nitem 1")

    def test_streaming_cleaner_splits_think_across_chunks(self) -> None:
        cleaner = StreamingResponseCleaner(clean_response=True)
        chunks = [
            "<thi",
            "nk>secret ",
            "thought</thi",
            "nk>\n**Hello**\n",
            "How are ",
            "you?",
        ]
        visible_out: list[str] = []
        thinking_out: list[str] = []

        for chunk in chunks:
            vis, think = cleaner.feed(chunk)
            if vis:
                visible_out.append(vis)
            if think:
                thinking_out.append(think)

        vis_tail, think_tail = cleaner.finish()
        if vis_tail:
            visible_out.append(vis_tail)
        if think_tail:
            thinking_out.append(think_tail)

        self.assertEqual("".join(thinking_out), "secret thought")
        self.assertEqual("".join(visible_out), "Hello\nHow are you?")

    def test_streaming_cleaner_passthrough_when_disabled(self) -> None:
        cleaner = StreamingResponseCleaner(clean_response=False)
        vis1, think1 = cleaner.feed("<think>keep</think>**bold**")
        vis2, think2 = cleaner.finish()
        self.assertEqual(vis1 + vis2, "<think>keep</think>**bold**")
        self.assertEqual(think1 + think2, "")


class TestConversationMappingCache(unittest.TestCase):
    """Tests for ConversationMappingCache LRU and TTL behavior."""

    def test_lru_eviction(self) -> None:
        cache = ConversationMappingCache(max_size=2, ttl_seconds=60)
        cache.set("ha1", "dify1")
        cache.set("ha2", "dify2")
        # Access ha1 to refresh its recency so ha2 becomes least recently used.
        self.assertEqual(cache.get("ha1"), "dify1")
        cache.set("ha3", "dify3")
        self.assertIsNone(cache.get("ha2"))
        self.assertEqual(cache.get("ha1"), "dify1")
        self.assertEqual(cache.get("ha3"), "dify3")

    def test_ttl_expiration_and_delete(self) -> None:
        cache = ConversationMappingCache(max_size=10, ttl_seconds=0.02)
        cache.set("ha1", "dify1")
        time.sleep(0.03)
        self.assertIsNone(cache.get("ha1"))

        cache.set("ha2", "dify2")
        cache.delete("ha2")
        self.assertIsNone(cache.get("ha2"))


if __name__ == "__main__":
    unittest.main()
