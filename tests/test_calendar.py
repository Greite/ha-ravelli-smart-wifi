"""Tests for the schedule calendar."""

from typing import Any

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ravelli_smart_wifi.calendar import DESCRIPTIONS
from custom_components.ravelli_smart_wifi.const import DOMAIN

from .fake_module import MAC, FakeModule
from .helpers import entity_id_for

MONDAY = "2026-09-28T00:00:00+02:00"
NEXT_MONDAY = "2026-10-05T00:00:00+02:00"


@pytest.fixture(autouse=True)
async def paris(hass: HomeAssistant) -> None:
    """Run every test in a time zone that is not UTC."""
    await hass.config.async_set_time_zone("Europe/Paris")


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    """Set the integration up after the module was prepared."""
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def events(
    hass: HomeAssistant, start: str = MONDAY, end: str = NEXT_MONDAY
) -> list[dict[str, Any]]:
    """Ask the calendar for the events of a window."""
    entity_id = entity_id_for(hass, "calendar", "schedule")
    response = await hass.services.async_call(
        "calendar",
        "get_events",
        {"entity_id": entity_id, "start_date_time": start, "end_date_time": end},
        blocking=True,
        return_response=True,
    )
    return response[entity_id]["events"]


async def test_week_of_a_daily_program(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The evening program runs every day from 18:00 to 22:30."""
    found = await events(hass)

    assert len(found) == 7
    assert found[0]["summary"] == "Evening"
    assert found[0]["start"] == "2026-09-28T18:00:00+02:00"
    assert found[0]["end"] == "2026-09-28T22:30:00+02:00"
    assert found[0]["description"] == "22 °C, power 1"
    assert found[6]["start"] == "2026-10-04T18:00:00+02:00"


async def test_programs_follow_their_weekdays(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """A weekday program has five events, sorted with the others by start."""
    fake_module.programs[1] = [1, 1, 6, 2, 1, 8, 0, 21, 3, 31, "Morning"]
    await setup(hass, config_entry)

    found = await events(hass)

    assert len(found) == 12
    assert [event["summary"] for event in found[:3]] == [
        "Morning",
        "Evening",
        "Morning",
    ]
    assert found[0]["start"] == "2026-09-28T06:30:00+02:00"
    assert found[0]["end"] == "2026-09-28T08:00:00+02:00"
    assert [event["summary"] for event in found[-2:]] == ["Evening", "Evening"]


@pytest.mark.parametrize(
    ("row", "start", "end", "description"),
    [
        (
            [1, 1, 18, 0, 0, 0, 0, 22, 1, 127, "Evening"],
            "2026-09-28T18:00:00+02:00",
            "2026-09-28T18:15:00+02:00",
            "22 °C, power 1, start only",
        ),
        (
            [1, 0, 0, 0, 1, 22, 2, 22, 1, 127, "Evening"],
            "2026-09-28T22:30:00+02:00",
            "2026-09-28T22:45:00+02:00",
            "22 °C, power 1, stop only",
        ),
        (
            [1, 1, 18, 0, 1, 22, 2, 41, 4, 127, "Evening"],
            "2026-09-28T18:00:00+02:00",
            "2026-09-28T22:30:00+02:00",
            "manual, power 4",
        ),
    ],
)
async def test_event_shapes(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_module: FakeModule,
    row: list[Any],
    start: str,
    end: str,
    description: str,
) -> None:
    """A program with one time lasts a quarter of an hour in the calendar."""
    fake_module.programs[0] = row
    await setup(hass, config_entry)

    found = await events(hass)

    assert len(found) == 7
    assert found[0]["start"] == start
    assert found[0]["end"] == end
    assert found[0]["description"] == description


async def test_disabled_program_has_no_events(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The stove ignores it, so the calendar does too."""
    fake_module.programs[0][0] = 0
    await setup(hass, config_entry)

    assert await events(hass) == []


async def test_disabled_schedule_has_no_events(
    hass: HomeAssistant, config_entry: MockConfigEntry, fake_module: FakeModule
) -> None:
    """The global switch empties the calendar."""
    fake_module.schedule_enabled = False
    await setup(hass, config_entry)

    assert await events(hass) == []
    state = hass.states.get(entity_id_for(hass, "calendar", "schedule"))
    assert state.state == STATE_OFF


async def test_window_that_starts_during_an_event(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """An event that is under way belongs to the window."""
    found = await events(
        hass, start="2026-09-28T20:00:00+02:00", end="2026-09-29T12:00:00+02:00"
    )

    assert [event["start"] for event in found] == ["2026-09-28T18:00:00+02:00"]


async def test_window_given_in_another_time_zone(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """The programs are in local time whatever the window is expressed in."""
    found = await events(
        hass, start="2026-09-28T15:00:00+00:00", end="2026-09-28T17:00:00+00:00"
    )

    assert [event["start"] for event in found] == ["2026-09-28T18:00:00+02:00"]


@pytest.mark.freeze_time("2026-09-29T17:00:00+00:00")
async def test_calendar_is_on_during_a_program(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """19:00 in Paris is inside the evening program."""
    state = hass.states.get(entity_id_for(hass, "calendar", "schedule"))

    assert state.state == STATE_ON
    assert state.attributes["message"] == "Evening"
    assert state.attributes["start_time"] == "2026-09-29 18:00:00"
    assert state.attributes["end_time"] == "2026-09-29 22:30:00"


@pytest.mark.freeze_time("2026-09-29T08:00:00+00:00")
async def test_calendar_announces_the_next_program(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """10:00 in Paris is before the evening program."""
    state = hass.states.get(entity_id_for(hass, "calendar", "schedule"))

    assert state.state == STATE_OFF
    assert state.attributes["message"] == "Evening"
    assert state.attributes["start_time"] == "2026-09-29 18:00:00"


async def test_calendar_follows_the_actions(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A program stored by the action shows without waiting for a poll."""
    device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, MAC), init_integration.entry_id
    )
    assert device is not None
    await hass.services.async_call(
        DOMAIN,
        "set_schedule_program",
        {
            "device_id": device.id,
            "slot": 2,
            "name": "Morning",
            "start": "06:30:00",
            "end": "08:00:00",
            "temperature": 21,
            "power": 3,
            "weekdays": ["sat"],
        },
        blocking=True,
    )

    found = await events(hass)

    assert len(found) == 8
    assert [event["summary"] for event in found].count("Morning") == 1


@pytest.mark.parametrize("stop", [[1, 6, 0], [1, 22, 0]])
async def test_program_that_ends_before_it_starts_is_skipped(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_module: FakeModule,
    stop: list[int],
) -> None:
    """A program stored from elsewhere must not break the calendar."""
    fake_module.programs[1] = [1, 1, 22, 0, *stop, 20, 2, 127, "Night"]
    await setup(hass, config_entry)

    found = await events(hass)

    assert len(found) == 7
    assert {event["summary"] for event in found} == {"Evening"}


@pytest.mark.parametrize(
    ("language", "row", "description"),
    [
        ("fr", [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"], "22 °C, puissance 1"),
        ("fr", [1, 1, 18, 0, 1, 22, 2, 41, 4, 127, "Evening"], "manuel, puissance 4"),
        (
            "fr",
            [1, 1, 18, 0, 0, 0, 0, 22, 1, 127, "Evening"],
            "22 °C, puissance 1, début seulement",
        ),
        (
            "fr",
            [1, 0, 0, 0, 1, 22, 2, 22, 1, 127, "Evening"],
            "22 °C, puissance 1, arrêt seulement",
        ),
        (
            "fr-CA",
            [1, 1, 18, 0, 1, 22, 2, 41, 4, 127, "Evening"],
            "manuel, puissance 4",
        ),
        ("de", [1, 1, 18, 0, 1, 22, 2, 41, 4, 127, "Evening"], "manual, power 4"),
        (
            "en-GB",
            [1, 1, 18, 0, 0, 0, 0, 22, 1, 127, "Evening"],
            "22 °C, power 1, start only",
        ),
    ],
)
async def test_description_follows_the_language(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    fake_module: FakeModule,
    language: str,
    row: list[Any],
    description: str,
) -> None:
    """French for a French Home Assistant, English for any other language."""
    hass.config.language = language
    fake_module.programs[0] = row
    await setup(hass, config_entry)

    found = await events(hass)

    assert found[0]["summary"] == "Evening"
    assert found[0]["description"] == description


def test_french_has_every_text_english_has() -> None:
    """A text added in English cannot be forgotten in French."""
    assert set(DESCRIPTIONS["fr"]) == set(DESCRIPTIONS["en"])
