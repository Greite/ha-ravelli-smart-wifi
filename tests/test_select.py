"""Tests for the ducting selects of a KTR-AIR BLDC stove."""

from homeassistant.const import CONF_HOST, CONF_MAC, CONF_MODEL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import HOST, MAC, PATH_SET, FakeModule
from .helpers import entity_id_for

# Category 6 of the stove of issue 3, ducting configuration 2.
CONFIG_2 = {
    175: 2,
    183: 20,
    184: 20,
    185: 20,
    186: 0,
    187: 6,
    188: 1,
    189: 2,
    190: 1,
    191: 0,
    192: 0,
    193: 0,
}


async def setup_ktr(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, ducting: dict[int, int]
) -> FakeModule:
    """Set up a KTR-AIR BLDC stove with the given category 6."""
    module = FakeModule(model=8)
    module.categories[6] = dict(ducting)
    module.install(aioclient_mock)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Ravelli",
        unique_id=MAC,
        data={CONF_HOST: HOST, CONF_MODEL: 8, CONF_MAC: MAC},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return module


@pytest.mark.parametrize(
    ("key", "state", "options"),
    [
        ("ducting_fan", "1", ["0", "1", "2", "3", "4", "5", "auto"]),
        (
            "ducting_direction",
            "middle",
            [
                "rear_left",
                "three_quarter_rear_left",
                "middle",
                "three_quarter_rear_right",
                "rear_right",
            ],
        ),
        ("ducting_split", "equal", ["front_rear_left", "equal", "rear_rear_right"]),
    ],
)
async def test_ducting_selects_of_configuration_2(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    key: str,
    state: str,
    options: list[str],
) -> None:
    """The values read against the vendor app of a stove in configuration 2."""
    await setup_ktr(hass, aioclient_mock, CONFIG_2)

    select = hass.states.get(entity_id_for(hass, "select", key))
    assert select.state == state
    assert select.attributes["options"] == options


@pytest.mark.parametrize(
    ("key", "option", "register", "value"),
    [
        ("ducting_fan", "3", 188, 3),
        ("ducting_fan", "auto", 188, 6),
        ("ducting_fan", "0", 188, 0),
        ("ducting_direction", "rear_right", 189, 4),
        ("ducting_split", "rear_rear_right", 190, 2),
    ],
)
async def test_select_writes_its_register(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    key: str,
    option: str,
    register: int,
    value: int,
) -> None:
    """The raw value of the option is written and shows at once."""
    module = await setup_ktr(hass, aioclient_mock, CONFIG_2)
    entity_id = entity_id_for(hass, "select", key)

    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": option},
        blocking=True,
    )

    assert module.count(PATH_SET, regId=str(register), value=str(value)) == 1
    assert hass.states.get(entity_id).state == option


@pytest.mark.parametrize("config", [0, 1, 3, 4])
async def test_no_select_outside_configuration_2(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, config: int
) -> None:
    """Registers 188 to 190 were only read against the app in configuration 2."""
    await setup_ktr(hass, aioclient_mock, CONFIG_2 | {175: config})

    registry = er.async_get(hass)
    for key in ("ducting_fan", "ducting_direction", "ducting_split"):
        assert registry.async_get_entity_id("select", DOMAIN, f"{MAC}_{key}") is None


async def test_select_unavailable_when_the_configuration_changes(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Nothing is shown or written once the stove leaves configuration 2."""
    module = await setup_ktr(hass, aioclient_mock, CONFIG_2)
    module.categories[6][175] = 3
    await hass.config_entries.async_entries(DOMAIN)[0].runtime_data.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id_for(hass, "select", "ducting_fan")).state == (
        "unavailable"
    )


async def test_no_select_on_another_board(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """AIR-RDS has none of these registers."""
    assert not hass.states.async_entity_ids("select")
