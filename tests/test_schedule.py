"""Tests for the schedule model."""

from dataclasses import replace
from datetime import time
from typing import Any

import pytest

from custom_components.ravelli_smart_wifi.models import (
    InvalidPayloadError,
    Schedule,
    ScheduleProgram,
    ScheduleValidationError,
)

EVENING_RAW = [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"]
FREE_RAW = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, ""]
ALL_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
EVENING = ScheduleProgram(
    name="Evening",
    enabled=True,
    start=time(18, 0),
    end=time(22, 30),
    temperature=22,
    power=1,
    weekdays=ALL_DAYS,
)
EVENING_FIELDS = {
    "p011": 1,
    "p012": 200,
    "p013": 218,
    "p014": 22,
    "p015": 1,
    "p016": 127,
    "p017": "Evening",
}


def answer(*programs: list[Any], enabled: Any = True) -> dict[str, Any]:
    """Build the answer to a schedule read, padded to six slots."""
    rows = [*programs, *([FREE_RAW] * (6 - len(programs)))]
    return {"key": 33, "enabled": enabled, "programs": rows}


def test_program_is_decoded() -> None:
    """Quarters of an hour become minutes and the mask becomes weekdays."""
    assert ScheduleProgram.from_raw(EVENING_RAW) == EVENING


