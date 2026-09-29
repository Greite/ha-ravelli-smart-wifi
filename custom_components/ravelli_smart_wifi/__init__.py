"""Ravelli Smart Wi-Fi integration."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import WinetClient, WinetError
from .const import DOMAIN, ISSUE_URL
from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .models import SUPPORTED_MODELS
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.CALENDAR,
    Platform.CLIMATE,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions once, whatever the number of stoves."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RavelliConfigEntry) -> bool:
    """Set one stove up."""
    client = WinetClient(async_get_clientsession(hass), entry.data[CONF_HOST])
    try:
        info = await client.get_info()
    except WinetError as err:
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN, translation_key="cannot_connect"
        ) from err
    code = info.get("model")
    model = SUPPORTED_MODELS.get(code) if isinstance(code, int) else None
    if model is None:
        raise ConfigEntryError(
            translation_domain=DOMAIN,
            translation_key="unsupported_model",
            translation_placeholders={"model": str(code), "issue_url": ISSUE_URL},
        )
    coordinator = RavelliCoordinator(hass, entry, client, model)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RavelliConfigEntry) -> bool:
    """Unload one stove."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
