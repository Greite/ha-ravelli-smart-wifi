"""Register tables and data model of the RDS stove family.

This module imports nothing from Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, time
from typing import Any

REG_AMBIENT_TEMP = 0
REG_WATER_TEMP = 1
REG_STATUS = 2
REG_ALARM = 3
REG_EXTRACTOR = 5
REG_DUCT_RIGHT_TEMP = 24
REG_DUCT_LEFT_TEMP = 25
REG_WATER_SETPOINT = 49
REG_SETPOINT = 50
REG_POWER = 51
REG_CLOCK_WEEKDAY = 59
REG_CLOCK_HOUR = 60
REG_CLOCK_MINUTE = 61
REG_CLOCK_DAY = 62
REG_CLOCK_MONTH = 63
REG_CLOCK_YEAR = 64
REG_COMFORT_DELAY = 73
REG_COMFORT_DELTA = 74
REG_DUCT_RIGHT_SETPOINT = 184
REG_DUCT_LEFT_SETPOINT = 185

CATEGORY_MAIN = 2
CATEGORY_DUCTING = 6
CATEGORY_COMFORT = 11

# Special raw values of the set point registers.
MANUAL_SETPOINT = 41
WATER_MANUAL_SETPOINT = 81
DUCT_OFF = 5
DUCT_EXTERNAL = 6

# The module reports 255 when the board has no flame information.
FLAME_UNSUPPORTED = 255

# Codes read on the display of a real stove. Code 4 is "Travail" and also
# "Modulation". The codes 5, 8 and 9 were never seen and have no key.
STATUS_KEYS: dict[int, str] = {
    0: "off",
    1: "ignition",
    2: "waiting_flame",
    3: "flame_present",
    4: "working",
    6: "final_cleaning",
    7: "eco_stop",
}
STATUS_UNKNOWN = "unknown"
STATUS_IGNITING = frozenset({1, 2, 3})
# Every other code, an unknown one included, counts as on: the safe side.
STATUS_NOT_ON = frozenset({0, 6, 8, 9})
# The page of the module calls 8 and 9 alarms. Never seen on hardware: they
# are only kept to refuse turning on.
STATUS_ALARM = frozenset({8, 9})

# Raw bounds of every writable register, as enforced by the vendor UI.
WRITE_BOUNDS: dict[int, tuple[int, int]] = {
    REG_WATER_SETPOINT: (30, WATER_MANUAL_SETPOINT),
    REG_SETPOINT: (5, MANUAL_SETPOINT),
    REG_POWER: (1, 5),
    REG_CLOCK_WEEKDAY: (1, 7),
    REG_CLOCK_HOUR: (0x00, 0x23),
    REG_CLOCK_MINUTE: (0x00, 0x59),
    REG_CLOCK_DAY: (0x01, 0x31),
    REG_CLOCK_MONTH: (0x01, 0x12),
    REG_CLOCK_YEAR: (0x00, 0x99),
    REG_COMFORT_DELAY: (0, 9),
    REG_COMFORT_DELTA: (0, 20),
    REG_DUCT_RIGHT_SETPOINT: (DUCT_OFF, 41),
    REG_DUCT_LEFT_SETPOINT: (DUCT_OFF, 41),
}

_COMMON_WRITABLE = frozenset(
    {
        REG_SETPOINT,
        REG_POWER,
        REG_CLOCK_WEEKDAY,
        REG_CLOCK_HOUR,
        REG_CLOCK_MINUTE,
        REG_CLOCK_DAY,
        REG_CLOCK_MONTH,
        REG_CLOCK_YEAR,
        REG_COMFORT_DELAY,
        REG_COMFORT_DELTA,
    }
)


class InvalidPayloadError(ValueError):
    """The module answered with data that cannot be decoded."""


class RegisterNotWritableError(ValueError):
    """The register is not writable on this stove model."""

    def __init__(self, register: int) -> None:
        """Remember the register."""
        super().__init__(f"register {register} is not writable")
        self.register = register


class ValueOutOfRangeError(ValueError):
    """The value is outside the bounds of the register."""

    def __init__(self, register: int, value: int, minimum: int, maximum: int) -> None:
        """Remember what the error message needs."""
        super().__init__(
            f"value {value} for register {register} is outside {minimum}..{maximum}"
        )
        self.register = register
        self.value = value
        self.minimum = minimum
        self.maximum = maximum


@dataclass(frozen=True, slots=True)
class StoveModel:
    """What the integration knows about one board model."""

    code: int
    name: str
    categories: tuple[int, ...]
    writable: frozenset[int]
    has_ducting: bool = False
    has_water: bool = False


SUPPORTED_MODELS: dict[int, StoveModel] = {
    7: StoveModel(
        code=7,
        name="AIR-RDS",
        categories=(CATEGORY_MAIN, CATEGORY_DUCTING, CATEGORY_COMFORT),
        writable=_COMMON_WRITABLE | {REG_DUCT_RIGHT_SETPOINT, REG_DUCT_LEFT_SETPOINT},
        has_ducting=True,
    ),
    11: StoveModel(
        code=11,
        name="HYDRO-RDS",
        categories=(CATEGORY_MAIN, CATEGORY_COMFORT),
        writable=_COMMON_WRITABLE | {REG_WATER_SETPOINT},
        has_water=True,
    ),
    12: StoveModel(
        code=12,
        name="ECO-RDS",
        categories=(CATEGORY_MAIN, CATEGORY_COMFORT),
        writable=_COMMON_WRITABLE,
    ),
}


def _is_int(value: object) -> bool:
    """Tell a real integer from a boolean or a float."""
    return isinstance(value, int) and not isinstance(value, bool)


def parse_registers(payload: Any) -> dict[int, int]:
    """Turn the answer to a category read into a register mapping."""
    if not isinstance(payload, dict):
        raise InvalidPayloadError("the answer is not an object")
    params = payload.get("params")
    if not isinstance(params, list):
        raise InvalidPayloadError("the answer has no register list")
    registers: dict[int, int] = {}
    for item in params:
        if (
            not isinstance(item, list)
            or len(item) != 2
            or not _is_int(item[0])
            or not _is_int(item[1])
        ):
            raise InvalidPayloadError(f"malformed register entry: {item!r}")
        registers[item[0]] = item[1]
    return registers


def validate_write(model: StoveModel, register: int, value: int) -> None:
    """Refuse a write the vendor UI would not allow."""
    if register not in model.writable:
        raise RegisterNotWritableError(register)
    minimum, maximum = WRITE_BOUNDS[register]
    if not minimum <= value <= maximum:
        raise ValueOutOfRangeError(register, value, minimum, maximum)


@dataclass(frozen=True, slots=True)
class StoveState:
    """State of the stove, decoded from one or more category reads."""

    model: int
    registers: dict[int, int]
    flame: int | None
    alarm_text: str
    name: str

    @classmethod
    def from_payloads(cls, payloads: list[Any]) -> StoveState:
        """Merge the category answers of one polling cycle."""
        if not payloads:
            raise InvalidPayloadError("there is no answer to decode")
        registers: dict[int, int] = {}
        for payload in payloads:
            registers.update(parse_registers(payload))
        if REG_STATUS not in registers:
            raise InvalidPayloadError("the status register is missing")
        last = payloads[-1]
        model = last.get("model")
        if not _is_int(model):
            raise InvalidPayloadError("the model code is missing")
        flame = last.get("flame")
        return cls(
            model=model,
            registers=registers,
            flame=flame if _is_int(flame) and flame != FLAME_UNSUPPORTED else None,
            alarm_text=str(last.get("alr") or "").strip(),
            name=str(last.get("name") or ""),
        )

    def raw(self, register: int) -> int | None:
        """Return the raw value of a register, if the module sent it."""
        return self.registers.get(register)

    @property
    def status_code(self) -> int:
        """Raw status code."""
        return self.registers[REG_STATUS]

    @property
    def status_key(self) -> str:
        """Status as a translation key."""
        return STATUS_KEYS.get(self.status_code, STATUS_UNKNOWN)

    @property
    def is_on(self) -> bool:
        """Whether the stove is running or about to."""
        return self.status_code not in STATUS_NOT_ON

    @property
    def is_igniting(self) -> bool:
        """Whether the stove is between the on command and steady work."""
        return self.status_code in STATUS_IGNITING

    @property
    def in_alarm(self) -> bool:
        """Whether the status is an alarm status."""
        return self.status_code in STATUS_ALARM

    @property
    def has_alarm(self) -> bool:
        """Whether an alarm is active or waiting to be acknowledged."""
        return self.in_alarm or bool(self.raw(REG_ALARM))

    @property
    def ambient_temperature(self) -> float | None:
        """Ambient temperature in degrees Celsius."""
        raw = self.raw(REG_AMBIENT_TEMP)
        return raw / 2 if raw else None

    @property
    def is_manual(self) -> bool:
        """Whether the stove ignores the ambient set point."""
        return self.raw(REG_SETPOINT) == MANUAL_SETPOINT

    @property
    def setpoint(self) -> int | None:
        """Ambient set point in degrees Celsius, None in manual mode."""
        raw = self.raw(REG_SETPOINT)
        return None if raw == MANUAL_SETPOINT else raw

    @property
    def power(self) -> int | None:
        """Power level, 1 to 5."""
        return self.raw(REG_POWER)

    @property
    def extractor_speed(self) -> int | None:
        """Extractor speed in revolutions per minute, 0 when stopped."""
        raw = self.raw(REG_EXTRACTOR)
        # Verified on hardware against the display of the stove.
        return raw * 10 + 250 if raw else raw

    @property
    def water_temperature(self) -> int | None:
        """Water temperature in degrees Celsius."""
        return self.raw(REG_WATER_TEMP) or None

    @property
    def water_setpoint(self) -> int | None:
        """Water set point in degrees Celsius, None in manual mode."""
        raw = self.raw(REG_WATER_SETPOINT)
        return None if raw == WATER_MANUAL_SETPOINT else raw


def to_bcd(value: int) -> int:
    """Encode two decimal digits in one byte."""
    if not 0 <= value <= 99:
        raise ValueError(f"{value} does not fit in two decimal digits")
    return (value // 10) * 16 + value % 10


def from_bcd(raw: int) -> int:
    """Decode one byte holding two decimal digits."""
    return (raw >> 4) * 10 + (raw & 0x0F)


def encode_clock(now: datetime) -> list[tuple[int, int]]:
    """Return the register writes that set the stove clock to a local time."""
    return [
        (REG_CLOCK_WEEKDAY, now.isoweekday()),
        (REG_CLOCK_HOUR, to_bcd(now.hour)),
        (REG_CLOCK_MINUTE, to_bcd(now.minute)),
        (REG_CLOCK_DAY, to_bcd(now.day)),
        (REG_CLOCK_MONTH, to_bcd(now.month)),
        (REG_CLOCK_YEAR, to_bcd(now.year % 100)),
    ]


WEEKDAYS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SLOT_COUNT = 6
NAME_MAX_LENGTH = 15
_PROGRAM_LENGTH = 11
_QUARTER = 15


class ScheduleValidationError(ValueError):
    """A schedule program breaks a rule of the vendor UI."""

    def __init__(self, key: str) -> None:
        """Remember which rule was broken."""
        super().__init__(key)
        self.key = key


def _decode_time(enabled: int, hour: int, quarter: int) -> time | None:
    """Decode one start or stop time."""
    if not 0 <= hour <= 23 or not 0 <= quarter <= 3:
        raise InvalidPayloadError(f"malformed time: {hour}h, quarter {quarter}")
    return time(hour, quarter * _QUARTER) if enabled == 1 else None


def _encode_time(moment: time | None) -> int:
    """Pack one start or stop time as enabled, hour and quarter."""
    if moment is None:
        return 0
    return 1 << 7 | moment.hour << 2 | moment.minute // _QUARTER


@dataclass(frozen=True, slots=True)
class ScheduleProgram:
    """One of the six programs stored by the module."""

    name: str
    enabled: bool
    start: time | None
    end: time | None
    temperature: int
    power: int
    weekdays: frozenset[str]

    @classmethod
    def from_raw(cls, raw: Any) -> ScheduleProgram | None:
        """Decode one row of a schedule read; None is a free slot."""
        # The messages describe the shape of the row, never its content: they
        # reach the log and the row holds a name typed by the owner.
        if not isinstance(raw, list):
            raise InvalidPayloadError(
                f"malformed program: {type(raw).__name__} instead of a list"
            )
        if len(raw) != _PROGRAM_LENGTH:
            raise InvalidPayloadError(
                f"malformed program: {len(raw)} items instead of {_PROGRAM_LENGTH}"
            )
        *numbers, name = raw
        for position, item in enumerate(numbers):
            if not _is_int(item):
                raise InvalidPayloadError(
                    f"malformed program: item {position} is not an integer"
                )
        if not isinstance(name, str):
            raise InvalidPayloadError(
                f"malformed program: item {len(numbers)} is not a text"
            )
        (
            enabled,
            start_enabled,
            start_hour,
            start_quarter,
            stop_enabled,
            stop_hour,
            stop_quarter,
            temperature,
            power,
            days,
        ) = numbers
        # Same test as the vendor UI; a free slot may hold anything else.
        if enabled > 1 or power == 0 or not name:
            return None
        return cls(
            name=name,
            enabled=enabled == 1,
            start=_decode_time(start_enabled, start_hour, start_quarter),
            end=_decode_time(stop_enabled, stop_hour, stop_quarter),
            temperature=temperature,
            power=power,
            weekdays=frozenset(
                day for bit, day in enumerate(WEEKDAYS) if days >> bit & 1
            ),
        )

    def validate(self) -> None:
        """Apply the rules the vendor UI applies before saving."""
        if not self.name.strip() or len(self.name) > NAME_MAX_LENGTH:
            raise ScheduleValidationError("name_length")
        if any(not " " <= char <= "~" for char in self.name):
            raise ScheduleValidationError("name_characters")
        for moment in (self.start, self.end):
            if moment is not None and (
                moment.minute % _QUARTER or moment.second or moment.microsecond
            ):
                raise ScheduleValidationError("time_step")
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ScheduleValidationError("end_before_start")
        if self.enabled and self.start is None and self.end is None:
            raise ScheduleValidationError("no_time")
        if not self.weekdays or not self.weekdays <= set(WEEKDAYS):
            raise ScheduleValidationError("no_weekday")
        if not 5 <= self.temperature <= MANUAL_SETPOINT:
            raise ScheduleValidationError("temperature_range")
        if not 1 <= self.power <= 5:
            raise ScheduleValidationError("power_range")

    def to_fields(self, slot: int) -> dict[str, int | str]:
        """Return the form fields of this program for a slot, 1 to 6."""
        prefix = f"p0{slot}"
        days = sum(1 << bit for bit, day in enumerate(WEEKDAYS) if day in self.weekdays)
        return {
            f"{prefix}1": int(self.enabled),
            f"{prefix}2": _encode_time(self.start),
            f"{prefix}3": _encode_time(self.end),
            f"{prefix}4": self.temperature,
            f"{prefix}5": self.power,
            f"{prefix}6": days,
            f"{prefix}7": self.name,
        }


@dataclass(frozen=True, slots=True)
class Schedule:
    """The whole schedule table and its global switch."""

    enabled: bool
    programs: tuple[ScheduleProgram | None, ...]

    @classmethod
    def from_payload(cls, payload: Any) -> Schedule:
        """Decode the answer to a schedule read."""
        if not isinstance(payload, dict):
            raise InvalidPayloadError("the schedule answer is not an object")
        rows = payload.get("programs")
        if not isinstance(rows, list) or len(rows) != SLOT_COUNT:
            raise InvalidPayloadError("the schedule does not hold six programs")
        # Every write sends the flag back: a misread flag could make the stove
        # start by itself, so only a boolean, 0 or 1 is accepted.
        flag = payload.get("enabled")
        if not isinstance(flag, bool) and not (_is_int(flag) and flag in (0, 1)):
            raise InvalidPayloadError("the global schedule flag is not 0 or 1")
        return cls(
            enabled=flag == 1,
            programs=tuple(ScheduleProgram.from_raw(row) for row in rows),
        )

    def to_fields(self) -> dict[str, int | str]:
        """Return the form fields that write the whole table."""
        fields: dict[str, int | str] = {"enabled": int(self.enabled)}
        for slot, program in enumerate(self.programs, start=1):
            if program is not None:
                fields.update(program.to_fields(slot))
        return fields

    def with_enabled(self, enabled: bool) -> Schedule:
        """Return a copy with the global switch changed."""
        return replace(self, enabled=enabled)

    def with_program(self, slot: int, program: ScheduleProgram | None) -> Schedule:
        """Return a copy with one slot, 1 to 6, replaced or freed."""
        if not 1 <= slot <= SLOT_COUNT:
            raise ScheduleValidationError("slot_range")
        programs = list(self.programs)
        programs[slot - 1] = program
        return replace(self, programs=tuple(programs))
