"""Tests for the stove thermostat."""

from typing import Any

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from .fake_module import PATH_GET, PATH_SET, FakeModule
from .helpers import advance, entity_id_for


def stove(hass: HomeAssistant) -> State:
    """Return the state of the thermostat."""
    state = hass.states.get(entity_id_for(hass, "climate", "stove"))
    assert state is not None
    return state


async def call(hass: HomeAssistant, action: str, **data: Any) -> None:
    """Call a climate action on the thermostat."""
    await hass.services.async_call(
        "climate",
        action,
        {"entity_id": entity_id_for(hass, "climate", "stove"), **data},
        blocking=True,
    )


async def test_thermostat_of_an_idle_stove(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The capture of an idle stove at 22 degrees."""
    state = stove(hass)

    assert state.state == "off"
    assert state.attributes["hvac_modes"] == ["heat", "off"]
    assert state.attributes["hvac_action"] == "off"
    assert state.attributes["current_temperature"] == 22.0
    assert state.attributes["temperature"] == 22
    assert state.attributes["min_temp"] == 5
    assert state.attributes["max_temp"] == 40
    assert state.attributes["target_temp_step"] == 1
    assert state.attributes["fan_mode"] == "1"
    assert state.attributes["fan_modes"] == ["1", "2", "3", "4", "5"]
    assert state.attributes["preset_mode"] == "none"
    assert state.attributes["preset_modes"] == ["none", "manual"]


@pytest.mark.parametrize(
    ("status", "mode", "action"),
    [
        (0, "off", "off"),
        (1, "heat", "preheating"),
        (2, "heat", "preheating"),
        (3, "heat", "preheating"),
        (4, "heat", "preheating"),
        (5, "heat", "heating"),
        (6, "off", "off"),
        (7, "heat", "idle"),
        (8, "off", "off"),
        (9, "off", "off"),
        (42, "off", None),
    ],
)
async def test_mode_and_action_follow_the_status(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
    status: int,
    mode: str,
    action: str | None,
) -> None:
    """Ignition shows as preheating and eco stop as idle."""
    fake_module.common[2] = status

    await advance(hass, freezer)

    assert stove(hass).state == mode
    assert stove(hass).attributes.get("hvac_action") == action


@pytest.mark.parametrize(("asked", "written"), [(23, 23), (23.4, 23), (5, 5), (40, 40)])
async def test_set_temperature(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    asked: float,
    written: int,
) -> None:
    """The stove works in whole degrees."""
    await call(hass, "set_temperature", temperature=asked)

    assert fake_module.categories[2][50] == written
    assert stove(hass).attributes["temperature"] == written


@pytest.mark.parametrize("asked", [4, 41, 50])
async def test_temperature_outside_the_bounds_is_refused(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    asked: int,
) -> None:
    """41 is the manual mode, not a temperature."""
    with pytest.raises(ServiceValidationError):
        await call(hass, "set_temperature", temperature=asked)

    assert fake_module.count(PATH_SET) == 0


async def test_set_fan_mode_writes_the_power_level(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The fan modes are the five power levels, as in Agua IOT."""
    await call(hass, "set_fan_mode", fan_mode="3")

    assert fake_module.categories[2][51] == 3
    assert stove(hass).attributes["fan_mode"] == "3"


async def test_unknown_fan_mode_is_refused(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """There is no level 6."""
    with pytest.raises(ServiceValidationError):
        await call(hass, "set_fan_mode", fan_mode="6")

    assert fake_module.count(PATH_SET) == 0


async def test_manual_preset_and_back(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Leaving the manual mode restores the last target."""
    await call(hass, "set_preset_mode", preset_mode="manual")

    assert fake_module.categories[2][50] == 41
    assert stove(hass).attributes["preset_mode"] == "manual"
    assert stove(hass).attributes["temperature"] is None

    await call(hass, "set_preset_mode", preset_mode="none")

    assert fake_module.categories[2][50] == 22
    assert stove(hass).attributes["preset_mode"] == "none"
    assert stove(hass).attributes["temperature"] == 22


async def test_leaving_manual_mode_without_a_known_target(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A stove found in manual mode goes back to 20 degrees."""
    fake_module.categories[2][50] = 41
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert stove(hass).attributes["preset_mode"] == "manual"

    await call(hass, "set_preset_mode", preset_mode="none")

    assert fake_module.categories[2][50] == 20


async def test_setting_a_temperature_leaves_the_manual_mode(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A target temperature is a way out of the manual mode."""
    fake_module.categories[2][50] = 41
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    await call(hass, "set_temperature", temperature=21)

    assert stove(hass).attributes["preset_mode"] == "none"
    assert stove(hass).attributes["temperature"] == 21


@pytest.mark.parametrize(
    ("action", "data"), [("turn_on", {}), ("set_hvac_mode", {"hvac_mode": "heat"})]
)
async def test_turn_on(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    action: str,
    data: dict[str, str],
) -> None:
    """The thermostat shows the ignition at once."""
    await call(hass, action, **data)

    assert fake_module.count(PATH_GET, key="022", status="1") == 1
    assert stove(hass).state == "heat"
    assert stove(hass).attributes["hvac_action"] == "preheating"


@pytest.mark.parametrize(
    ("action", "data"), [("turn_off", {}), ("set_hvac_mode", {"hvac_mode": "off"})]
)
async def test_turn_off(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
    action: str,
    data: dict[str, str],
) -> None:
    """A working stove can be turned off."""
    fake_module.common[2] = 5
    await advance(hass, freezer)

    await call(hass, action, **data)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1
    assert stove(hass).state == "off"


async def test_turn_off_is_refused_during_ignition(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The message tells the user to wait for the flame."""
    fake_module.common[2] = 2
    fake_module.extra["flame"] = 0

    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "turn_off")

    assert err.value.translation_key == "turn_off_during_ignition"
    assert fake_module.count(PATH_GET, key="022") == 0


async def test_turn_on_is_refused_in_alarm(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The message tells the user to acknowledge the alarm first."""
    fake_module.common[2] = 8

    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "turn_on")

    assert err.value.translation_key == "turn_on_in_alarm"
    assert fake_module.count(PATH_GET, key="022") == 0


async def test_missing_registers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """The thermostat stays up when the module omits its registers."""
    fake_module.categories[2] = {}

    await advance(hass, freezer)

    state = stove(hass)
    assert state.state == "off"
    assert state.attributes["current_temperature"] is None
    assert state.attributes["temperature"] is None
    assert state.attributes["fan_mode"] is None
    assert state.attributes["preset_mode"] == "none"
