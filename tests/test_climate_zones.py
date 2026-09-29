"""Tests for the ducting and water thermostats."""

from typing import Any

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import HOST, MAC, PATH_GET, PATH_SET, FakeModule
from .helpers import entity_id_for


async def setup_model(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, model: int
) -> FakeModule:
    """Set the integration up against a stove of another model."""
    module = FakeModule(model=model)
    module.install(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ravelli",
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_MODEL: model, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return module


def climate(hass: HomeAssistant, key: str) -> State:
    """Return the state of one thermostat."""
    state = hass.states.get(entity_id_for(hass, "climate", key))
    assert state is not None
    return state


def exists(hass: HomeAssistant, key: str) -> bool:
    """Tell whether a thermostat was created."""
    registry = er.async_get(hass)
    return registry.async_get_entity_id("climate", DOMAIN, f"{MAC}_{key}") is not None


async def call(hass: HomeAssistant, key: str, action: str, **data: Any) -> None:
    """Call a climate action on one thermostat."""
    await hass.services.async_call(
        "climate",
        action,
        {"entity_id": entity_id_for(hass, "climate", key), **data},
        blocking=True,
    )


@pytest.mark.parametrize("key", ["duct_right", "duct_left"])
async def test_ducting_is_off_by_default(
    hass: HomeAssistant, init_integration: MockConfigEntry, key: str
) -> None:
    """The module does not tell whether the stove has ducting."""
    entity_id = entity_id_for(hass, "climate", key)

    entry = er.async_get(hass).async_get(entity_id)
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("enable_all_entities")
async def test_ducting_that_is_off(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Raw 5 is off; raw 0 is a probe without a reading."""
    state = climate(hass, "duct_right")

    assert state.state == "off"
    assert state.attributes["hvac_modes"] == ["heat", "off"]
    assert state.attributes["temperature"] is None
    assert state.attributes["current_temperature"] is None
    assert state.attributes["min_temp"] == 7
    assert state.attributes["max_temp"] == 41
    assert state.attributes["preset_mode"] == "none"
    assert state.attributes["preset_modes"] == ["none", "external_thermostat"]
    assert "fan_modes" not in state.attributes
    assert "hvac_action" not in state.attributes


@pytest.mark.usefixtures("enable_all_entities")
async def test_ducting_in_use(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Right at 22 degrees, left on the external thermostat."""
    fake_module.categories[6] = {24: 21, 25: 19, 184: 22, 185: 6}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    right = climate(hass, "duct_right")
    assert right.state == "heat"
    assert right.attributes["temperature"] == 22
    assert right.attributes["current_temperature"] == 21
    assert right.attributes["preset_mode"] == "none"

    left = climate(hass, "duct_left")
    assert left.state == "heat"
    assert left.attributes["temperature"] is None
    assert left.attributes["current_temperature"] == 19
    assert left.attributes["preset_mode"] == "external_thermostat"


@pytest.mark.usefixtures("enable_all_entities")
async def test_ducting_commands(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Off writes 5, the external thermostat writes 6, on restores the target."""
    fake_module.categories[6] = {24: 21, 25: 19, 184: 22, 185: 22}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await call(hass, "duct_right", "set_temperature", temperature=24)
    assert fake_module.categories[6][184] == 24
    assert fake_module.categories[6][185] == 22

    await call(hass, "duct_right", "turn_off")
    assert fake_module.categories[6][184] == 5
    assert climate(hass, "duct_right").state == "off"

    await call(hass, "duct_right", "turn_on")
    assert fake_module.categories[6][184] == 24

    await call(hass, "duct_left", "set_preset_mode", preset_mode="external_thermostat")
    assert fake_module.categories[6][185] == 6

    await call(hass, "duct_left", "set_preset_mode", preset_mode="none")
    assert fake_module.categories[6][185] == 22

    await call(hass, "duct_left", "set_hvac_mode", hvac_mode="off")
    assert fake_module.categories[6][185] == 5

    await call(hass, "duct_left", "set_hvac_mode", hvac_mode="heat")
    assert fake_module.categories[6][185] == 22


@pytest.mark.usefixtures("enable_all_entities")
async def test_turning_on_ducting_that_is_on_writes_nothing(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Turning on must not replace the external thermostat by a temperature."""
    fake_module.categories[6] = {24: 21, 25: 19, 184: 22, 185: 6}
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await call(hass, "duct_left", "turn_on")

    assert fake_module.count(PATH_SET) == 0
    assert fake_module.categories[6][185] == 6


@pytest.mark.usefixtures("enable_all_entities")
async def test_turning_on_ducting_without_a_known_target(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Ducting found off starts at 20 degrees."""
    await call(hass, "duct_right", "turn_on")

    assert fake_module.categories[6][184] == 20


@pytest.mark.usefixtures("enable_all_entities")
@pytest.mark.parametrize("asked", [6, 42])
async def test_ducting_temperature_outside_the_bounds(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    asked: int,
) -> None:
    """5 and 6 are modes; the temperatures start at 7."""
    with pytest.raises(ServiceValidationError):
        await call(hass, "duct_right", "set_temperature", temperature=asked)

    assert fake_module.count(PATH_SET) == 0


@pytest.mark.usefixtures("enable_all_entities")
async def test_stove_without_ducting_or_water(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """ECO-RDS has the stove thermostat only."""
    await setup_model(hass, aioclient_mock, 12)

    assert exists(hass, "stove")
    assert not exists(hass, "duct_right")
    assert not exists(hass, "duct_left")
    assert not exists(hass, "water")


@pytest.mark.usefixtures("enable_all_entities")
async def test_water_thermostat(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """HYDRO-RDS adds a water target and has no ducting."""
    module = await setup_model(hass, aioclient_mock, 11)

    assert exists(hass, "stove")
    assert not exists(hass, "duct_right")
    state = climate(hass, "water")
    assert state.state == "off"
    assert state.attributes["temperature"] == 60
    assert state.attributes["current_temperature"] == 45
    assert state.attributes["min_temp"] == 30
    assert state.attributes["max_temp"] == 80
    assert state.attributes["preset_modes"] == ["none", "manual"]

    await call(hass, "water", "set_temperature", temperature=65)
    assert module.categories[2][49] == 65

    await call(hass, "water", "set_preset_mode", preset_mode="manual")
    assert module.categories[2][49] == 81
    assert climate(hass, "water").attributes["temperature"] is None

    await call(hass, "water", "set_preset_mode", preset_mode="none")
    assert module.categories[2][49] == 65

    await call(hass, "water", "turn_on")
    assert module.count(PATH_GET, key="022", status="1") == 1
    assert climate(hass, "water").state == "heat"
    assert climate(hass, "stove").state == "heat"


@pytest.mark.usefixtures("enable_all_entities")
async def test_water_leaves_manual_mode_without_a_known_target(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """20 degrees is below the water range: the default is 60."""
    module = FakeModule(model=11)
    module.categories[2][49] = 81
    module.install(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_MODEL: 11, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    await call(hass, "water", "set_preset_mode", preset_mode="none")

    assert module.categories[2][49] == 60
