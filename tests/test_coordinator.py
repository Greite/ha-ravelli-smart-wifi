"""Tests for the coordinator."""

import asyncio
from dataclasses import replace
from datetime import time, timedelta

import aiohttp
from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from pytest_homeassistant_custom_component.test_util.aiohttp import (
    AiohttpClientMocker,
)

from custom_components.ravelli_smart_wifi.api import WinetClient
from custom_components.ravelli_smart_wifi.const import DOMAIN
from custom_components.ravelli_smart_wifi.coordinator import RavelliCoordinator
from custom_components.ravelli_smart_wifi.models import (
    SUPPORTED_MODELS,
    ScheduleProgram,
)

from .fake_module import HOST, PATH_GET, PATH_SET, PATH_STATUS, FakeModule

EVENING_RAW = [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"]
MORNING = ScheduleProgram(
    name="Morning",
    enabled=True,
    start=time(6, 30),
    end=time(8, 0),
    temperature=21,
    power=3,
    weekdays=frozenset({"mon", "tue", "wed", "thu", "fri"}),
)
MORNING_RAW = [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Morning"]


def build(
    hass: HomeAssistant, entry: MockConfigEntry, model: int = 7
) -> RavelliCoordinator:
    """Build a coordinator without setting the integration up."""
    client = WinetClient(async_get_clientsession(hass), HOST)
    return RavelliCoordinator(hass, entry, client, SUPPORTED_MODELS[model])


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> RavelliCoordinator:
    """Return a coordinator that has polled the module once."""
    coordinator = build(hass, config_entry)
    await coordinator.async_refresh()
    assert coordinator.last_update_success
    fake_module.requests.clear()
    return coordinator


def categories_read(fake_module: FakeModule) -> list[str]:
    """List the categories read, in order."""
    return [
        fields["category"]
        for _, fields in fake_module.requests
        if fields.get("key") == "020"
    ]


async def test_first_refresh_reads_everything(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The first poll reads the registers, the system status and the schedule."""
    coordinator = build(hass, config_entry)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert coordinator.data.state.setpoint == 22
    assert coordinator.data.state.raw(184) == 5
    assert coordinator.data.state.raw(74) == 1
    assert coordinator.data.system["fwVer"] == "0.51"
    assert coordinator.data.schedule.programs[0].name == "Evening"
    assert categories_read(fake_module) == ["2", "6", "11"]
    assert coordinator.update_interval == timedelta(seconds=30)


async def test_models_without_ducting_skip_its_category(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """HYDRO-RDS and ECO-RDS read two categories."""
    module = FakeModule(model=12)
    module.install(aioclient_mock)
    coordinator = build(hass, config_entry, model=12)

    await coordinator.async_refresh()

    assert coordinator.last_update_success
    assert categories_read(module) == ["2", "11"]


async def test_polling_interval_comes_from_the_options(
    hass: HomeAssistant, fake_module: FakeModule
) -> None:
    """The options flow stores the interval in seconds."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={"host": HOST}, options={"scan_interval": 60}
    )
    entry.add_to_hass(hass)

    assert build(hass, entry).update_interval == timedelta(seconds=60)


async def test_slow_data_is_read_every_ten_minutes(
    coordinator: RavelliCoordinator,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """System status and schedule are not part of every poll."""
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert fake_module.count(PATH_STATUS) == 0
    assert fake_module.count(PATH_GET, key="033") == 0

    freezer.tick(timedelta(seconds=601))
    await coordinator.async_refresh()

    assert fake_module.count(PATH_STATUS) == 1
    assert fake_module.count(PATH_GET, key="033") == 1


async def test_unreachable_module_fails_the_update(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """Entities follow last_update_success."""
    fake_module.error = aiohttp.ClientConnectionError()
    await coordinator.async_refresh()
    assert not coordinator.last_update_success

    fake_module.error = None
    await coordinator.async_refresh()
    assert coordinator.last_update_success


@pytest.mark.parametrize("answer", ["<html>busy</html>", '{"params": [[0, 44]]}'])
async def test_unexpected_answer_fails_the_update(
    coordinator: RavelliCoordinator, fake_module: FakeModule, answer: str
) -> None:
    """HTML, or registers without a status, must not raise out of the poll."""
    fake_module.raw_answers[PATH_GET] = answer

    await coordinator.async_refresh()

    assert not coordinator.last_update_success


async def test_write_register(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A write is followed by a read, so the new value shows at once."""
    await coordinator.async_write_register(50, 23)

    assert fake_module.requests[0] == (
        PATH_SET,
        {"key": "002", "memory": "1", "regId": "50", "value": "23", "result": "false"},
    )
    assert categories_read(fake_module) == ["2", "6", "11"]
    assert coordinator.data.state.setpoint == 23


async def test_out_of_range_write_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The bounds are checked before the module is contacted."""
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_write_register(50, 42)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "value_out_of_range"
    assert err.value.translation_placeholders == {
        "value": "42",
        "minimum": "5",
        "maximum": "41",
    }
    assert fake_module.requests == []


async def test_register_outside_the_table_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """Register 49 belongs to the hydro model."""
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_write_register(49, 60)

    assert err.value.translation_key == "register_not_writable"
    assert err.value.translation_placeholders == {"register": "49"}
    assert fake_module.requests == []


async def test_refused_write(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A refusal is reported and the write is not repeated."""
    fake_module.write_result = False

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_write_register(50, 23)

    assert err.value.translation_key == "command_refused"
    assert fake_module.count(PATH_SET) == 1


async def test_write_to_an_unreachable_module(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A network failure is reported and the write is not repeated."""
    fake_module.error = aiohttp.ClientConnectionError()

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_write_register(50, 23)

    assert err.value.translation_key == "cannot_connect"
    assert fake_module.count(PATH_SET) == 1


async def test_polls_faster_after_a_command(
    hass: HomeAssistant,
    coordinator: RavelliCoordinator,
    fake_module: FakeModule,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Five close polls follow a command, then the normal pace returns."""
    remove_listener = coordinator.async_add_listener(lambda: None)

    await coordinator.async_write_register(51, 2)
    assert coordinator.update_interval == timedelta(seconds=2)

    for expected in (3, 5, 10, 10, 30):
        polls = fake_module.count(PATH_GET, key="020", category="2")
        freezer.tick(timedelta(seconds=11))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert fake_module.count(PATH_GET, key="020", category="2") == polls + 1
        assert coordinator.update_interval == timedelta(seconds=expected)

    remove_listener()


async def test_requests_never_overlap(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The module handles one request at a time."""
    fake_module.delay = 0.01

    await asyncio.gather(
        coordinator.async_write_register(51, 2),
        coordinator.async_write_register(50, 21),
        coordinator.async_refresh(),
    )

    assert fake_module.max_concurrent == 1
    assert fake_module.categories[2][51] == 2
    assert fake_module.categories[2][50] == 21


async def test_turn_on(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The command is sent and the new status is read back."""
    await coordinator.async_set_power(True)

    assert fake_module.count(PATH_GET, key="022", status="1") == 1
    assert coordinator.data.state.status_key == "ignition"


async def test_turn_on_when_already_on_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """An on command never reaches a running stove."""
    fake_module.common[2] = 4

    await coordinator.async_set_power(True)

    assert fake_module.count(PATH_GET, key="022") == 0
    assert coordinator.data.state.status_key == "working"


async def test_turn_on_is_refused_in_alarm_raised_since_the_last_poll(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The rule uses the state read at command time, not the polled one."""
    assert coordinator.data.state.status_key == "off"
    fake_module.common[2] = 8

    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_power(True)

    assert err.value.translation_key == "turn_on_in_alarm"
    assert fake_module.count(PATH_GET, key="022") == 0


async def test_turn_off(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A working stove can be turned off."""
    fake_module.common[2] = 4

    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1
    assert coordinator.data.state.status_key == "off"


async def test_turn_off_when_already_off_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """An off command never reaches an idle stove."""
    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022") == 0


@pytest.mark.parametrize("status", [1, 2, 3])
async def test_turn_off_is_refused_while_igniting_without_flame(
    coordinator: RavelliCoordinator, fake_module: FakeModule, status: int
) -> None:
    """The vendor UI refuses this too."""
    fake_module.common[2] = status
    fake_module.extra["flame"] = 0

    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_power(False)

    assert err.value.translation_key == "turn_off_during_ignition"
    assert fake_module.count(PATH_GET, key="022") == 0


@pytest.mark.parametrize("flame", [255, 1])
async def test_turn_off_while_igniting_is_allowed_otherwise(
    coordinator: RavelliCoordinator, fake_module: FakeModule, flame: int
) -> None:
    """Allowed when the flame is there, or when the board does not report it."""
    fake_module.common[2] = 2
    fake_module.extra["flame"] = flame

    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1


@pytest.mark.parametrize("status", [4, 7])
async def test_turn_off_is_allowed_without_flame_out_of_ignition(
    coordinator: RavelliCoordinator, fake_module: FakeModule, status: int
) -> None:
    """The ignition rule covers the codes 1 to 3 only."""
    fake_module.common[2] = status
    fake_module.extra["flame"] = 0

    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1


@pytest.mark.parametrize(
    ("status", "alarm_code"), [(8, 0), (9, 0), (4, 5), (5, 0), (42, 0)]
)
async def test_turn_off_in_alarm_or_unknown_status_is_sent(
    coordinator: RavelliCoordinator,
    fake_module: FakeModule,
    status: int,
    alarm_code: int,
) -> None:
    """Like the power button of the stove; an unknown code counts as on."""
    fake_module.common.update({2: status, 3: alarm_code})

    await coordinator.async_set_power(False)

    assert fake_module.count(PATH_GET, key="022", status="0") == 1


async def test_set_program_keeps_the_other_slots(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The table is read, changed, written and read back."""
    await coordinator.async_set_program(2, MORNING)

    assert fake_module.programs[0] == EVENING_RAW
    assert fake_module.programs[1] == MORNING_RAW
    assert fake_module.count(PATH_GET, key="033") == 2
    assert fake_module.count(PATH_GET, key="032") == 1
    assert coordinator.data.schedule.programs[1] == MORNING


async def test_set_program_keeps_an_accented_name(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The module stores accented letters unchanged."""
    program = replace(MORNING, name="Matinée")

    await coordinator.async_set_program(2, program)

    assert fake_module.programs[1] == [*MORNING_RAW[:10], "Matinée"]
    assert coordinator.data.schedule.programs[1] == program


async def test_set_program_uses_the_table_of_the_module(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A program added from the vendor UI since the last poll is kept."""
    fake_module.programs[4] = [1, 1, 7, 0, 0, 0, 0, 20, 2, 64, "Sunday"]

    await coordinator.async_set_program(2, MORNING)

    assert fake_module.programs[4] == [1, 1, 7, 0, 0, 0, 0, 20, 2, 64, "Sunday"]
    assert fake_module.programs[1] == MORNING_RAW


async def test_schedule_is_checked_after_the_write(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A write the module ignored is reported."""
    fake_module.ignore_schedule_writes = True

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_program(2, MORNING)

    assert err.value.translation_key == "schedule_mismatch"
    assert fake_module.count(PATH_GET, key="032") == 1


async def test_invalid_program_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The rules of the vendor UI apply before anything is sent."""
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_program(2, replace(MORNING, end=time(6, 0)))

    assert err.value.translation_key == "schedule_end_before_start"
    assert fake_module.requests == []


@pytest.mark.parametrize("slot", [0, 7])
async def test_slot_must_exist(
    coordinator: RavelliCoordinator, fake_module: FakeModule, slot: int
) -> None:
    """Slots are numbered 1 to 6, for writing and for deleting."""
    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_program(slot, MORNING)
    assert err.value.translation_key == "schedule_slot_range"

    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_delete_program(slot)
    assert err.value.translation_key == "schedule_slot_range"

    assert fake_module.requests == []


async def test_delete_program(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """Slot 1 is index 0 for the module."""
    await coordinator.async_delete_program(1)

    assert fake_module.count(PATH_GET, key="034", index="0") == 1
    assert fake_module.programs[0][10] == ""
    assert coordinator.data.schedule.programs[0] is None


async def test_delete_a_free_slot_sends_nothing(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """There is nothing to delete."""
    await coordinator.async_delete_program(3)

    assert fake_module.count(PATH_GET, key="034") == 0


async def test_schedule_switch_keeps_the_programs(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The global flag travels with the whole table."""
    await coordinator.async_set_schedule_enabled(False)

    assert fake_module.schedule_enabled is False
    assert fake_module.programs[0] == EVENING_RAW
    assert coordinator.data.schedule.enabled is False


@pytest.mark.freeze_time("2026-09-29T16:57:30+00:00")
async def test_clock_is_set_to_local_time(
    hass: HomeAssistant, coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """16:57 UTC is 18:57 in Paris; the stove shows local time."""
    await hass.config.async_set_time_zone("Europe/Paris")
    fake_module.categories[4] = dict.fromkeys(range(59, 65), 0)

    await coordinator.async_sync_clock()

    assert fake_module.categories[4] == {
        59: 2,
        60: 0x18,
        61: 0x57,
        62: 0x29,
        63: 0x09,
        64: 0x26,
    }
    assert fake_module.count(PATH_SET) == 6


async def test_diagnostics_read(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """Every category from 0 to 12 is read, with the status and the schedule."""
    dump = await coordinator.async_read_diagnostics()

    assert sorted(dump) == ["categories", "schedule", "system"]
    assert list(dump["categories"]) == [str(number) for number in range(13)]
    assert [300, 1] in dump["categories"]["0"]["params"]
    assert [60, 24] in dump["categories"]["4"]["params"]
    assert dump["system"]["fwVer"] == "0.51"
    assert dump["schedule"]["programs"][0] == EVENING_RAW


SUNDAY_RAW = [1, 1, 7, 0, 0, 0, 0, 20, 2, 64, "Sunday"]


async def test_mismatch_keeps_the_table_the_module_holds(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The read-back is shown, not the table from before the write."""
    fake_module.programs[4] = list(SUNDAY_RAW)
    fake_module.ignore_schedule_writes = True

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_program(2, MORNING)

    assert err.value.translation_key == "schedule_mismatch"
    assert coordinator.data.schedule.programs[4].name == "Sunday"
    assert coordinator.data.schedule.programs[1] is None


async def test_delete_mismatch_keeps_the_table_the_module_holds(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """The delete path checks the read-back too."""
    fake_module.programs[4] = list(SUNDAY_RAW)
    fake_module.ignore_schedule_writes = True

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_delete_program(1)

    assert err.value.translation_key == "schedule_mismatch"
    assert fake_module.count(PATH_GET, key="034", index="0") == 1
    assert coordinator.data.schedule.programs[0].name == "Evening"
    assert coordinator.data.schedule.programs[4].name == "Sunday"


async def test_refused_schedule_write_shows_the_table_of_the_module(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A refused write reads the table again at once."""
    fake_module.programs[4] = list(SUNDAY_RAW)
    fake_module.write_result = False

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_schedule_enabled(False)

    assert err.value.translation_key == "command_refused"
    assert coordinator.data.schedule.programs[4].name == "Sunday"
    assert coordinator.data.schedule.enabled is True


@pytest.mark.parametrize(
    ("fault", "key"),
    [("refused", "command_refused"), ("unreachable", "cannot_connect")],
)
async def test_failed_command_refreshes_at_the_normal_pace(
    coordinator: RavelliCoordinator, fake_module: FakeModule, fault: str, key: str
) -> None:
    """The state is read again, without the fast polls of a command."""
    if fault == "refused":
        fake_module.write_result = False
    else:
        fake_module.error = aiohttp.ClientConnectionError()

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_write_register(50, 23)

    assert err.value.translation_key == key
    assert fake_module.count(PATH_GET, key="020", category="2") == 1
    assert coordinator.update_interval == timedelta(seconds=30)


async def test_refused_safety_rule_does_not_poll_faster(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A command refused by a safety rule is a failed command too."""
    fake_module.common[2] = 8

    with pytest.raises(ServiceValidationError):
        await coordinator.async_set_power(True)

    assert coordinator.update_interval == timedelta(seconds=30)
    assert coordinator.data.state.status_code == 8


@pytest.mark.parametrize(("status", "alarm_code"), [(9, 0), (0, 5), (6, 5), (4, 5)])
async def test_turn_on_is_refused_in_alarm_memory_or_with_an_alarm_code(
    coordinator: RavelliCoordinator,
    fake_module: FakeModule,
    status: int,
    alarm_code: int,
) -> None:
    """Status 9, or an alarm code with any status, refuses the on command."""
    fake_module.common.update({2: status, 3: alarm_code})

    with pytest.raises(ServiceValidationError) as err:
        await coordinator.async_set_power(True)

    assert err.value.translation_key == "turn_on_in_alarm"
    assert fake_module.count(PATH_GET, key="022") == 0


async def test_poll_with_another_model_fails_the_update(
    coordinator: RavelliCoordinator,
    fake_module: FakeModule,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The register table of the entry no longer applies."""
    fake_module.model = 11

    await coordinator.async_refresh()

    assert not coordinator.last_update_success
    assert "model 11" in caplog.text

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_power(True)
    assert err.value.translation_key == "model_mismatch"
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_schedule_enabled(False)
    assert err.value.translation_key == "model_mismatch"
    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_write_register(50, 23)
    assert err.value.translation_key == "model_mismatch"
    assert fake_module.count(PATH_GET, key="022") == 0
    assert fake_module.count(PATH_GET, key="032") == 0
    assert fake_module.count(PATH_SET) == 0

    fake_module.model = 7
    await coordinator.async_refresh()
    assert coordinator.last_update_success


async def test_turn_on_checks_the_model_read_at_command_time(
    coordinator: RavelliCoordinator, fake_module: FakeModule
) -> None:
    """A model change since the last poll stops the command too."""
    fake_module.model = 12

    with pytest.raises(HomeAssistantError) as err:
        await coordinator.async_set_power(True)

    assert err.value.translation_key == "model_mismatch"
    assert fake_module.count(PATH_GET, key="022") == 0
