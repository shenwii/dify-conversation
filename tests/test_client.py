"""Unit tests for the async Dify API client."""

from __future__ import annotations

import json
import unittest

from tests.ha_stubs import install_stubs

install_stubs()

from custom_components.dify_conversation.client import (  # noqa: E402
    DifyAuthError,
    DifyClient,
    DifyConnectionError,
    DifyConversationNotFoundError,
    DifyResponseError,
    DifyUnsupportedAppError,
)


class _FakeContent:
    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = chunks

    async def iter_any(self):
        for chunk in self._chunks:
            yield chunk


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int = 200,
        text_body: str = "",
        json_body: dict | None = None,
        stream_chunks: list[bytes] | None = None,
    ) -> None:
        self.status = status
        self._text_body = text_body
        self._json_body = json_body
        self.content = _FakeContent(stream_chunks or [])

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def text(self) -> str:
        return self._text_body

    async def json(self, content_type=None):
        return self._json_body


class _FakeSession:
    def __init__(self, routes: dict[tuple[str, str], list[_FakeResponse | Exception]]) -> None:
        self._routes = routes
        self.calls: list[tuple[str, str, dict]] = []

    def get(self, url: str, **kwargs):
        self.calls.append(("GET", url, kwargs))
        item = self._routes[("GET", url)].pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def post(self, url: str, **kwargs):
        self.calls.append(("POST", url, kwargs))
        item = self._routes[("POST", url)].pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class TestDifyClient(unittest.IsolatedAsyncioTestCase):
    """Tests for DifyClient HTTP and SSE handling."""

    async def test_validate_connection_success(self) -> None:
        session = _FakeSession(
            {
                ("GET", "https://api.dify.ai/v1/info"): [
                    _FakeResponse(status=200, json_body={"name": "Home Agent", "mode": "agent-chat"})
                ]
            }
        )
        client = DifyClient(session, "https://api.dify.ai/v1/", "app-key", timeout=30)
        info = await client.async_validate_connection()
        self.assertEqual(info.name, "Home Agent")
        self.assertEqual(info.mode, "agent-chat")

    async def test_validate_connection_fallback_to_parameters(self) -> None:
        session = _FakeSession(
            {
                ("GET", "https://dify.local/v1/info"): [_FakeResponse(status=404)],
                ("GET", "https://dify.local/v1/parameters"): [
                    _FakeResponse(status=200, json_body={"user_input_form": []})
                ],
            }
        )
        client = DifyClient(session, "https://dify.local/v1", "app-key", timeout=30)
        info = await client.async_validate_connection()
        self.assertIsNone(info.name)
        self.assertIsNone(info.mode)

    async def test_validate_connection_errors(self) -> None:
        session_auth = _FakeSession(
            {("GET", "https://api.dify.ai/v1/info"): [_FakeResponse(status=401)]}
        )
        with self.assertRaises(DifyAuthError):
            await DifyClient(session_auth, "https://api.dify.ai/v1", "bad", 10).async_validate_connection()

        session_workflow = _FakeSession(
            {
                ("GET", "https://api.dify.ai/v1/info"): [
                    _FakeResponse(status=200, json_body={"name": "WF", "mode": "workflow"})
                ]
            }
        )
        with self.assertRaises(DifyUnsupportedAppError):
            await DifyClient(session_workflow, "https://api.dify.ai/v1", "k", 10).async_validate_connection()

        session_timeout = _FakeSession(
            {("GET", "https://api.dify.ai/v1/info"): [TimeoutError("timed out")]}
        )
        with self.assertRaises(DifyConnectionError):
            await DifyClient(session_timeout, "https://api.dify.ai/v1", "k", 10).async_validate_connection()

    async def test_chat_blocking_and_404_conversation_not_found(self) -> None:
        session = _FakeSession(
            {
                ("POST", "https://api.dify.ai/v1/chat-messages"): [
                    _FakeResponse(
                        status=200,
                        text_body=json.dumps({"answer": "Done.", "conversation_id": "dify-1"}),
                    ),
                    _FakeResponse(
                        status=404,
                        text_body=json.dumps(
                            {"code": "not_found", "message": "Conversation Not Exists."}
                        ),
                    ),
                ]
            }
        )
        client = DifyClient(session, "https://api.dify.ai/v1", "k", 30)
        answer, conv_id = await client.async_chat_blocking(
            query="hi", inputs={"user_id": "wei"}, user="wei"
        )
        self.assertEqual(answer, "Done.")
        self.assertEqual(conv_id, "dify-1")

        with self.assertRaises(DifyConversationNotFoundError):
            await client.async_chat_blocking(
                query="hi", inputs={}, user="wei", conversation_id="stale-id"
            )

    async def test_chat_streaming_parses_split_chunks_and_events(self) -> None:
        sse_payload = (
            ": ping\n\n"
            'event: message\ndata: {"event": "message", "answer": "你", "conversation_id": "c1"}\n\n'
            'event: agent_message\ndata: {"event": "agent_message", "answer": "好？", "conversation_id": "c1"}\n\n'
            'event: message_end\ndata: {"event": "message_end", "conversation_id": "c1"}\n\n'
        ).encode("utf-8")

        # Split arbitrarily mid-line to verify chunk reassembly.
        chunks = [sse_payload[:25], sse_payload[25:95], sse_payload[95:]]
        session = _FakeSession(
            {
                ("POST", "https://api.dify.ai/v1/chat-messages"): [
                    _FakeResponse(status=200, stream_chunks=chunks)
                ]
            }
        )
        client = DifyClient(session, "https://api.dify.ai/v1", "k", 30)
        events = [
            ev
            async for ev in client.async_chat_streaming(
                query="hello", inputs={}, user="wei", conversation_id=None
            )
        ]

        deltas = [ev.text for ev in events if ev.kind == "delta"]
        self.assertEqual("".join(deltas), "你好？")
        self.assertEqual(events[-1].kind, "end")
        self.assertEqual(events[-1].conversation_id, "c1")

    async def test_chat_streaming_midstream_errors(self) -> None:
        stale_sse = b'data: {"event": "error", "status": 404, "code": "conversation_not_exists", "message": "Conversation Not Exists"}\n\n'
        generic_sse = b'data: {"event": "error", "status": 500, "code": "llm_error", "message": "Model failed"}\n\n'
        session = _FakeSession(
            {
                ("POST", "https://api.dify.ai/v1/chat-messages"): [
                    _FakeResponse(status=200, stream_chunks=[stale_sse]),
                    _FakeResponse(status=200, stream_chunks=[generic_sse]),
                ]
            }
        )
        client = DifyClient(session, "https://api.dify.ai/v1", "k", 30)

        with self.assertRaises(DifyConversationNotFoundError):
            async for _ in client.async_chat_streaming(
                query="hi", inputs={}, user="wei", conversation_id="old"
            ):
                pass

        with self.assertRaises(DifyResponseError):
            async for _ in client.async_chat_streaming(
                query="hi", inputs={}, user="wei", conversation_id=None
            ):
                pass


if __name__ == "__main__":
    unittest.main()
