"""Diagnostics download."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import REDACTED, async_redact_data
from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.core import HomeAssistant

from .coordinator import RavelliConfigEntry

REDACT_ENTRY = {CONF_HOST, CONF_MAC, "unique_id"}
# Only these keys are kept; every other key is redacted, so a key added by a
# new firmware never comes out in clear.
KEEP_SYSTEM = {
    "status",
    "fwUpdate",
    "fwVer",
    "boot",
    "board",
    "signal",
    "rssi",
    "client",
    "useTSense",
    "lastDisconnectReason",
    "lastCloudError",
    "apConnected",
    "pairing",
    "show",
    "timeout",
}
KEEP_CATEGORY = {
    "params",
    "cat",
    "model",
    "flame",
    "chrono",
    "alr",
    "signal",
    "authLevel",
    "localWeb",
}
KEEP_SCHEDULE = {"key", "enabled"}
_NAME = 10


def _keep(payload: dict[str, Any] | str, keep: set[str]) -> dict[str, Any]:
    """Redact every key that is not in the allow-list."""
    if isinstance(payload, str):
        return {"error": payload}
    return {key: value if key in keep else REDACTED for key, value in payload.items()}


def _redact_program(program: Any) -> list[Any] | str:
    """Keep the integers of a program row; describe a row of another shape."""
    if not isinstance(program, list):
        return type(program).__name__
    if len(program) != _NAME + 1:
        return f"list of {len(program)} items"
    numbers = [
        item if isinstance(item, int) and not isinstance(item, bool) else REDACTED
        for item in program[:_NAME]
    ]
    return [*numbers, REDACTED if program[_NAME] else ""]


def _redact_schedule(schedule: dict[str, Any] | str) -> dict[str, Any]:
    """Hide the program names, free text typed by the owner, and any non-number."""
    if isinstance(schedule, str):
        return {"error": schedule}
    programs = [_redact_program(program) for program in schedule.get("programs", [])]
    return {**_keep(schedule, KEEP_SCHEDULE), "programs": programs}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: RavelliConfigEntry
) -> dict[str, Any]:
    """Dump every register category of the stove, without personal data."""
    coordinator = entry.runtime_data
    result: dict[str, Any] = {
        "entry": async_redact_data(entry.as_dict(), REDACT_ENTRY),
        "model": coordinator.model.name,
    }
    raw = await coordinator.async_read_diagnostics()
    return {
        **result,
        "system": _keep(raw["system"], KEEP_SYSTEM),
        "categories": {
            category: _keep(payload, KEEP_CATEGORY)
            for category, payload in raw["categories"].items()
        },
        "schedule": _redact_schedule(raw["schedule"]),
    }
