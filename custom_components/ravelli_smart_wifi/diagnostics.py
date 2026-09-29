"""Diagnostics download."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from .api import WinetError
from .coordinator import RavelliConfigEntry

REDACT_ENTRY = {CONF_HOST, CONF_MAC, "unique_id"}
REDACT_SYSTEM = {
    "network",
    "currentIp",
    "currentMask",
    "currentGw",
    "currentApIp",
    "eNowDevs",
}
REDACT_CATEGORY = {"name", "tsense"}
_NAME = 10


def _redact_schedule(schedule: dict[str, Any]) -> dict[str, Any]:
    """Hide the program names: they are free text typed by the owner."""
    programs = [
        [*program[:_NAME], REDACTED if program[_NAME] else ""]
        for program in schedule.get("programs", [])
        if isinstance(program, list) and len(program) > _NAME
    ]
    return {**schedule, "programs": programs}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RavelliConfigEntry
) -> dict[str, Any]:
    """Dump every register category of the stove, without personal data."""
    coordinator = entry.runtime_data
    result: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), REDACT_ENTRY),
        "model": coordinator.model.name,
    }
    try:
        raw = await coordinator.async_read_diagnostics()
    except WinetError as err:
        # The message of the error can hold the address of the module.
        return {**result, "error": type(err).__name__}
    return {
        **result,
        "system": async_redact_data(raw["system"], REDACT_SYSTEM),
        "categories": {
            category: async_redact_data(payload, REDACT_CATEGORY)
            for category, payload in raw["categories"].items()
        },
        "schedule": _redact_schedule(raw["schedule"]),
    }
