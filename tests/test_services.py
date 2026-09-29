"""Tests for the schedule actions."""

from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import FREE_PROGRAM, MAC, PATH_GET, FakeModule

EVENING_RAW = [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"]
MORNING_RAW = [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Morning"]
MORNING: dict[str, Any] = {
    "slot": 2,
    "name": "Morning",
    "start": "06:30:00",
    "end": "08:00:00",
    "temperature": 21,
    "power": 3,
    "weekdays": ["mon", "tue", "wed", "thu", "fri"],
}


def stove_id(hass: HomeAssistant, entry: MockConfigEntry) -> str:
    """Return the device id of the stove."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, MAC), entry.entry_id
    )
    assert device is not None
    return device.id


async def set_program(
    hass: HomeAssistant, entry: MockConfigEntry, **changes: Any
) -> None:
    """Store the morning program, with changes; None removes a field."""
    data = {"device_id": stove_id(hass, entry), **MORNING, **changes}
    await hass.services.async_call(
        DOMAIN,
        "set_schedule_program",
        {key: value for key, value in data.items() if value is not None},
        blocking=True,
    )


async def delete_program(
    hass: HomeAssistant, entry: MockConfigEntry, slot: int
) -> None:
    """Free one slot."""
    await hass.services.async_call(
        DOMAIN,
        "delete_schedule_program",
        {"device_id": stove_id(hass, entry), "slot": slot},
        blocking=True,
    )


async def test_set_program(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The program is stored and the other slots are kept."""
    await set_program(hass, init_integration)

    assert fake_module.programs[0] == EVENING_RAW
    assert fake_module.programs[1] == MORNING_RAW
    assert fake_module.programs[2] == FREE_PROGRAM
    schedule = init_integration.runtime_data.data.schedule
    assert schedule.programs[1].name == "Morning"


async def test_replacing_a_program(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """Writing to a used slot replaces its program."""
    await set_program(hass, init_integration, slot=1)

    assert fake_module.programs[0] == MORNING_RAW


@pytest.mark.parametrize(
    ("changes", "row"),
    [
        ({"enabled": False}, [0, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Morning"]),
        ({"end": None}, [1, 1, 6, 2, 0, 0, 0, 21, 3, 31, "Morning"]),
        ({"start": None}, [1, 0, 0, 0, 1, 8, 0, 21, 3, 31, "Morning"]),
        ({"start": "06:30"}, MORNING_RAW),
        (
            {"manual": True, "temperature": None},
            [1, 1, 6, 2, 1, 8, 0, 41, 3, 31, "Morning"],
        ),
        ({"manual": True}, [1, 1, 6, 2, 1, 8, 0, 41, 3, 31, "Morning"]),
        ({"weekdays": "sun"}, [1, 1, 6, 2, 1, 8, 0, 21, 3, 64, "Morning"]),
        ({"name": "A & B = C"}, [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "A & B = C"]),
    ],
)
async def test_program_variants(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    changes: dict[str, Any],
    row: list[Any],
) -> None:
    """Optional fields, manual mode and separators in the name."""
    await set_program(hass, init_integration, **changes)

    assert fake_module.programs[1] == row
    assert fake_module.programs[0] == EVENING_RAW


@pytest.mark.parametrize(
    ("changes", "key"),
    [
        ({"temperature": None}, "temperature_required"),
        ({"name": "Café"}, "schedule_name_characters"),
        ({"end": "06:30:00"}, "schedule_end_before_start"),
        ({"end": "06:00:00"}, "schedule_end_before_start"),
        ({"start": "06:10:00"}, "schedule_time_step"),
        ({"start": None, "end": None}, "schedule_no_time"),
    ],
)
async def test_programs_that_break_a_rule(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    changes: dict[str, Any],
    key: str,
) -> None:
    """Each rule has its own message and nothing is sent."""
    with pytest.raises(ServiceValidationError) as err:
        await set_program(hass, init_integration, **changes)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == key
    assert fake_module.count(PATH_GET, key="032") == 0
    assert fake_module.programs[1] == FREE_PROGRAM


@pytest.mark.parametrize(
    "changes",
    [
        {"slot": 0},
        {"slot": 7},
        {"name": ""},
        {"name": "x" * 16},
        {"temperature": 4},
        {"temperature": 41},
        {"power": 0},
        {"power": 6},
        {"weekdays": []},
        {"weekdays": ["mon", "someday"]},
        {"start": "25:00:00"},
        {"device_id": None},
    ],
)
async def test_fields_outside_the_schema(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    fake_module: FakeModule,
    changes: dict[str, Any],
) -> None:
    """The schema of the action refuses them before any code runs."""
    data = {"device_id": stove_id(hass, init_integration), **MORNING, **changes}

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "set_schedule_program",
            {key: value for key, value in data.items() if value is not None},
            blocking=True,
        )

    assert fake_module.count(PATH_GET, key="032") == 0


async def test_delete_program(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The slot is freed on the module and in the state."""
    await delete_program(hass, init_integration, 1)

    assert fake_module.programs[0] == FREE_PROGRAM
    assert init_integration.runtime_data.data.schedule.programs[0] is None


async def test_write_the_module_ignored(
    hass: HomeAssistant, init_integration: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The read-back catches a module that answers yes and stores nothing."""
    fake_module.ignore_schedule_writes = True

    with pytest.raises(HomeAssistantError) as err:
        await set_program(hass, init_integration)

    assert err.value.translation_key == "schedule_mismatch"


async def test_unknown_device(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A device id that does not exist is refused."""
    with pytest.raises(ServiceValidationError) as err:
        await set_program(hass, init_integration, device_id="not-a-device")

    assert err.value.translation_key == "device_not_found"


async def test_device_of_an_unloaded_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A stove that is not loaded has no coordinator to talk to."""
    device_id = stove_id(hass, init_integration)
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await set_program(hass, init_integration, device_id=device_id)

    assert err.value.translation_key == "device_not_found"
