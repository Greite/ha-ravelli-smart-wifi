"""Tests for the ducting and water thermostats."""

from typing import Any

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
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
async def test_ktr_air_bldc(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Model 8 has no comfort settings; code 0 is off."""
    module = await setup_model(hass, aioclient_mock, 8)
    registry = er.async_get(hass)

    assert exists(hass, "stove")
    assert not exists(hass, "duct_right")
    assert not exists(hass, "water")
    assert registry.async_get_entity_id("number", DOMAIN, f"{MAC}_power")
    for key in ("comfort_delta", "comfort_delay"):
        assert registry.async_get_entity_id("number", DOMAIN, f"{MAC}_{key}") is None
    assert module.count(PATH_GET, key="020", category="11") == 0

    state = climate(hass, "stove")
    assert state.state == "off"
    assert state.attributes["hvac_action"] == "off"
    assert state.attributes["current_temperature"] == 21
    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "off"
    fan = hass.states.get(entity_id_for(hass, "sensor", "front_fan"))
    assert fan.state == "auto"
    assert fan.attributes["raw_value"] == 6


@pytest.mark.parametrize(
    ("status", "key", "action"),
    [
        (1, "waiting_start", "preheating"),
        (2, "ignition", "preheating"),
        (5, "working", "heating"),
        (7, "final_cleaning", "off"),
        (8, "eco_stop", "idle"),
    ],
)
async def test_ktr_air_bldc_status_is_shown_and_stays_on(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    key: str,
    action: str,
) -> None:
    """Every code but 0 keeps the thermostat on, final cleaning included."""
    module = await setup_model(hass, aioclient_mock, 8)
    module.common[2] = status
    await hass.config_entries.async_entries(DOMAIN)[0].runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == key
    state = climate(hass, "stove")
    assert state.state == "heat"
    assert state.attributes["hvac_action"] == action


async def test_front_fan_is_ktr_air_bldc_only(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Register 187 has no known meaning on the other boards."""
    await setup_model(hass, aioclient_mock, 7)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{MAC}_front_fan") is None


@pytest.mark.parametrize(
    ("config", "expected", "raw"),
    [(2, "1", 1), (0, "unknown", None), (4, "unknown", None)],
)
async def test_front_fan_follows_the_ducting_configuration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config: int,
    expected: str,
    raw: int | None,
) -> None:
    """Configuration 2 drives the front fan by register 188; others are unknown."""
    module = await setup_model(hass, aioclient_mock, 8)
    module.categories[6][175] = config
    await hass.config_entries.async_entries(DOMAIN)[0].runtime_data.async_refresh()
    await hass.async_block_till_done()

    fan = hass.states.get(entity_id_for(hass, "sensor", "front_fan"))
    assert fan.state == expected
    assert fan.attributes["raw_value"] == raw


