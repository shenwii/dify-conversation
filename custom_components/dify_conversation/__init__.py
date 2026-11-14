"""The Dify Conversation integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import DifyClient
from .const import (
    CONF_API_KEY,
    CONF_APP_MODE,
    CONF_BASE_URL,
    CONF_TIMEOUT,
    CONF_VERIFY_SSL,
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    DEFAULT_VERIFY_SSL,
)

PLATFORMS: list[Platform] = [Platform.CONVERSATION]


@dataclass(slots=True)
class DifyRuntimeData:
    """Runtime data stored on a Dify Conversation config entry."""

    client: DifyClient
    app_mode: str | None


type DifyConfigEntry = ConfigEntry[DifyRuntimeData]


def get_entry_config(entry: ConfigEntry) -> dict[str, Any]:
    """Return merged config entry data and options (options take precedence)."""
    return {**entry.data, **entry.options}


async def async_setup_entry(hass: HomeAssistant, entry: DifyConfigEntry) -> bool:
    """Set up Dify Conversation from a config entry."""
    config = get_entry_config(entry)
    verify_ssl = bool(config.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
    session = async_get_clientsession(hass, verify_ssl=verify_ssl)

    client = DifyClient(
        session=session,
        base_url=str(config.get(CONF_BASE_URL, DEFAULT_BASE_URL)),
        api_key=str(config[CONF_API_KEY]),
        timeout=int(config.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
    )

    entry.runtime_data = DifyRuntimeData(
        client=client,
        app_mode=config.get(CONF_APP_MODE),
    )

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DifyConfigEntry) -> bool:
    """Unload a Dify Conversation config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: DifyConfigEntry) -> None:
    """Reload config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)
