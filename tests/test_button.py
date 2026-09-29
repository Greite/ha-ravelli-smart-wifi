"""Tests for the clock button."""

from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .fake_module import PATH_SET, FakeModule
from .helpers import entity_id_for


@pytest.mark.freeze_time("2026-09-29T16:57:30+00:00")
async def test_button_sets_the_clock_to_local_time(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """16:57 UTC on a Tuesday is 18:57 in Paris."""
    await hass.config.async_set_time_zone("Europe/Paris")
    fake_module.categories[4] = dict.fromkeys(range(59, 65), 0)
    entity_id = entity_id_for(hass, "button", "sync_clock")
    entry = er.async_get(hass).async_get(entity_id)
    assert entry.entity_category is EntityCategory.CONFIG

    await hass.services.async_call(
        "button", "press", {"entity_id": entity_id}, blocking=True
    )

    assert fake_module.categories[4] == {
        59: 2,
        60: 0x18,
        61: 0x57,
        62: 0x29,
        63: 0x09,
        64: 0x26,
    }
    assert fake_module.count(PATH_SET) == 6
