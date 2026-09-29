"""Register tables and data model of the RDS stove family.

This module imports nothing from Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

REG_AMBIENT_TEMP = 0
REG_WATER_TEMP = 1
REG_STATUS = 2
REG_ALARM = 3
REG_FLUE_TEMP = 4
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

STATUS_KEYS: dict[int, str] = {
    0: "off",
    1: "pellet_loading",
    2: "ignition",
    3: "waiting_flame",
    4: "flame_present",
    5: "working",
    6: "final_cleaning",
    7: "eco_stop",
    8: "alarm",
    9: "alarm_memory",
}
STATUS_UNKNOWN = "unknown"
STATUS_IGNITING = frozenset({1, 2, 3, 4})
STATUS_ON = frozenset({1, 2, 3, 4, 5, 7})
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
        return self.status_code in STATUS_ON

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
    def flue_temperature(self) -> int | None:
        """Flue gas temperature, raw."""
        return self.raw(REG_FLUE_TEMP)

    @property
    def extractor_speed(self) -> int | None:
        """Extractor speed, raw."""
        return self.raw(REG_EXTRACTOR)

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
