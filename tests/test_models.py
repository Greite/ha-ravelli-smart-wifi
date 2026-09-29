"""Tests for the register model."""

from datetime import datetime
from typing import Any

import pytest

from custom_components.ravelli_smart_wifi.models import (
    SUPPORTED_MODELS,
    InvalidPayloadError,
    RegisterNotWritableError,
    StoveState,
    ValueOutOfRangeError,
    encode_clock,
    from_bcd,
    parse_registers,
    to_bcd,
    validate_write,
)

MAIN = [[0, 44], [2, 0], [3, 0], [4, 0], [5, 0], [37, 0], [50, 22], [51, 1]]


def payload(params: list[list[int]], **extra: Any) -> dict[str, Any]:
    """Build the answer to a category read."""
    return {
        "params": params,
        "model": 7,
        "flame": 255,
        "alr": "",
        "name": "NO NAME",
        **extra,
    }


def state(registers: dict[int, int], **extra: Any) -> StoveState:
    """Build a state from a register mapping."""
    params = [[register, value] for register, value in registers.items()]
    return StoveState.from_payloads([payload(params, **extra)])


def test_main_registers_are_decoded() -> None:
    """A capture of an idle AIR-RDS stove decodes to readable values."""
    decoded = StoveState.from_payloads([payload(MAIN)])

    assert decoded.model == 7
    assert decoded.status_code == 0
    assert decoded.status_key == "off"
    assert decoded.ambient_temperature == 22.0
    assert decoded.setpoint == 22
    assert decoded.power == 1
    assert decoded.flue_temperature == 0
    assert decoded.extractor_speed == 0
    assert decoded.flame is None
    assert decoded.alarm_text == ""
    assert decoded.name == "NO NAME"
    assert decoded.is_on is False
    assert decoded.has_alarm is False


def test_categories_are_merged_and_the_last_answer_wins() -> None:
    """Registers of all categories end up in one state."""
    decoded = StoveState.from_payloads(
        [
            payload(MAIN),
            payload([[2, 0], [24, 0], [25, 19], [184, 5], [185, 22]]),
            payload([[2, 5], [73, 0], [74, 1]], flame=1, alr=" AL05 NO IGNITION "),
        ]
    )

    assert decoded.raw(185) == 22
    assert decoded.raw(74) == 1
    assert decoded.raw(999) is None
    assert decoded.status_key == "working"
    assert decoded.flame == 1
    assert decoded.alarm_text == "AL05 NO IGNITION"


@pytest.mark.parametrize(
    ("code", "key", "is_on", "is_igniting", "in_alarm"),
    [
        (0, "off", False, False, False),
        (1, "pellet_loading", True, True, False),
        (2, "ignition", True, True, False),
        (3, "waiting_flame", True, True, False),
        (4, "flame_present", True, True, False),
        (5, "working", True, False, False),
        (6, "final_cleaning", False, False, False),
        (7, "eco_stop", True, False, False),
        (8, "alarm", False, False, True),
        (9, "alarm_memory", False, False, True),
        (42, "unknown", False, False, False),
    ],
)
def test_status_table(
    code: int, key: str, is_on: bool, is_igniting: bool, in_alarm: bool
) -> None:
    """Every status code has a key and the flags the safety rules use."""
    decoded = state({2: code})

    assert decoded.status_key == key
    assert decoded.is_on is is_on
    assert decoded.is_igniting is is_igniting
    assert decoded.in_alarm is in_alarm


def test_manual_set_point_has_no_temperature() -> None:
    """Raw 41 means manual mode, not 41 degrees."""
    decoded = state({2: 0, 50: 41})

    assert decoded.is_manual is True
    assert decoded.setpoint is None


def test_missing_registers_give_none() -> None:
    """A category answer without the usual registers must not raise."""
    decoded = state({2: 5})

    assert decoded.ambient_temperature is None
    assert decoded.setpoint is None
    assert decoded.is_manual is False
    assert decoded.power is None
    assert decoded.flue_temperature is None
    assert decoded.extractor_speed is None
    assert decoded.water_temperature is None
    assert decoded.water_setpoint is None


def test_zero_ambient_temperature_means_no_reading() -> None:
    """The vendor UI shows dashes for a raw value of 0."""
    assert state({2: 0, 0: 0}).ambient_temperature is None


def test_half_degrees_are_kept() -> None:
    """The ambient probe has a resolution of half a degree."""
    assert state({2: 0, 0: 43}).ambient_temperature == 21.5


def test_alarm_register_raises_the_alarm_flag() -> None:
    """An alarm code counts even when the status is not an alarm status."""
    assert state({2: 5, 3: 4}).has_alarm is True
    assert state({2: 8, 3: 0}).has_alarm is True


def test_water_registers() -> None:
    """The hydro model adds a water probe and a water set point."""
    assert state({2: 5, 1: 45, 49: 60}).water_temperature == 45
    assert state({2: 5, 1: 45, 49: 60}).water_setpoint == 60
    assert state({2: 5, 1: 0, 49: 81}).water_temperature is None
    assert state({2: 5, 1: 0, 49: 81}).water_setpoint is None


