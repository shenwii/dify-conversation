"""Lightweight stubs for Home Assistant, aiohttp, and voluptuous for unit testing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import sys
import types
from typing import Any


def install_stubs() -> None:
    """Install minimal module stubs into sys.modules when HA dependencies are absent."""
    if "aiohttp" not in sys.modules:
        aiohttp_mod = types.ModuleType("aiohttp")

        class ClientError(Exception):
            pass

        class ClientTimeout:
            def __init__(self, total: float | None = None) -> None:
                self.total = total

        class ClientSession:
            pass

        aiohttp_mod.ClientError = ClientError
        aiohttp_mod.ClientTimeout = ClientTimeout
        aiohttp_mod.ClientSession = ClientSession
        sys.modules["aiohttp"] = aiohttp_mod

    if "voluptuous" not in sys.modules:
        vol_mod = types.ModuleType("voluptuous")

        class _Marker:
            def __init__(self, key: str, default: Any = None) -> None:
                self.schema = key
                self.default = default

            def __hash__(self) -> int:
                return hash(self.schema)

            def __eq__(self, other: object) -> bool:
                return isinstance(other, _Marker) and self.schema == other.schema

        class Schema:
            def __init__(self, schema: dict[Any, Any]) -> None:
                self.schema = schema

        vol_mod.Schema = Schema
        vol_mod.Required = lambda key, default=None: _Marker(key, default)
        vol_mod.Optional = lambda key, default=None: _Marker(key, default)
        sys.modules["voluptuous"] = vol_mod

    if "homeassistant" in sys.modules:
        return

    ha = types.ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # homeassistant.const
    const_mod = types.ModuleType("homeassistant.const")
    const_mod.MATCH_ALL = "*"
    const_mod.CONF_NAME = "name"

    class Platform(str, Enum):
        CONVERSATION = "conversation"

    const_mod.Platform = Platform
    sys.modules["homeassistant.const"] = const_mod

    # homeassistant.core
    core_mod = types.ModuleType("homeassistant.core")

    class HomeAssistant:
        pass

    def callback(func: Any) -> Any:
        return func

    core_mod.HomeAssistant = HomeAssistant
    core_mod.callback = callback
    sys.modules["homeassistant.core"] = core_mod

    # homeassistant.config_entries
    ce_mod = types.ModuleType("homeassistant.config_entries")

    class ConfigEntry:
        def __class_getitem__(cls, item: Any) -> Any:
            return cls

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs: Any) -> None:
            super().__init_subclass__()

        def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: Any,
            errors: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
            }

    class OptionsFlow:
        config_entry: Any

        def async_create_entry(self, *, title: str, data: dict[str, Any]) -> dict[str, Any]:
            return {"type": "create_entry", "title": title, "data": data}

        def async_show_form(
            self,
            *,
            step_id: str,
            data_schema: Any,
            errors: dict[str, str] | None = None,
        ) -> dict[str, Any]:
            return {
                "type": "form",
                "step_id": step_id,
                "data_schema": data_schema,
                "errors": errors or {},
            }

    ce_mod.ConfigEntry = ConfigEntry
    ce_mod.ConfigFlow = ConfigFlow
    ce_mod.ConfigFlowResult = dict[str, Any]
    ce_mod.OptionsFlow = OptionsFlow
    sys.modules["homeassistant.config_entries"] = ce_mod

    # homeassistant.helpers.*
    helpers_mod = types.ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = helpers_mod

    aio_helper_mod = types.ModuleType("homeassistant.helpers.aiohttp_client")
    aio_helper_mod.async_get_clientsession = lambda hass, verify_ssl=True: None
    sys.modules["homeassistant.helpers.aiohttp_client"] = aio_helper_mod

    ep_mod = types.ModuleType("homeassistant.helpers.entity_platform")
    ep_mod.AddConfigEntryEntitiesCallback = Any
    sys.modules["homeassistant.helpers.entity_platform"] = ep_mod

    # selectors
    sel_mod = types.ModuleType("homeassistant.helpers.selector")
    for name in (
        "BooleanSelector",
        "NumberSelector",
        "NumberSelectorConfig",
        "SelectSelector",
        "SelectSelectorConfig",
        "TextSelector",
        "TextSelectorConfig",
    ):
        setattr(sel_mod, name, type(name, (), {"__init__": lambda self, *a, **kw: None}))

    class NumberSelectorMode(str, Enum):
        BOX = "box"

    class SelectSelectorMode(str, Enum):
        DROPDOWN = "dropdown"

    class TextSelectorType(str, Enum):
        TEXT = "text"
        URL = "url"
        PASSWORD = "password"

    sel_mod.NumberSelectorMode = NumberSelectorMode
    sel_mod.SelectSelectorMode = SelectSelectorMode
    sel_mod.TextSelectorType = TextSelectorType
    sys.modules["homeassistant.helpers.selector"] = sel_mod

    # device_registry & area_registry
    dr_mod = types.ModuleType("homeassistant.helpers.device_registry")

    class DeviceEntryType(str, Enum):
        SERVICE = "service"

    class DeviceInfo(dict):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    dr_mod.DeviceEntryType = DeviceEntryType
    dr_mod.DeviceInfo = DeviceInfo
    dr_mod.async_get = lambda hass: hass.device_registry
    sys.modules["homeassistant.helpers.device_registry"] = dr_mod

    ar_mod = types.ModuleType("homeassistant.helpers.area_registry")
    ar_mod.async_get = lambda hass: hass.area_registry
    sys.modules["homeassistant.helpers.area_registry"] = ar_mod

    # intent
    intent_mod = types.ModuleType("homeassistant.helpers.intent")

    class IntentResponseErrorCode(str, Enum):
        UNKNOWN = "unknown"

    class IntentResponse:
        def __init__(self, language: str = "en") -> None:
            self.language = language
            self.speech: dict[str, Any] = {}
            self.error_code: IntentResponseErrorCode | None = None
            self.error_message: str | None = None

        def async_set_speech(self, speech: str) -> None:
            self.speech = {"plain": {"speech": speech}}

        def async_set_error(self, code: IntentResponseErrorCode, message: str) -> None:
            self.error_code = code
            self.error_message = message

    intent_mod.IntentResponse = IntentResponse
    intent_mod.IntentResponseErrorCode = IntentResponseErrorCode
    sys.modules["homeassistant.helpers.intent"] = intent_mod

    # homeassistant.components.conversation
    comp_mod = types.ModuleType("homeassistant.components")
    sys.modules["homeassistant.components"] = comp_mod

    conv_mod = types.ModuleType("homeassistant.components.conversation")

    @dataclass
    class ConversationInput:
        text: str
        context: Any
        conversation_id: str | None = None
        device_id: str | None = None
        satellite_id: str | None = None
        language: str = "en"

    @dataclass
    class ConversationResult:
        response: IntentResponse
        conversation_id: str | None = None
        continue_conversation: bool = False

    @dataclass
    class AssistantContent:
        agent_id: str
        content: str = ""
        thinking_content: str = ""

    class ChatLog:
        def __init__(self, conversation_id: str) -> None:
            self.conversation_id = conversation_id
            self.content: list[AssistantContent] = []

        async def async_add_delta_content_stream(self, agent_id: str, stream: Any) -> Any:
            current: AssistantContent | None = None
            async for delta in stream:
                if "role" in delta:
                    current = AssistantContent(agent_id=agent_id)
                    self.content.append(current)
                if current is None:
                    current = AssistantContent(agent_id=agent_id)
                    self.content.append(current)
                if delta.get("thinking_content"):
                    current.thinking_content += delta["thinking_content"]
                if delta.get("content"):
                    current.content += delta["content"]
            if current is not None:
                yield current

    class ConversationEntity:
        hass: Any = None
        entity_id: str = "conversation.dify"

    def async_get_result_from_chat_log(
        user_input: ConversationInput,
        chat_log: ChatLog,
    ) -> ConversationResult:
        resp = IntentResponse(language=user_input.language)
        last_content = chat_log.content[-1].content if chat_log.content else ""
        resp.async_set_speech(last_content)
        return ConversationResult(
            response=resp,
            conversation_id=chat_log.conversation_id,
            continue_conversation=last_content.endswith(("?", "？", ";", ";")),
        )

    conv_mod.ConversationInput = ConversationInput
    conv_mod.ConversationResult = ConversationResult
    conv_mod.ChatLog = ChatLog
    conv_mod.ConversationEntity = ConversationEntity
    conv_mod.AssistantContentDeltaDict = dict[str, Any]
    conv_mod.async_get_result_from_chat_log = async_get_result_from_chat_log
    sys.modules["homeassistant.components.conversation"] = conv_mod
