"""Unit tests for conversation entity and config flow."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tests.ha_stubs import install_stubs

install_stubs()

from homeassistant.components import conversation  # noqa: E402
from homeassistant.helpers.intent import IntentResponseErrorCode  # noqa: E402

from custom_components.dify_conversation import DifyRuntimeData  # noqa: E402
from custom_components.dify_conversation.client import (  # noqa: E402
    DifyAppInfo,
    DifyConversationNotFoundError,
    DifyResponseError,
    DifyStreamEvent,
)
from custom_components.dify_conversation.config_flow import (  # noqa: E402
    DifyConfigFlow,
    DifyOptionsFlowHandler,
)
from custom_components.dify_conversation.const import (  # noqa: E402
    CONF_API_KEY,
    CONF_BASE_URL,
    CONF_CLEAN_RESPONSE,
    CONF_CUSTOM_INPUTS,
    CONF_RESPONSE_MODE,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
    RESPONSE_MODE_BLOCKING,
    RESPONSE_MODE_STREAMING,
)
from custom_components.dify_conversation.conversation import DifyConversationEntity  # noqa: E402


@dataclass
class _FakeCredential:
    auth_provider_type: str
    data: dict[str, str]


@dataclass
class _FakeUser:
    id: str
    name: str
    credentials: list[_FakeCredential] = field(default_factory=list)


class _FakeAuth:
    def __init__(self, users: dict[str, _FakeUser]) -> None:
        self._users = users

    async def async_get_user(self, user_id: str) -> _FakeUser | None:
        return self._users.get(user_id)


class _FakeDeviceRegistry:
    def __init__(self, devices: dict[str, SimpleNamespace]) -> None:
        self._devices = devices

    def async_get(self, device_id: str):
        return self._devices.get(device_id)


class _FakeAreaRegistry:
    def __init__(self, areas: dict[str, SimpleNamespace]) -> None:
        self._areas = areas

    def async_get_area(self, area_id: str):
        return self._areas.get(area_id)


class _FakeHass:
    def __init__(
        self,
        users: dict[str, _FakeUser] | None = None,
        devices: dict[str, SimpleNamespace] | None = None,
        areas: dict[str, SimpleNamespace] | None = None,
    ) -> None:
        self.auth = _FakeAuth(users or {})
        self.device_registry = _FakeDeviceRegistry(devices or {})
        self.area_registry = _FakeAreaRegistry(areas or {})


class _MockDifyClient:
    def __init__(self) -> None:
        self.streaming_calls: list[dict] = []
        self.blocking_calls: list[dict] = []
        self.stream_outcomes: list[list[DifyStreamEvent] | Exception] = []
        self.blocking_outcomes: list[tuple[str, str | None] | Exception] = []

    async def async_chat_streaming(self, **kwargs):
        self.streaming_calls.append(kwargs)
        outcome = self.stream_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        for event in outcome:
            yield event

    async def async_chat_blocking(self, **kwargs):
        self.blocking_calls.append(kwargs)
        outcome = self.blocking_outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _make_entry(
    client: _MockDifyClient,
    *,
    response_mode: str = RESPONSE_MODE_STREAMING,
    clean_response: bool = False,
    custom_inputs: str = "{}",
) -> SimpleNamespace:
    return SimpleNamespace(
        entry_id="entry-1",
        title="Dify Assistant",
        data={
            CONF_BASE_URL: "https://api.dify.ai/v1",
            CONF_API_KEY: "app-secret",
            CONF_CUSTOM_INPUTS: custom_inputs,
            CONF_RESPONSE_MODE: response_mode,
            CONF_CLEAN_RESPONSE: clean_response,
        },
        options={},
        runtime_data=DifyRuntimeData(client=client, app_mode="chat"),  # type: ignore[arg-type]
    )


class TestDifyConversationEntity(unittest.IsolatedAsyncioTestCase):
    """Tests for conversation handling, ID mapping, templates, and continue_conversation."""

    async def test_multi_turn_mapping_and_template_variables(self) -> None:
        client = _MockDifyClient()
        client.stream_outcomes = [
            [
                DifyStreamEvent(kind="delta", text="请问要调到多少度？\n", conversation_id="dify-conv-1"),
                DifyStreamEvent(kind="end", conversation_id="dify-conv-1"),
            ],
            [
                DifyStreamEvent(kind="delta", text="好的，已设为 25 度。", conversation_id="dify-conv-1"),
                DifyStreamEvent(kind="end", conversation_id="dify-conv-1"),
            ],
        ]
        custom_inputs = (
            '{"user_id": "$user_id", "user_name": "$user_name", '
            '"uuid": "$ha_user_uuid", "device": "$device_id", '
            '"device_name": "$device_name", "area": "$area_name", '
            '"satellite": "$satellite_id", "lang": "$language", "query": "ignored"}'
        )
        entity = DifyConversationEntity(
            _make_entry(client, custom_inputs=custom_inputs)  # type: ignore[arg-type]
        )
        entity.hass = _FakeHass(
            users={
                "uuid-123": _FakeUser(
                    id="uuid-123",
                    name="Wei Display",
                    credentials=[_FakeCredential("homeassistant", {"username": "wei_login"})],
                )
            },
            devices={
                "dev-1": SimpleNamespace(name="Speaker", name_by_user="Living Speaker", area_id="area-1")
            },
            areas={"area-1": SimpleNamespace(name="Living Room")},
        )

        # Turn 1: new conversation -> Dify receives conversation_id=None, trailing ？\n triggers continue.
        chat_log = conversation.ChatLog(conversation_id="ha-conv-1")
        user_input_1 = conversation.ConversationInput(
            text="打开空调",
            context=SimpleNamespace(user_id="uuid-123"),
            conversation_id="ha-conv-1",
            device_id="dev-1",
            satellite_id="assist_satellite.living",
            language="zh-CN",
        )
        res1 = await entity._async_handle_message(user_input_1, chat_log)

        self.assertTrue(res1.continue_conversation)
        self.assertEqual(client.streaming_calls[0]["conversation_id"], None)
        self.assertEqual(client.streaming_calls[0]["user"], "wei_login")
        self.assertEqual(
            client.streaming_calls[0]["inputs"],
            {
                "user_id": "wei_login",
                "user_name": "Wei Display",
                "uuid": "uuid-123",
                "device": "dev-1",
                "device_name": "Living Speaker",
                "area": "Living Room",
                "satellite": "assist_satellite.living",
                "lang": "zh-CN",
                "query": "打开空调",
            },
        )

        # Turn 2: same HA conversation_id -> reuses dify-conv-1; period ends continue_conversation.
        user_input_2 = conversation.ConversationInput(
            text="25度",
            context=SimpleNamespace(user_id="uuid-123"),
            conversation_id="ha-conv-1",
            device_id="dev-1",
            satellite_id="assist_satellite.living",
            language="zh-CN",
        )
        res2 = await entity._async_handle_message(user_input_2, chat_log)
        self.assertFalse(res2.continue_conversation)
        self.assertEqual(client.streaming_calls[1]["conversation_id"], "dify-conv-1")

    async def test_empty_user_context_and_stale_conversation_recovery(self) -> None:
        client = _MockDifyClient()
        # Prime cache with stale mapping via turn 1, then fail turn 2 with 404 and recover.
        client.stream_outcomes = [
            [
                DifyStreamEvent(kind="delta", text="Hi!", conversation_id="stale-dify-id"),
                DifyStreamEvent(kind="end", conversation_id="stale-dify-id"),
            ],
            DifyConversationNotFoundError("Conversation Not Exists"),
            [
                DifyStreamEvent(kind="delta", text="Fresh start?", conversation_id="fresh-dify-id"),
                DifyStreamEvent(kind="end", conversation_id="fresh-dify-id"),
            ],
        ]
        entity = DifyConversationEntity(
            _make_entry(client, custom_inputs='{"user_id": "$user_id", "user_name": "$user_name"}')  # type: ignore[arg-type]
        )
        entity.hass = _FakeHass()

        chat_log = conversation.ChatLog(conversation_id="ha-conv-2")
        inp = conversation.ConversationInput(
            text="Hello",
            context=SimpleNamespace(user_id=None),
            conversation_id="ha-conv-2",
            device_id=None,
            satellite_id="assist_satellite.bedroom",
            language="en",
        )

        await entity._async_handle_message(inp, chat_log)
        self.assertEqual(client.streaming_calls[0]["user"], "assist_satellite.bedroom")
        self.assertEqual(client.streaming_calls[0]["inputs"], {"user_id": "", "user_name": ""})

        res2 = await entity._async_handle_message(inp, chat_log)
        self.assertTrue(res2.continue_conversation)
        # Call 1 used stale-dify-id, retry call 2 used None.
        self.assertEqual(client.streaming_calls[1]["conversation_id"], "stale-dify-id")
        self.assertIsNone(client.streaming_calls[2]["conversation_id"])
        self.assertEqual(entity._conversation_map.get("ha-conv-2"), "fresh-dify-id")

    async def test_blocking_mode_with_cleanup_and_error_handling(self) -> None:
        client = _MockDifyClient()
        client.blocking_outcomes = [
            ("<think>secret</think>**All set**!", "dify-blk-1"),
            DifyResponseError("Upstream error"),
        ]
        entity = DifyConversationEntity(
            _make_entry(client, response_mode=RESPONSE_MODE_BLOCKING, clean_response=True)  # type: ignore[arg-type]
        )
        entity.hass = _FakeHass()

        chat_log = conversation.ChatLog(conversation_id="ha-blk")
        inp = conversation.ConversationInput(
            text="Status",
            context=SimpleNamespace(user_id=None),
            conversation_id="ha-blk",
            language="en",
        )
        res = await entity._async_handle_message(inp, chat_log)
        self.assertEqual(res.response.speech["plain"]["speech"], "All set!")
        self.assertFalse(res.continue_conversation)

        err_res = await entity._async_handle_message(inp, chat_log)
        self.assertEqual(err_res.response.error_code, IntentResponseErrorCode.UNKNOWN)


class TestConfigAndOptionsFlow(unittest.IsolatedAsyncioTestCase):
    """Tests for ConfigFlow and OptionsFlow JSON validation and submission."""

    async def test_invalid_json_blocks_config_flow(self) -> None:
        flow = DifyConfigFlow()
        flow.hass = _FakeHass()  # type: ignore[assignment]

        res = await flow.async_step_user(
            {
                CONF_BASE_URL: "https://api.dify.ai/v1",
                CONF_API_KEY: "app-key",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 60,
                CONF_RESPONSE_MODE: RESPONSE_MODE_STREAMING,
                CONF_CLEAN_RESPONSE: False,
                CONF_CUSTOM_INPUTS: "{not valid json",
            }
        )
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["errors"], {CONF_CUSTOM_INPUTS: "invalid_json"})

    async def test_valid_config_flow_uses_dify_app_name(self) -> None:
        flow = DifyConfigFlow()
        flow.hass = _FakeHass()  # type: ignore[assignment]

        with patch(
            "custom_components.dify_conversation.config_flow.DifyClient.async_validate_connection",
            return_value=DifyAppInfo(name="My Smart Home", mode="chat"),
        ):
            res = await flow.async_step_user(
                {
                    CONF_BASE_URL: "https://api.dify.ai/v1/",
                    CONF_API_KEY: "app-key",
                    CONF_VERIFY_SSL: False,
                    CONF_TIMEOUT: 45,
                    CONF_RESPONSE_MODE: RESPONSE_MODE_STREAMING,
                    CONF_CLEAN_RESPONSE: True,
                    CONF_CUSTOM_INPUTS: '{"user_id": "$user_id"}',
                }
            )

        self.assertEqual(res["type"], "create_entry")
        self.assertEqual(res["title"], "My Smart Home")
        self.assertEqual(res["data"][CONF_BASE_URL], "https://api.dify.ai/v1")
        self.assertFalse(res["data"][CONF_VERIFY_SSL])

    async def test_options_flow_validates_json_object(self) -> None:
        options_flow = DifyOptionsFlowHandler()
        options_flow.hass = _FakeHass()  # type: ignore[assignment]
        options_flow.config_entry = SimpleNamespace(
            data={
                CONF_BASE_URL: "https://api.dify.ai/v1",
                CONF_API_KEY: "app-key",
            },
            options={},
        )

        res = await options_flow.async_step_init(
            {
                CONF_BASE_URL: "https://api.dify.ai/v1",
                CONF_API_KEY: "app-key",
                CONF_VERIFY_SSL: True,
                CONF_TIMEOUT: 60,
                CONF_RESPONSE_MODE: RESPONSE_MODE_STREAMING,
                CONF_CLEAN_RESPONSE: False,
                CONF_CUSTOM_INPUTS: '["not", "an", "object"]',
            }
        )
        self.assertEqual(res["type"], "form")
        self.assertEqual(res["errors"], {CONF_CUSTOM_INPUTS: "invalid_json_object"})


if __name__ == "__main__":
    unittest.main()
