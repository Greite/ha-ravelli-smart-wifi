"""Actions that edit the schedule stored in the stove."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, ATTR_NAME, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from .const import DOMAIN
from .coordinator import RavelliCoordinator
from .models import (
    MANUAL_SETPOINT,
    NAME_MAX_LENGTH,
    SLOT_COUNT,
    WEEKDAYS,
    ScheduleProgram,
)

SERVICE_SET_PROGRAM = "set_schedule_program"
SERVICE_DELETE_PROGRAM = "delete_schedule_program"

ATTR_SLOT = "slot"
ATTR_ENABLED = "enabled"
ATTR_START = "start"
ATTR_END = "end"
ATTR_MANUAL = "manual"
ATTR_POWER = "power"
ATTR_WEEKDAYS = "weekdays"

_SLOT = vol.All(vol.Coerce(int), vol.Range(min=1, max=SLOT_COUNT))

SET_PROGRAM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_SLOT): _SLOT,
        vol.Required(ATTR_NAME): vol.All(
            cv.string, vol.Length(min=1, max=NAME_MAX_LENGTH)
        ),
        vol.Optional(ATTR_ENABLED, default=True): cv.boolean,
        vol.Optional(ATTR_START): cv.time,
        vol.Optional(ATTR_END): cv.time,
        vol.Optional(ATTR_TEMPERATURE): vol.All(
            vol.Coerce(int), vol.Range(min=5, max=MANUAL_SETPOINT - 1)
        ),
        vol.Optional(ATTR_MANUAL, default=False): cv.boolean,
        vol.Required(ATTR_POWER): vol.All(vol.Coerce(int), vol.Range(min=1, max=5)),
        vol.Required(ATTR_WEEKDAYS): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.In(WEEKDAYS)]
        ),
    }
)

DELETE_PROGRAM_SCHEMA = vol.Schema(
    {vol.Required(ATTR_DEVICE_ID): cv.string, vol.Required(ATTR_SLOT): _SLOT}
)


def _coordinator(hass: HomeAssistant, device_id: str) -> RavelliCoordinator:
    """Return the coordinator of a stove that is loaded."""
    device = dr.async_get(hass).async_get(device_id)
    if device is not None:
        for entry_id in device.config_entries:
            entry = hass.config_entries.async_get_entry(entry_id)
            if (
                entry is not None
                and entry.domain == DOMAIN
                and entry.state is ConfigEntryState.LOADED
            ):
                return entry.runtime_data
    raise ServiceValidationError(
        translation_domain=DOMAIN, translation_key="device_not_found"
    )


async def _async_set_program(call: ServiceCall) -> None:
    """Store one program."""
    data = call.data
    if data[ATTR_MANUAL]:
        temperature = MANUAL_SETPOINT
    elif ATTR_TEMPERATURE in data:
        temperature = data[ATTR_TEMPERATURE]
    else:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="temperature_required"
        )
    program = ScheduleProgram(
        name=data[ATTR_NAME],
        enabled=data[ATTR_ENABLED],
        start=data.get(ATTR_START),
        end=data.get(ATTR_END),
        temperature=temperature,
        power=data[ATTR_POWER],
        weekdays=frozenset(data[ATTR_WEEKDAYS]),
    )
    coordinator = _coordinator(call.hass, data[ATTR_DEVICE_ID])
    await coordinator.async_set_program(data[ATTR_SLOT], program)


async def _async_delete_program(call: ServiceCall) -> None:
    """Free one slot."""
    coordinator = _coordinator(call.hass, call.data[ATTR_DEVICE_ID])
    await coordinator.async_delete_program(call.data[ATTR_SLOT])


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the actions of the integration."""
    hass.services.async_register(
        DOMAIN, SERVICE_SET_PROGRAM, _async_set_program, schema=SET_PROGRAM_SCHEMA
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_PROGRAM,
        _async_delete_program,
        schema=DELETE_PROGRAM_SCHEMA,
    )
