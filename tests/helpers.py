"""Helpers shared by the tests."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import async_fire_time_changed

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import MAC


def entity_id_for(hass: HomeAssistant, platform: str, key: str) -> str:
    """Find an entity by its key, whatever its translated name is."""
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{MAC}_{key}")
    assert entity_id is not None, f"no {platform} entity for {key}"
    return entity_id


async def advance(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, seconds: int = 31
) -> None:
    """Move the clock forward and let the due timers run."""
    freezer.tick(timedelta(seconds=seconds))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
