"""Tests for the sensors and the device."""

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_MODEL,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import HOST, MAC, FakeModule
from .helpers import advance, entity_id_for

STATUS_OPTIONS = [
    "off",
    "pellet_loading",
    "ignition",
    "waiting_flame",
    "flame_present",
    "working",
    "final_cleaning",
    "eco_stop",
    "alarm",
    "alarm_memory",
]


async def test_sensors_of_an_idle_stove(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The capture of an idle stove at 22 degrees."""
    status = hass.states.get(entity_id_for(hass, "sensor", "status"))
    assert status.state == "off"
    assert status.attributes["raw_value"] == 0
    assert status.attributes["options"] == STATUS_OPTIONS
    assert status.attributes["device_class"] == "enum"

    alarm = hass.states.get(entity_id_for(hass, "sensor", "alarm"))
    assert alarm.state == "none"
    assert alarm.attributes["raw_value"] == 0

    ambient = hass.states.get(entity_id_for(hass, "sensor", "ambient_temperature"))
    assert ambient.state == "22.0"
    assert ambient.attributes["unit_of_measurement"] == "°C"
    assert ambient.attributes["device_class"] == "temperature"
    assert ambient.attributes["state_class"] == "measurement"

    flue = hass.states.get(entity_id_for(hass, "sensor", "flue_temperature"))
    assert flue.state == "0"
    assert flue.attributes["unit_of_measurement"] == "°C"


@pytest.mark.parametrize("key", ["extractor_speed", "wifi_signal"])
async def test_sensors_that_are_off_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry, key: str
) -> None:
    """They exist in the registry, disabled, and have no state."""
    entity_id = entity_id_for(hass, "sensor", key)

    entry = er.async_get(hass).async_get(entity_id)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("enable_all_entities")
async def test_sensors_once_enabled(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The extractor has no unit yet; the signal is in dBm."""
    extractor = hass.states.get(entity_id_for(hass, "sensor", "extractor_speed"))
    assert extractor.state == "0"
    assert "unit_of_measurement" not in extractor.attributes

    signal_id = entity_id_for(hass, "sensor", "wifi_signal")
    signal = hass.states.get(signal_id)
    assert signal.state == "-74"
    assert signal.attributes["unit_of_measurement"] == "dBm"
    assert signal.attributes["device_class"] == "signal_strength"
    entry = er.async_get(hass).async_get(signal_id)
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_status_follows_the_stove(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The next poll shows the new status and temperatures."""
    fake_module.common[2] = 5
    fake_module.categories[2].update({0: 43, 4: 180})

    await advance(hass, freezer)

    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "working"
    ambient = hass.states.get(entity_id_for(hass, "sensor", "ambient_temperature"))
    assert ambient.state == "21.5"
    flue = hass.states.get(entity_id_for(hass, "sensor", "flue_temperature"))
    assert flue.state == "180"


async def test_unknown_status_code(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A code outside the table gives the unknown state and keeps the code."""
    fake_module.common[2] = 42

    await advance(hass, freezer)

    status = hass.states.get(entity_id_for(hass, "sensor", "status"))
    assert status.state == STATE_UNKNOWN
    assert status.attributes["raw_value"] == 42


async def test_alarm_message(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The module sends the alarm text itself."""
    fake_module.common.update({2: 8, 3: 5})
    fake_module.extra["alr"] = "AL05 NO IGNITION"

    await advance(hass, freezer)

    alarm = hass.states.get(entity_id_for(hass, "sensor", "alarm"))
    assert alarm.state == "AL05 NO IGNITION"
    assert alarm.attributes["raw_value"] == 5
    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "alarm"


async def test_alarm_without_a_text_shows_its_code(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Never "none" while the alarm register is set."""
    alarm_id = entity_id_for(hass, "sensor", "alarm")
    assert hass.states.get(alarm_id).state == "none"
    fake_module.common.update({2: 8, 3: 5})
    fake_module.extra["alr"] = ""

    await advance(hass, freezer)

    assert hass.states.get(alarm_id).state == "code 5"


async def test_missing_register_gives_an_unknown_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The other sensors keep working."""
    del fake_module.categories[2][0]
    del fake_module.categories[2][4]

    await advance(hass, freezer)

    ambient = hass.states.get(entity_id_for(hass, "sensor", "ambient_temperature"))
    assert ambient.state == STATE_UNKNOWN
    flue = hass.states.get(entity_id_for(hass, "sensor", "flue_temperature"))
    assert flue.state == STATE_UNKNOWN
    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "off"


async def test_sensors_follow_the_availability_of_the_module(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unplugging the stove makes the entities unavailable, not stale."""
    entity_id = entity_id_for(hass, "sensor", "status")

    fake_module.error = aiohttp.ClientConnectionError()
    await advance(hass, freezer)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    fake_module.error = None
    await advance(hass, freezer)
    assert hass.states.get(entity_id).state == "off"


async def test_device(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """One device per module, tied to its MAC address."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, MAC), init_integration.entry_id
    )

    assert device is not None
    assert device.name == "Ravelli AIR-RDS"
    assert device.manufacturer == "Ravelli"
    assert device.model == "AIR-RDS"
    assert device.sw_version == "0.51"
    assert device.configuration_url == f"http://{HOST}"
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, MAC)}


async def test_entry_without_a_mac_address(
    hass: HomeAssistant, fake_module: FakeModule
) -> None:
    """The entry id replaces the MAC address in the identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ravelli AIR-RDS",
        data={CONF_HOST: HOST, CONF_MODEL: 7, CONF_MAC: None},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_status"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "off"
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    assert device is not None
    assert device.connections == set()