@pytest.mark.parametrize(
    "answer",
    [
        None,
        [],
        "text",
        {},
        {"params": None},
        {"params": [[1]]},
        {"params": [[1, 2, 3]]},
        {"params": [["1", 2]]},
        {"params": [[1, 2.5]]},
        {"params": [[1, True]]},
        {"params": ["12"]},
    ],
)
def test_malformed_answers_are_rejected(answer: Any) -> None:
    """Anything that is not a list of integer pairs is refused."""
    with pytest.raises(InvalidPayloadError):
        parse_registers(answer)


def test_status_register_is_required() -> None:
    """A state without a status cannot be trusted."""
    with pytest.raises(InvalidPayloadError):
        StoveState.from_payloads([payload([[0, 44]])])


def test_no_answer_is_rejected() -> None:
    """At least one category is needed."""
    with pytest.raises(InvalidPayloadError):
        StoveState.from_payloads([])


def test_model_must_be_a_number() -> None:
    """The model code drives the register table."""
    with pytest.raises(InvalidPayloadError):
        StoveState.from_payloads([payload(MAIN, model="7")])


def test_only_the_rds_family_is_supported() -> None:
    """Three model codes, with the categories each one polls."""
    assert sorted(SUPPORTED_MODELS) == [7, 11, 12]
    assert SUPPORTED_MODELS[7].name == "AIR-RDS"
    assert SUPPORTED_MODELS[11].name == "HYDRO-RDS"
    assert SUPPORTED_MODELS[12].name == "ECO-RDS"
    assert SUPPORTED_MODELS[7].categories == (2, 6, 11)
    assert SUPPORTED_MODELS[11].categories == (2, 11)
    assert SUPPORTED_MODELS[12].categories == (2, 11)
    assert SUPPORTED_MODELS[7].has_ducting and not SUPPORTED_MODELS[7].has_water
    assert SUPPORTED_MODELS[11].has_water and not SUPPORTED_MODELS[11].has_ducting
    assert not SUPPORTED_MODELS[12].has_water
    assert not SUPPORTED_MODELS[12].has_ducting


@pytest.mark.parametrize(
    ("model", "register", "value"),
    [
        (7, 50, 5),
        (7, 50, 41),
        (7, 51, 1),
        (7, 51, 5),
        (7, 73, 0),
        (7, 73, 9),
        (7, 74, 0),
        (7, 74, 20),
        (7, 184, 5),
        (7, 185, 41),
        (7, 59, 7),
        (7, 60, 0x23),
        (11, 49, 30),
        (11, 49, 81),
        (12, 50, 20),
    ],
)
def test_valid_writes_pass(model: int, register: int, value: int) -> None:
    """The bounds are those of the vendor UI, both ends included."""
    validate_write(SUPPORTED_MODELS[model], register, value)


@pytest.mark.parametrize(
    ("register", "value", "minimum", "maximum"),
    [
        (50, 4, 5, 41),
        (50, 42, 5, 41),
        (51, 0, 1, 5),
        (51, 6, 1, 5),
        (73, 10, 0, 9),
        (74, 21, 0, 20),
        (184, 4, 5, 41),
        (60, 0x24, 0x00, 0x23),
    ],
)
def test_out_of_range_writes_are_refused(
    register: int, value: int, minimum: int, maximum: int
) -> None:
    """The error carries what the message needs."""
    with pytest.raises(ValueOutOfRangeError) as err:
        validate_write(SUPPORTED_MODELS[7], register, value)

    assert err.value.register == register
    assert err.value.value == value
    assert err.value.minimum == minimum
    assert err.value.maximum == maximum


@pytest.mark.parametrize(
    ("model", "register"),
    [(7, 49), (11, 184), (12, 184), (12, 49), (7, 0), (7, 2), (7, 999)],
)
def test_registers_outside_the_table_are_refused(model: int, register: int) -> None:
    """Read-only, unknown and other-model registers cannot be written."""
    with pytest.raises(RegisterNotWritableError):
        validate_write(SUPPORTED_MODELS[model], register, 20)


def test_bcd_round_trip() -> None:
    """The clock registers hold two decimal digits in one byte."""
    assert to_bcd(0) == 0x00
    assert to_bcd(18) == 0x18
    assert to_bcd(59) == 0x59
    assert from_bcd(0x57) == 57
    for value in range(100):
        assert from_bcd(to_bcd(value)) == value


@pytest.mark.parametrize("value", [-1, 100])
def test_bcd_holds_two_digits_only(value: int) -> None:
    """Three digits do not fit."""
    with pytest.raises(ValueError, match="two decimal digits"):
        to_bcd(value)


def test_clock_encoding() -> None:
    """Tuesday 29 September 2026, 18:57."""
    assert encode_clock(datetime(2026, 9, 29, 18, 57)) == [
        (59, 2),
        (60, 0x18),
        (61, 0x57),
        (62, 0x29),
        (63, 0x09),
        (64, 0x26),
    ]


def test_sunday_is_day_seven() -> None:
    """The module counts Monday as 1 and Sunday as 7."""
    assert encode_clock(datetime(2026, 10, 4, 0, 0))[0] == (59, 7)
