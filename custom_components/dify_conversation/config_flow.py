"""Config flow for Dify Conversation integration."""

from __future__ import annotations

from collections.abc import Mapping
import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from . import get_entry_config
from .client import (
    DifyAppInfo,
    DifyAuthError,
    DifyClient,
    DifyConnectionError,
    DifyUnsupportedAppError,
)
from .const import (
    CONF_API_KEY,
    CONF_APP_MODE,
    CONF_BASE_URL,
    CONF_CLEAN_RESPONSE,
    CONF_CUSTOM_INPUTS,
    CONF_RESPONSE_MODE,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
    DEFAULT_BASE_URL,
    DEFAULT_CLEAN_RESPONSE,
    DEFAULT_CUSTOM_INPUTS,
    DEFAULT_NAME,
    DEFAULT_RESPONSE_MODE,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    RESPONSE_MODE_BLOCKING,
    RESPONSE_MODE_STREAMING,
)
from .helpers import InvalidJsonError, validate_custom_inputs_json

_LOGGER = logging.getLogger(__name__)


def _build_schema(defaults: Mapping[str, Any], include_name: bool) -> vol.Schema:
    """Build the shared Voluptuous schema for config and options flows."""
    fields: dict[Any, Any] = {}

    if include_name:
        fields[vol.Optional(CONF_NAME, default=defaults.get(CONF_NAME, ""))] = TextSelector(
            TextSelectorConfig(type=TextSelectorType.TEXT)
        )

    fields.update(
        {
            vol.Required(
                CONF_BASE_URL,
                default=defaults.get(CONF_BASE_URL, DEFAULT_BASE_URL),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.URL)),
            vol.Required(
                CONF_API_KEY,
                default=defaults.get(CONF_API_KEY, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Required(
                CONF_VERIFY_SSL,
                default=defaults.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
            ): BooleanSelector(),
            vol.Required(
                CONF_TIMEOUT,
                default=defaults.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=5,
                    max=600,
                    step=1,
                    unit_of_measurement="s",
                    mode=NumberSelectorMode.BOX,
                )
            ),
            vol.Required(
                CONF_RESPONSE_MODE,
                default=defaults.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE),
            ): SelectSelector(
                SelectSelectorConfig(
                    options=[RESPONSE_MODE_STREAMING, RESPONSE_MODE_BLOCKING],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key=CONF_RESPONSE_MODE,
                )
            ),
            vol.Required(
                CONF_CLEAN_RESPONSE,
                default=defaults.get(CONF_CLEAN_RESPONSE, DEFAULT_CLEAN_RESPONSE),
            ): BooleanSelector(),
            vol.Optional(
                CONF_CUSTOM_INPUTS,
                default=defaults.get(CONF_CUSTOM_INPUTS, DEFAULT_CUSTOM_INPUTS),
            ): TextSelector(
                TextSelectorConfig(
                    multiline=True,
                    type=TextSelectorType.TEXT,
                )
            ),
        }
    )

    return vol.Schema(fields)


async def _async_validate_user_input(
    hass: HomeAssistant,
    user_input: dict[str, Any],
) -> tuple[dict[str, str], DifyAppInfo | None]:
    """Validate custom JSON syntax and Dify API connectivity."""
    errors: dict[str, str] = {}

    try:
        validate_custom_inputs_json(user_input.get(CONF_CUSTOM_INPUTS))
    except InvalidJsonError as err:
        errors[CONF_CUSTOM_INPUTS] = err.error_key
        return errors, None

    verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)
    client = DifyClient(
        session=session,
        base_url=str(user_input[CONF_BASE_URL]),
        api_key=str(user_input[CONF_API_KEY]),
        timeout=int(user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
    )

    try:
        app_info = await client.async_validate_connection()
    except DifyAuthError:
        errors["base"] = "invalid_auth"
    except DifyUnsupportedAppError:
        errors["base"] = "unsupported_app_mode"
    except DifyConnectionError:
        errors["base"] = "cannot_connect"
    except Exception:
        _LOGGER.exception("Unexpected error validating Dify connection")
        errors["base"] = "unknown"
    else:
        return errors, app_info

    return errors, None


class DifyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Dify Conversation."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle the initial configuration step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors, app_info = await _async_validate_user_input(self.hass, user_input)
            if not errors:
                custom_name = str(user_input.get(CONF_NAME, "")).strip()
                title = custom_name or (app_info.name if app_info and app_info.name else DEFAULT_NAME)

                entry_data = {
                    CONF_BASE_URL: str(user_input[CONF_BASE_URL]).rstrip("/"),
                    CONF_API_KEY: str(user_input[CONF_API_KEY]),
                    CONF_VERIFY_SSL: bool(user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)),
                    CONF_TIMEOUT: int(user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
                    CONF_RESPONSE_MODE: str(
                        user_input.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE)
                    ),
                    CONF_CLEAN_RESPONSE: bool(
                        user_input.get(CONF_CLEAN_RESPONSE, DEFAULT_CLEAN_RESPONSE)
                    ),
                    CONF_CUSTOM_INPUTS: user_input.get(CONF_CUSTOM_INPUTS) or DEFAULT_CUSTOM_INPUTS,
                    CONF_APP_MODE: app_info.mode if app_info else None,
                }
                return self.async_create_entry(title=title, data=entry_data)

        defaults = user_input or {}
        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(defaults, include_name=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return DifyOptionsFlowHandler()


class DifyOptionsFlowHandler(OptionsFlow):
    """Handle options flow for Dify Conversation."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the Dify Conversation options."""
        errors: dict[str, str] = {}
        current = get_entry_config(self.config_entry)

        if user_input is not None:
            errors, app_info = await _async_validate_user_input(self.hass, user_input)
            if not errors:
                options_data = {
                    CONF_BASE_URL: str(user_input[CONF_BASE_URL]).rstrip("/"),
                    CONF_API_KEY: str(user_input[CONF_API_KEY]),
                    CONF_VERIFY_SSL: bool(user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL)),
                    CONF_TIMEOUT: int(user_input.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
                    CONF_RESPONSE_MODE: str(
                        user_input.get(CONF_RESPONSE_MODE, DEFAULT_RESPONSE_MODE)
                    ),
                    CONF_CLEAN_RESPONSE: bool(
                        user_input.get(CONF_CLEAN_RESPONSE, DEFAULT_CLEAN_RESPONSE)
                    ),
                    CONF_CUSTOM_INPUTS: user_input.get(CONF_CUSTOM_INPUTS) or DEFAULT_CUSTOM_INPUTS,
                    CONF_APP_MODE: app_info.mode if app_info else current.get(CONF_APP_MODE),
                }
                return self.async_create_entry(title="", data=options_data)

        defaults = user_input or current
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(defaults, include_name=False),
            errors=errors,
        )
