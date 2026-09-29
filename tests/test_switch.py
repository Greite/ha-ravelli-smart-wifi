"""Tests for the schedule switch."""

from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .fake_module import FakeModule
from .helpers import entity_id_for

EVENING_RAW = [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"]


async def turn(hass: HomeAssistant, action: str) -> None:
    """Flip the switch."""
    await hass.services.async_call(
        "switch",
        action,
        {"entity_id": entity_id_for(hass, "switch", "schedule")},
        blocking=True,
    )


async def test_switch_flips_the_global_flag(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The programs travel with the flag and come back unchanged."""
    entity_id = entity_id_for(hass, "switch", "schedule")
    assert hass.states.get(entity_id).state == STATE_ON
    entry = er.async_get(hass).async_get(entity_id)
    assert entry.entity_category is EntityCategory.CONFIG

    await turn(hass, "turn_off")

    assert fake_module.schedule_enabled is False
    assert fake_module.programs[0] == EVENING_RAW
    assert hass.states.get(entity_id).state == STATE_OFF

    await turn(hass, "turn_on")

    assert fake_module.schedule_enabled is True
    assert fake_module.programs[0] == EVENING_RAW
    assert hass.states.get(entity_id).state == STATE_ON


async def test_switch_reports_a_write_the_module_ignored(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The switch does not show a state the stove does not have."""
    fake_module.ignore_schedule_writes = True

    with pytest.raises(HomeAssistantError) as err:
        await turn(hass, "turn_off")

    assert err.value.translation_key == "schedule_mismatch"
    state = hass.states.get(entity_id_for(hass, "switch", "schedule"))
    assert state.state == STATE_ON
