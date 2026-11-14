"""Conversation entity implementation for Dify Conversation."""

from __future__ import annotations

from collections.abc import AsyncGenerator
import logging
from typing import Any, Literal, override

from homeassistant.components import conversation
from homeassistant.const import MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar, device_registry as dr, intent
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import DifyConfigEntry, get_entry_config
from .client import DifyConversationNotFoundError, DifyError
from .const import (
    CONF_CLEAN_RESPONSE,
    CONF_CUSTOM_INPUTS,
    CONF_RESPONSE_MODE,
    DEFAULT_CLEAN_RESPONSE,
    DEFAULT_CUSTOM_INPUTS,
    DEFAULT_RESPONSE_MODE,
    DOMAIN,
    RESPONSE_MODE_BLOCKING,
)
from .helpers import (
    ConversationMappingCache,
    StreamingResponseCleaner,
    clean_response_text,
    render_custom_inputs,
    should_continue_conversation,
    validate_custom_inputs_json,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: DifyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Dify conversation entity from a config entry."""
    async_add_entities([DifyConversationEntity(config_entry)])


class DifyConversationEntity(conversation.ConversationEntity):
    """Dify Conversation agent entity."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: DifyConfigEntry) -> None:
        """Initialize the Dify conversation entity."""
        self._entry = entry
        self._attr_unique_id = entry.entry_id

        config = get_entry_config(entry)
        self._response_mode = str(config.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE))
        self._clean_response = bool(config.get(CONF_CLEAN_RESPONSE, DEFAULT_CLEAN_RESPONSE))
        self._template_inputs = validate_custom_inputs_json(
            config.get(CONF_CUSTOM_INPUTS, DEFAULT_CUSTOM_INPUTS)
        )
        self._conversation_map = ConversationMappingCache()

        app_mode = entry.runtime_data.app_mode
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Dify",
            model=app_mode or "Chat App",
            entry_type=dr.DeviceEntryType.SERVICE,
        )

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        """Return all languages since Dify models handle multilingual prompts."""
        return MATCH_ALL

    async def _async_build_template_variables(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> dict[str, str]:
        """Collect Home Assistant user, device, area, and conversation metadata."""
        ha_user_uuid = user_input.context.user_id or ""
        user_id = ""
        user_name = ""

        if ha_user_uuid:
            user = await self.hass.auth.async_get_user(ha_user_uuid)
            if user is not None:
                user_name = user.name or ""
                for cred in user.credentials:
                    if cred.auth_provider_type == "homeassistant":
                        username = cred.data.get("username")
                        if username:
                            user_id = str(username)
                        break

        device_id = user_input.device_id or ""
        device_name = ""
        area_id = ""
        area_name = ""

        if device_id:
            dev_reg = dr.async_get(self.hass)
            device = dev_reg.async_get(device_id)
            if device is not None:
                device_name = device.name_by_user or device.name or ""
                if device.area_id:
                    area_id = device.area_id
                    area_reg = ar.async_get(self.hass)
                    area = area_reg.async_get_area(area_id)
                    if area is not None:
                        area_name = area.name or ""

        return {
            "user_id": user_id,
            "user_name": user_name,
            "ha_user_uuid": ha_user_uuid,
            "device_id": device_id,
            "device_name": device_name,
            "area_id": area_id,
            "area_name": area_name,
            "satellite_id": user_input.satellite_id or "",
            "language": user_input.language or "",
            "conversation_id": chat_log.conversation_id,
            "query": user_input.text,
        }

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        """Process a user message via Dify and return the conversation result."""
        variables = await self._async_build_template_variables(user_input, chat_log)
        inputs = render_custom_inputs(self._template_inputs, variables, user_input.text)
        dify_user = (
            variables["user_id"]
            or variables["ha_user_uuid"]
            or variables["device_id"]
            or variables["satellite_id"]
            or "homeassistant"
        )

        ha_conv_id = chat_log.conversation_id
        dify_conv_id = self._conversation_map.get(ha_conv_id)

        try:
            final_text, new_dify_conv_id = await self._async_execute_dify_turn(
                query=user_input.text,
                inputs=inputs,
                dify_user=dify_user,
                ha_conv_id=ha_conv_id,
                dify_conv_id=dify_conv_id,
                chat_log=chat_log,
            )
        except DifyError as err:
            _LOGGER.error("Dify conversation failed: %s", err)
            intent_response = intent.IntentResponse(language=user_input.language)
            intent_response.async_set_error(
                intent.IntentResponseErrorCode.UNKNOWN,
                f"Error communicating with Dify: {err}",
            )
            return conversation.ConversationResult(
                response=intent_response,
                conversation_id=ha_conv_id,
                continue_conversation=False,
            )

        if new_dify_conv_id:
            self._conversation_map.set(ha_conv_id, new_dify_conv_id)

        result = conversation.async_get_result_from_chat_log(user_input, chat_log)
        result.continue_conversation = should_continue_conversation(final_text)
        return result

    async def _async_execute_dify_turn(
        self,
        *,
        query: str,
        inputs: dict[str, Any],
        dify_user: str,
        ha_conv_id: str,
        dify_conv_id: str | None,
        chat_log: conversation.ChatLog,
    ) -> tuple[str, str | None]:
        """Run a Dify turn, retrying once with an empty conversation_id if stale."""
        if self._response_mode == RESPONSE_MODE_BLOCKING:
            return await self._async_run_blocking(
                query=query,
                inputs=inputs,
                dify_user=dify_user,
                ha_conv_id=ha_conv_id,
                dify_conv_id=dify_conv_id,
                chat_log=chat_log,
            )

        return await self._async_run_streaming(
            query=query,
            inputs=inputs,
            dify_user=dify_user,
            ha_conv_id=ha_conv_id,
            dify_conv_id=dify_conv_id,
            chat_log=chat_log,
        )

    async def _async_run_blocking(
        self,
        *,
        query: str,
        inputs: dict[str, Any],
        dify_user: str,
        ha_conv_id: str,
        dify_conv_id: str | None,
        chat_log: conversation.ChatLog,
    ) -> tuple[str, str | None]:
        """Execute a blocking Dify request with stale conversation recovery."""
        client = self._entry.runtime_data.client
        try:
            answer, new_conv_id = await client.async_chat_blocking(
                query=query,
                inputs=inputs,
                user=dify_user,
                conversation_id=dify_conv_id,
            )
        except DifyConversationNotFoundError:
            if not dify_conv_id:
                raise
            _LOGGER.warning(
                "Dify conversation '%s' no longer exists; starting a fresh Dify session",
                dify_conv_id,
            )
            self._conversation_map.delete(ha_conv_id)
            answer, new_conv_id = await client.async_chat_blocking(
                query=query,
                inputs=inputs,
                user=dify_user,
                conversation_id=None,
            )

        final_text = clean_response_text(answer) if self._clean_response else answer

        async def _single_delta() -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
            yield {"role": "assistant", "content": final_text}

        async for _ in chat_log.async_add_delta_content_stream(
            self.entity_id,
            _single_delta(),
        ):
            pass

        return final_text, new_conv_id

    async def _async_run_streaming(
        self,
        *,
        query: str,
        inputs: dict[str, Any],
        dify_user: str,
        ha_conv_id: str,
        dify_conv_id: str | None,
        chat_log: conversation.ChatLog,
    ) -> tuple[str, str | None]:
        """Execute a streaming Dify request with stale conversation recovery."""
        client = self._entry.runtime_data.client
        cleaner = StreamingResponseCleaner(clean_response=self._clean_response)
        visible_parts: list[str] = []
        raw_parts: list[str] = []
        captured_conv_id: str | None = None
        replaced = False

        async def _delta_stream() -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
            nonlocal captured_conv_id, replaced
            started_role = False

            async def _consume(conv_id: str | None) -> AsyncGenerator[conversation.AssistantContentDeltaDict]:
                nonlocal captured_conv_id, replaced, started_role
                async for event in client.async_chat_streaming(
                    query=query,
                    inputs=inputs,
                    user=dify_user,
                    conversation_id=conv_id,
                ):
                    if event.conversation_id:
                        captured_conv_id = event.conversation_id

                    if event.kind == "delta" and event.text:
                        raw_parts.append(event.text)
                        visible_delta, thinking_delta = cleaner.feed(event.text)
                        delta_dict: conversation.AssistantContentDeltaDict = {}
                        if not started_role and (visible_delta or thinking_delta):
                            delta_dict["role"] = "assistant"
                            started_role = True
                        if thinking_delta:
                            delta_dict["thinking_content"] = thinking_delta
                        if visible_delta:
                            visible_parts.append(visible_delta)
                            delta_dict["content"] = visible_delta
                        if delta_dict:
                            yield delta_dict

                    elif event.kind == "replace":
                        replaced = True
                        raw_parts.clear()
                        raw_parts.append(event.text)
                        cleaned = (
                            clean_response_text(event.text)
                            if self._clean_response
                            else event.text
                        )
                        visible_parts.clear()
                        visible_parts.append(cleaned)
                        started_role = True
                        yield {"role": "assistant", "content": cleaned}

            try:
                async for delta in _consume(dify_conv_id):
                    yield delta
            except DifyConversationNotFoundError:
                if not dify_conv_id or started_role:
                    raise
                _LOGGER.warning(
                    "Dify conversation '%s' no longer exists; starting a fresh Dify session",
                    dify_conv_id,
                )
                self._conversation_map.delete(ha_conv_id)
                async for delta in _consume(None):
                    yield delta

            if not replaced:
                tail_visible, tail_thinking = cleaner.finish()
                tail_delta: conversation.AssistantContentDeltaDict = {}
                if not started_role and (tail_visible or tail_thinking):
                    tail_delta["role"] = "assistant"
                    started_role = True
                if tail_thinking:
                    tail_delta["thinking_content"] = tail_thinking
                if tail_visible:
                    visible_parts.append(tail_visible)
                    tail_delta["content"] = tail_visible
                if tail_delta:
                    yield tail_delta

            if not started_role:
                yield {"role": "assistant", "content": ""}

        async for _ in chat_log.async_add_delta_content_stream(
            self.entity_id,
            _delta_stream(),
        ):
            pass

        final_text = "".join(visible_parts)
        return final_text, captured_conv_id
