"""Async HTTP client for the Dify Chat Messages API."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
import json
from typing import Any

import aiohttp

from .const import RESPONSE_MODE_BLOCKING, RESPONSE_MODE_STREAMING, UNSUPPORTED_APP_MODES


class DifyError(Exception):
    """Base exception for Dify API errors."""


class DifyAuthError(DifyError):
    """Raised when Dify rejects the API key."""


class DifyConnectionError(DifyError):
    """Raised on network, SSL, or timeout errors communicating with Dify."""


class DifyUnsupportedAppError(DifyError):
    """Raised when the Dify app mode does not support /chat-messages."""


class DifyConversationNotFoundError(DifyError):
    """Raised when Dify reports that a conversation_id no longer exists."""


class DifyResponseError(DifyError):
    """Raised when Dify returns an application-level or malformed response error."""


@dataclass(slots=True)
class DifyAppInfo:
    """Metadata describing a Dify application."""

    name: str | None = None
    mode: str | None = None


@dataclass(slots=True)
class DifyStreamEvent:
    """Normalized event emitted while streaming a Dify chat message."""

    kind: str  # "delta" | "replace" | "end"
    text: str = ""
    conversation_id: str | None = None


def _is_conversation_not_found(status: int, code: str | None, message: str | None) -> bool:
    """Return True if an API error indicates an unknown or expired conversation ID."""
    code_lower = (code or "").lower()
    msg_lower = (message or "").lower()
    if code_lower in {"conversation_not_exists", "not_found"} and (
        "conversation" in msg_lower or code_lower == "conversation_not_exists"
    ):
        return True
    return status == 404 and "conversation" in msg_lower


def _parse_error_body(raw_body: str) -> tuple[str | None, str]:
    """Extract error code and human-readable message from a Dify JSON error payload."""
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return None, raw_body.strip() or "Unknown error"

    if isinstance(payload, dict):
        code = payload.get("code")
        message = payload.get("message") or payload.get("error") or raw_body
        return (str(code) if code is not None else None), str(message)

    return None, raw_body.strip() or "Unknown error"


def _raise_for_http_error(status: int, raw_body: str) -> None:
    """Translate an HTTP error response from Dify into a typed DifyError."""
    if status in (401, 403):
        raise DifyAuthError("Invalid Dify API key or unauthorized access")

    code, message = _parse_error_body(raw_body)
    if _is_conversation_not_found(status, code, message):
        raise DifyConversationNotFoundError(message)

    raise DifyResponseError(f"Dify API error ({status}): {message}")


class DifyClient:
    """Asynchronous client for Dify's /v1/chat-messages API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
        timeout: int,
    ) -> None:
        """Initialize the Dify API client."""
        self._session = session
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    def _headers(self) -> dict[str, str]:
        """Build HTTP request headers."""
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _build_chat_payload(
        self,
        *,
        query: str,
        inputs: dict[str, Any],
        user: str,
        conversation_id: str | None,
        response_mode: str,
    ) -> dict[str, Any]:
        """Construct the JSON body for POST /chat-messages."""
        return {
            "inputs": inputs,
            "query": query,
            "response_mode": response_mode,
            "conversation_id": conversation_id or "",
            "user": user,
        }

    async def _get_json(self, path: str) -> tuple[int, dict[str, Any] | None]:
        """Perform a GET request and return HTTP status and optional JSON dict."""
        url = f"{self._base_url}{path}"
        try:
            async with self._session.get(
                url,
                headers=self._headers(),
                timeout=self._timeout,
            ) as response:
                if response.status in (401, 403):
                    raise DifyAuthError("Invalid Dify API key or unauthorized access")
                if response.status == 404:
                    return 404, None
                if response.status >= 400:
                    body = await response.text()
                    _raise_for_http_error(response.status, body)
                data = await response.json(content_type=None)
                return response.status, data if isinstance(data, dict) else None
        except DifyError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DifyConnectionError(f"Failed to connect to Dify: {err}") from err

    async def async_validate_connection(self) -> DifyAppInfo:
        """Verify Dify reachability, API key validity, and app compatibility."""
        status, info = await self._get_json("/info")
        if status == 404:
            # Older self-hosted Dify versions may not expose /info; fall back to /parameters.
            status, params = await self._get_json("/parameters")
            if status == 404 or params is None:
                raise DifyConnectionError("Dify API endpoint not found at the configured URL")
            return DifyAppInfo()

        if info is None:
            return DifyAppInfo()

        mode = info.get("mode")
        if isinstance(mode, str) and mode in UNSUPPORTED_APP_MODES:
            raise DifyUnsupportedAppError(
                f"Dify app mode '{mode}' does not support /chat-messages"
            )

        name = info.get("name")
        return DifyAppInfo(
            name=name if isinstance(name, str) and name.strip() else None,
            mode=mode if isinstance(mode, str) else None,
        )

    async def async_chat_blocking(
        self,
        *,
        query: str,
        inputs: dict[str, Any],
        user: str,
        conversation_id: str | None = None,
    ) -> tuple[str, str | None]:
        """Send a chat message in blocking mode and return (answer, dify_conversation_id)."""
        url = f"{self._base_url}/chat-messages"
        payload = self._build_chat_payload(
            query=query,
            inputs=inputs,
            user=user,
            conversation_id=conversation_id,
            response_mode=RESPONSE_MODE_BLOCKING,
        )

        try:
            async with self._session.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=self._timeout,
            ) as response:
                raw_body = await response.text()
                if response.status >= 400:
                    _raise_for_http_error(response.status, raw_body)
        except DifyError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DifyConnectionError(f"Failed to communicate with Dify: {err}") from err

        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError as err:
            raise DifyResponseError("Invalid JSON response received from Dify") from err

        if not isinstance(data, dict):
            raise DifyResponseError("Unexpected response structure from Dify")

        answer = data.get("answer")
        if answer is None:
            raise DifyResponseError("Dify response missing 'answer' field")

        new_conv_id = data.get("conversation_id")
        return str(answer), (str(new_conv_id) if new_conv_id else None)

    async def async_chat_streaming(
        self,
        *,
        query: str,
        inputs: dict[str, Any],
        user: str,
        conversation_id: str | None = None,
    ) -> AsyncIterator[DifyStreamEvent]:
        """Send a chat message in SSE streaming mode and yield normalized events."""
        url = f"{self._base_url}/chat-messages"
        payload = self._build_chat_payload(
            query=query,
            inputs=inputs,
            user=user,
            conversation_id=conversation_id,
            response_mode=RESPONSE_MODE_STREAMING,
        )

        try:
            async with self._session.post(
                url,
                headers=self._headers(),
                json=payload,
                timeout=self._timeout,
            ) as response:
                if response.status >= 400:
                    raw_body = await response.text()
                    _raise_for_http_error(response.status, raw_body)

                # Buffer chunks manually to avoid aiohttp's 64 KB readline limit on large SSE payloads.
                buffer = ""
                async for chunk in response.content.iter_any():
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        event = self._parse_sse_line(line.rstrip("\r"))
                        if event is not None:
                            yield event

                if buffer.strip():
                    event = self._parse_sse_line(buffer.rstrip("\r"))
                    if event is not None:
                        yield event
        except DifyError:
            raise
        except (aiohttp.ClientError, TimeoutError) as err:
            raise DifyConnectionError(f"Failed to stream response from Dify: {err}") from err

    def _parse_sse_line(self, line: str) -> DifyStreamEvent | None:
        """Parse a single SSE line into a DifyStreamEvent if applicable."""
        if not line or line.startswith(":") or not line.startswith("data:"):
            return None

        raw_data = line[5:].lstrip()
        if not raw_data or raw_data == "[DONE]":
            return None

        try:
            payload = json.loads(raw_data)
        except json.JSONDecodeError:
            return None

        if not isinstance(payload, dict):
            return None

        event_type = payload.get("event")
        conv_id = payload.get("conversation_id")
        conv_id_str = str(conv_id) if conv_id else None

        if event_type == "error":
            status = int(payload.get("status") or 500)
            code = payload.get("code")
            message = payload.get("message") or "Unknown Dify streaming error"
            if _is_conversation_not_found(status, str(code) if code else None, str(message)):
                raise DifyConversationNotFoundError(str(message))
            raise DifyResponseError(str(message))

        if event_type in ("message", "agent_message"):
            answer = payload.get("answer")
            if isinstance(answer, str) and answer:
                return DifyStreamEvent(kind="delta", text=answer, conversation_id=conv_id_str)
            if conv_id_str:
                return DifyStreamEvent(kind="delta", text="", conversation_id=conv_id_str)
            return None

        if event_type == "message_replace":
            answer = payload.get("answer")
            return DifyStreamEvent(
                kind="replace",
                text=str(answer) if answer is not None else "",
                conversation_id=conv_id_str,
            )

        if event_type in ("message_end", "workflow_finished"):
            return DifyStreamEvent(kind="end", conversation_id=conv_id_str)

        return None