async def test_water_temperature_is_hydro_only(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Register 1 means nothing on a board without a water circuit."""
    await setup_model(hass, aioclient_mock, 7)

    registry = er.async_get(hass)
    assert (
        registry.async_get_entity_id("sensor", DOMAIN, f"{MAC}_water_temperature")
        is None
    )


@pytest.mark.parametrize(
    ("status", "sent"), [(0, 1), (1, 0), (6, 0), (7, 0), (8, 0), (42, 0)]
)
async def test_ktr_air_bldc_turns_on_from_code_0_only(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: int, sent: int
) -> None:
    """Final cleaning (7), eco stop (8) and unknown codes count as on."""
    module = await setup_model(hass, aioclient_mock, 8)
    module.common[2] = status

    await call(hass, "stove", "turn_on")

    assert module.count(PATH_GET, key="022", status="1") == sent


async def test_ktr_air_bldc_flame_is_disabled_by_default(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The board reports a flame in every phase, eco stop included."""
    await setup_model(hass, aioclient_mock, 8)

    entry = er.async_get(hass).async_get(entity_id_for(hass, "binary_sensor", "flame"))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize("status", [1, 2, 4])
async def test_ktr_air_bldc_turn_off_without_flame_is_refused(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, status: int
) -> None:
    """Before the flame, like the page and the RDS boards, off waits."""
    module = await setup_model(hass, aioclient_mock, 8)
    module.common[2] = status
    module.extra["flame"] = 0

    with pytest.raises(ServiceValidationError) as err:
        await call(hass, "stove", "turn_off")

    assert err.value.translation_key == "turn_off_during_ignition"
    assert module.count(PATH_GET, key="022") == 0

    module.extra["flame"] = 1
    await call(hass, "stove", "turn_off")
    assert module.count(PATH_GET, key="022", status="0") == 1


@pytest.mark.usefixtures("enable_all_entities")
async def test_ktr_hydro(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Model 6: water thermostat, no power level, no code with a meaning."""
    module = await setup_model(hass, aioclient_mock, 6)
    registry = er.async_get(hass)

    assert not exists(hass, "duct_right")
    for key in ("power", "comfort_delta", "comfort_delay"):
        assert registry.async_get_entity_id("number", DOMAIN, f"{MAC}_{key}") is None
    assert module.count(PATH_GET, key="020", category="6") == 0
    assert module.count(PATH_GET, key="020", category="11") == 0

    stove = climate(hass, "stove")
    assert stove.state == "heat"
    assert stove.attributes.get("hvac_action") is None
    assert "fan_modes" not in stove.attributes
    assert stove.attributes["current_temperature"] == 21
    water = climate(hass, "water")
    assert water.attributes["current_temperature"] == 45.5
    assert water.attributes["temperature"] == 60
    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "unknown"
    assert (
        hass.states.get(entity_id_for(hass, "sensor", "water_temperature")).state
        == "45.5"
    )

    await call(hass, "water", "set_temperature", temperature=65)
    assert module.categories[2][49] == 65


@pytest.mark.usefixtures("enable_all_entities")
async def test_stilo(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Model 14: target and power, no code with a meaning, no room temperature."""
    module = await setup_model(hass, aioclient_mock, 14)
    registry = er.async_get(hass)

    for key in ("duct_right", "duct_left", "water"):
        assert not exists(hass, key)
    for key in ("comfort_delta", "comfort_delay"):
        assert registry.async_get_entity_id("number", DOMAIN, f"{MAC}_{key}") is None
    assert registry.async_get_entity_id("sensor", DOMAIN, f"{MAC}_front_fan") is None
    assert module.count(PATH_GET, key="020", category="6") == 0
    assert module.count(PATH_GET, key="020", category="11") == 0

    stove = climate(hass, "stove")
    assert stove.state == "heat"
    assert stove.attributes["current_temperature"] is None
    assert stove.attributes["fan_modes"] == ["1", "2", "3", "4", "5"]
    ambient = entity_id_for(hass, "sensor", "ambient_temperature")
    assert hass.states.get(ambient).state == "unknown"
    assert hass.states.get(entity_id_for(hass, "sensor", "status")).state == "unknown"

    await call(hass, "stove", "set_temperature", temperature=22)
    await call(hass, "stove", "set_fan_mode", fan_mode="4")
    assert module.categories[2][50] == 22
    assert module.categories[2][51] == 4


@pytest.mark.parametrize("model", [6, 14])
async def test_unread_board_flame_is_disabled_by_default(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, model: int
) -> None:
    """KTR-HYDRO reported a flame while off; nothing was read on STILO."""
    await setup_model(hass, aioclient_mock, model)

    entry = er.async_get(hass).async_get(entity_id_for(hass, "binary_sensor", "flame"))
    assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.parametrize(
    ("model", "enabled", "chrono", "expected"),
    [
        # As read on a KTR-HYDRO stove: the two flags disagree.
        (6, False, 1, "unknown"),
        (6, True, 0, "unknown"),
        (6, False, 0, "off"),
        (6, True, 1, "on"),
        # Nothing read on a STILO stove: same caution.
        (14, False, 1, "unknown"),
        # The RDS capture holds chrono 0 with the schedule on: not a signal.
        (7, True, 0, "on"),
    ],
)
async def test_ktr_hydro_schedule_switch_is_unknown_when_flags_disagree(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    model: int,
    enabled: bool,
    chrono: int,
    expected: str,
) -> None:
    """Never show off for a schedule that may start the stove."""
    module = FakeModule(model=model)
    module.schedule_enabled = enabled
    module.extra["chrono"] = chrono
    module.install(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_MODEL: model, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id_for(hass, "switch", "schedule")).state == expected
    calendar = entity_id_for(hass, "calendar", "schedule")
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": calendar, "duration": {"days": 2}},
        blocking=True,
        return_response=True,
    )
    # The calendar shows the starts the stove may make, unless surely off.
    assert bool(response[calendar]["events"]) is (expected != "off")


@pytest.mark.parametrize("status", [0, 5, 42])
@pytest.mark.parametrize(("model", "key"), [(6, "stove"), (6, "water"), (14, "stove")])
async def test_unread_board_turn_on_is_refused(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    model: int,
    key: str,
) -> None:
    """No code of these boards is trusted as off: Home Assistant cannot tell."""
    module = await setup_model(hass, aioclient_mock, model)
    module.common[2] = status

    with pytest.raises(ServiceValidationError) as err:
        await call(hass, key, "turn_on")

    assert err.value.translation_key == "turn_on_not_verified"
    assert module.count(PATH_GET, key="022") == 0


@pytest.mark.parametrize("model", [6, 14])
@pytest.mark.parametrize("flame", [0, 1, 255])
@pytest.mark.parametrize("status", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 42])
async def test_unread_board_turn_off_is_always_sent(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    status: int,
    flame: int,
    model: int,
) -> None:
    """Nobody saw which code is an ignition on these boards: off is never held."""
    module = await setup_model(hass, aioclient_mock, model)
    module.common[2] = status
    module.extra["flame"] = flame

    await call(hass, "stove", "turn_off")

    assert module.count(PATH_GET, key="022", status="0") == 1


@pytest.mark.parametrize("model", [6, 14])
async def test_unread_board_schedule_cannot_start_the_stove(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, model: int
) -> None:
    """A program can start the stove: only what stops it is sent."""
    module = await setup_model(hass, aioclient_mock, model)
    switch = entity_id_for(hass, "switch", "schedule")
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, MAC), hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )

    await hass.services.async_call(
        "switch", "turn_off", {"entity_id": switch}, blocking=True
    )
    assert module.count(PATH_GET, key="032") == 1
    assert module.schedule_enabled is False

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": switch}, blocking=True
        )
    assert err.value.translation_key == "schedule_not_verified"

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            "set_schedule_program",
            {
                "device_id": device.id,
                "slot": 6,
                "name": "Test",
                "start": "06:30:00",
                "end": "08:00:00",
                "temperature": 21,
                "power": 3,
                "weekdays": ["mon"],
            },
            blocking=True,
        )
    assert err.value.translation_key == "schedule_not_verified"
    assert module.count(PATH_GET, key="032") == 1
    assert module.schedule_enabled is False

    await hass.services.async_call(
        DOMAIN,
        "delete_schedule_program",
        {"device_id": device.id, "slot": 1},
        blocking=True,
    )
    assert module.count(PATH_GET, key="034") == 1


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
    # Whole degrees on this board: register 1 is not halved.
    assert (
        hass.states.get(entity_id_for(hass, "sensor", "water_temperature")).state
        == "45.0"
    )

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