@pytest.mark.parametrize(
    "raw",
    [
        FREE_RAW,
        [2, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Evening"],
        [1, 1, 18, 0, 1, 22, 2, 22, 0, 127, "Evening"],
        [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, ""],
    ],
)
def test_free_slots_decode_to_none(raw: list[Any]) -> None:
    """The vendor UI skips a row with power 0, enabled above 1 or no name."""
    assert ScheduleProgram.from_raw(raw) is None


def test_disabled_times_are_none() -> None:
    """A program can have a stop time only."""
    program = ScheduleProgram.from_raw([1, 0, 18, 0, 1, 22, 2, 22, 1, 127, "Stop"])

    assert program is not None
    assert program.start is None
    assert program.end == time(22, 30)


def test_disabled_program_is_kept() -> None:
    """A disabled program still occupies its slot."""
    program = ScheduleProgram.from_raw([0, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Off"])

    assert program is not None
    assert program.enabled is False


def test_weekday_mask() -> None:
    """Bit 0 is Monday and bit 6 is Sunday."""
    week = ScheduleProgram.from_raw([1, 1, 6, 2, 1, 8, 0, 21, 3, 0b0011111, "Week"])
    sunday = ScheduleProgram.from_raw([1, 1, 6, 2, 1, 8, 0, 21, 3, 0b1000000, "Sun"])

    assert week is not None
    assert week.weekdays == frozenset({"mon", "tue", "wed", "thu", "fri"})
    assert sunday is not None
    assert sunday.weekdays == frozenset({"sun"})


@pytest.mark.parametrize(
    "raw",
    [
        None,
        [],
        "text",
        EVENING_RAW[:10],
        [*EVENING_RAW, 1],
        [1, 1, 24, 0, 1, 22, 2, 22, 1, 127, "Hour"],
        [1, 1, 18, 4, 1, 22, 2, 22, 1, 127, "Quarter"],
        [1, 1, "18", 0, 1, 22, 2, 22, 1, 127, "Text"],
        [1, 1, 18, 0, 1, 22, 2, 22, 1, 127, 5],
    ],
)
def test_malformed_programs_are_rejected(raw: Any) -> None:
    """A short row must raise a decoding error, not an IndexError."""
    with pytest.raises(InvalidPayloadError):
        ScheduleProgram.from_raw(raw)


@pytest.mark.parametrize(
    ("raw", "shape"),
    [
        ([1, 1, 18, 0, 1, 22, 2, 22, 1, "Secret"], "10 items"),
        ([1, 1, 18, 0, 1, 22, 2, 22, 1, 127, "Secret", 1], "12 items"),
        ([1, 1, "Secret", 0, 1, 22, 2, 22, 1, 127, "Secret"], "item 2"),
        ([1, 1, 18, 0, 1, 22, 2, 22, 1, 127, ["Secret"]], "item 10"),
        ([1, 1, 24, 0, 1, 22, 2, 22, 1, 127, "Secret"], "24"),
        ("Secret", "str"),
    ],
)
def test_decode_errors_describe_the_shape_not_the_content(raw: Any, shape: str) -> None:
    """The message reaches the log: never the name typed by the owner."""
    with pytest.raises(InvalidPayloadError) as err:
        ScheduleProgram.from_raw(raw)

    assert "Secret" not in str(err.value)
    assert shape in str(err.value)


def test_program_fields() -> None:
    """Start and stop are packed as enabled, hour and quarter."""
    assert EVENING.to_fields(1) == EVENING_FIELDS


def test_fields_carry_the_slot_number() -> None:
    """Slot 4 uses the prefix p04."""
    assert sorted(EVENING.to_fields(4)) == [
        "p041",
        "p042",
        "p043",
        "p044",
        "p045",
        "p046",
        "p047",
    ]


def test_disabled_time_is_encoded_as_zero() -> None:
    """No enabled bit, no hour, no quarter."""
    assert replace(EVENING, start=None).to_fields(1)["p012"] == 0


def test_schedule_round_trip() -> None:
    """What is read can be written back unchanged."""
    schedule = Schedule.from_payload(answer(EVENING_RAW))

    assert schedule.enabled is True
    assert schedule.programs == (EVENING, None, None, None, None, None)
    assert schedule.to_fields() == {"enabled": 1, **EVENING_FIELDS}


def test_disabled_schedule() -> None:
    """The global flag is sent as 0 or 1."""
    schedule = Schedule.from_payload(answer(EVENING_RAW, enabled=False))

    assert schedule.enabled is False
    assert schedule.to_fields()["enabled"] == 0


@pytest.mark.parametrize(
    ("flag", "enabled"), [(True, True), (False, False), (1, True), (0, False)]
)
def test_global_flag_values(flag: Any, enabled: bool) -> None:
    """A boolean, 0 or 1."""
    assert Schedule.from_payload(answer(EVENING_RAW, enabled=flag)).enabled is enabled


@pytest.mark.parametrize("flag", ["0", "1", 2, -1, None, 1.0, "true"])
def test_global_flag_is_not_coerced(flag: Any) -> None:
    """Written back as it is read: a misread flag could start the stove."""
    with pytest.raises(InvalidPayloadError):
        Schedule.from_payload(answer(EVENING_RAW, enabled=flag))


def test_missing_global_flag_is_rejected() -> None:
    """A missing flag is not an off flag."""
    payload = answer(EVENING_RAW)
    del payload["enabled"]

    with pytest.raises(InvalidPayloadError):
        Schedule.from_payload(payload)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        [],
        {},
        {"programs": "text"},
        {"programs": []},
        {"programs": [FREE_RAW] * 5},
        {"programs": [FREE_RAW] * 7},
    ],
)
def test_malformed_schedules_are_rejected(payload: Any) -> None:
    """The module always sends six rows."""
    with pytest.raises(InvalidPayloadError):
        Schedule.from_payload(payload)


def test_with_program_replaces_one_slot() -> None:
    """The other slots are untouched."""
    morning = replace(EVENING, name="Morning", start=time(6, 30), end=time(8, 0))
    schedule = Schedule.from_payload(answer(EVENING_RAW)).with_program(3, morning)

    assert schedule.programs == (EVENING, None, morning, None, None, None)
    assert schedule.with_program(1, None).programs[0] is None


@pytest.mark.parametrize("slot", [0, 7, -1])
def test_slot_must_exist(slot: int) -> None:
    """Slots are numbered 1 to 6."""
    with pytest.raises(ScheduleValidationError) as err:
        Schedule.from_payload(answer()).with_program(slot, EVENING)

    assert err.value.key == "slot_range"


def test_with_enabled_keeps_the_programs() -> None:
    """Only the global flag changes."""
    schedule = Schedule.from_payload(answer(EVENING_RAW)).with_enabled(False)

    assert schedule.enabled is False
    assert schedule.programs[0] == EVENING


@pytest.mark.parametrize(
    "program",
    [
        EVENING,
        replace(EVENING, temperature=41),
        replace(EVENING, temperature=5, power=5),
        replace(EVENING, start=None),
        replace(EVENING, end=None),
        replace(EVENING, enabled=False, start=None, end=None),
        replace(EVENING, name="A & B = C"),
        replace(EVENING, name="x" * 15),
        replace(EVENING, name="Café"),
        replace(EVENING, name="Été à Noël"),
        replace(EVENING, weekdays=frozenset({"sun"})),
    ],
)
def test_valid_programs_pass(program: ScheduleProgram) -> None:
    """Separators of the form encoding and accents are allowed in a name."""
    program.validate()


@pytest.mark.parametrize(
    ("changes", "key"),
    [
        ({"name": ""}, "name_length"),
        ({"name": "   "}, "name_length"),
        ({"name": "x" * 16}, "name_length"),
        ({"name": "x" * 15 + "é"}, "name_length"),
        ({"name": "a\tb"}, "name_characters"),
        ({"name": "a\nb"}, "name_characters"),
        ({"name": "a\x7fb"}, "name_characters"),
        ({"start": time(18, 10)}, "time_step"),
        ({"end": time(22, 30, 5)}, "time_step"),
        ({"end": time(18, 0)}, "end_before_start"),
        ({"end": time(17, 45)}, "end_before_start"),
        ({"start": None, "end": None}, "no_time"),
        ({"weekdays": frozenset()}, "no_weekday"),
        ({"weekdays": frozenset({"mon", "someday"})}, "no_weekday"),
        ({"temperature": 4}, "temperature_range"),
        ({"temperature": 42}, "temperature_range"),
        ({"power": 0}, "power_range"),
        ({"power": 6}, "power_range"),
    ],
)
def test_invalid_programs_are_refused(changes: dict[str, Any], key: str) -> None:
    """Every rule of the vendor UI has its own error key."""
    with pytest.raises(ScheduleValidationError) as err:
        replace(EVENING, **changes).validate()

    assert err.value.key == key
