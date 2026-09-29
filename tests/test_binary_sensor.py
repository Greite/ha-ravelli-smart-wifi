"""Tests for the binary sensors."""

from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import MAC, FakeModule
from .helpers import advance, entity_id_for


async def test_binary_sensors_of_an_idle_stove(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """No alarm and no pending update."""
    alarm = hass.states.get(entity_id_for(hass, "binary_sensor", "alarm"))
    assert alarm.state == STATE_OFF
    assert alarm.attributes["device_class"] == "problem"

    update_id = entity_id_for(hass, "binary_sensor", "firmware_update")
    update = hass.states.get(update_id)
    assert update.state == STATE_OFF
    assert update.attributes["device_class"] == "update"
    entry = er.async_get(hass).async_get(update_id)
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_flame_is_absent_when_the_board_does_not_report_it(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The AIR-RDS capture reports 255: no information."""
    registry = er.async_get(hass)

    assert registry.async_get_entity_id("binary_sensor", DOMAIN, f"{MAC}_flame") is None


async def test_flame_follows_the_module(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The entity exists as soon as the module reports a flame value."""
    fake_module.extra["flame"] = 0
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = entity_id_for(hass, "binary_sensor", "flame")
    assert hass.states.get(entity_id).state == STATE_OFF

    fake_module.extra["flame"] = 1
    await advance(hass, freezer)

    assert hass.states.get(entity_id).state == STATE_ON


@pytest.mark.parametrize(("status", "alarm_code"), [(8, 0), (9, 0), (5, 4), (8, 5)])
async def test_alarm(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
    status: int,
    alarm_code: int,
) -> None:
    """An alarm status or an alarm code turns the sensor on."""
    fake_module.common.update({2: status, 3: alarm_code})

    await advance(hass, freezer)

    alarm = hass.states.get(entity_id_for(hass, "binary_sensor", "alarm"))
    assert alarm.state == STATE_ON


async def test_firmware_update(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The system status is read every ten minutes."""
    fake_module.system["fwUpdate"] = True

    await advance(hass, freezer, seconds=601)

    update = hass.states.get(entity_id_for(hass, "binary_sensor", "firmware_update"))
    assert update.state == STATE_ON
