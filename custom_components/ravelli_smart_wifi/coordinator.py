"""Polling, locking, safety rules and commands."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import WinetClient, WinetConnectionError, WinetError, WinetResponseError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DIAGNOSTIC_CATEGORIES,
    DOMAIN,
    FAST_REFRESH_STEPS,
    SLOW_REFRESH_INTERVAL,
)
from .models import (
    CATEGORY_MAIN,
    SLOT_COUNT,
    InvalidPayloadError,
    RegisterNotWritableError,
    Schedule,
    ScheduleProgram,
    ScheduleValidationError,
    StoveModel,
    StoveState,
    ValueOutOfRangeError,
    encode_clock,
    validate_write,
)

_LOGGER = logging.getLogger(__name__)

type RavelliConfigEntry = ConfigEntry[RavelliCoordinator]


@dataclass(frozen=True, slots=True)
class RavelliData:
    """What one polling cycle knows about the stove."""

    state: StoveState
    system: dict[str, Any]
    schedule: Schedule


def _invalid(key: str, **placeholders: str) -> ServiceValidationError:
    """Build the error raised for an input that breaks a rule."""
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def _failed(key: str) -> HomeAssistantError:
    """Build the error raised when the module does not do what was asked."""
    return HomeAssistantError(translation_domain=DOMAIN, translation_key=key)


def _check_slot(slot: int) -> None:
    if not 1 <= slot <= SLOT_COUNT:
        raise _invalid("schedule_slot_range")


class RavelliCoordinator(DataUpdateCoordinator[RavelliData]):
    """Owns every exchange with one module."""

    config_entry: RavelliConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: RavelliConfigEntry,
        client: WinetClient,
        model: StoveModel,
    ) -> None:
        """Set the polling interval from the options."""
        self._normal_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=self._normal_interval,
        )
        self.client = client
        self.model = model
        # The module handles one request at a time.
        self._lock = asyncio.Lock()
        self._system: dict[str, Any] = {}
        self._schedule: Schedule | None = None
        self._slow_read_at: datetime | None = None
        self._fast_steps: list[int] = []

    async def _async_update_data(self) -> RavelliData:
        try:
            async with self._lock:
                payloads = [
                    await self.client.get_registers(category)
                    for category in self.model.categories
                ]
                now = dt_util.utcnow()
                if (
                    self._schedule is None
                    or self._slow_read_at is None
                    or (now - self._slow_read_at).total_seconds()
                    >= SLOW_REFRESH_INTERVAL
                ):
                    self._system = await self.client.get_status()
                    self._schedule = Schedule.from_payload(
                        await self.client.get_schedule()
                    )
                    self._slow_read_at = now
                schedule = self._schedule
            state = StoveState.from_payloads(payloads)
        except (WinetError, InvalidPayloadError) as err:
            raise UpdateFailed(str(err)) from err
        finally:
            self.update_interval = (
                timedelta(seconds=self._fast_steps.pop(0))
                if self._fast_steps
                else self._normal_interval
            )
        return RavelliData(state=state, system=self._system, schedule=schedule)

    async def _async_command(self, command: Callable[[], Awaitable[None]]) -> None:
        """Run one command under the lock, then read the result back."""
        try:
            try:
                async with self._lock:
                    await command()
            except WinetConnectionError as err:
                raise _failed("cannot_connect") from err
            except (WinetResponseError, InvalidPayloadError) as err:
                raise _failed("command_refused") from err
        except HomeAssistantError:
            # The command may have changed part of the stove: show what it
            # holds now, schedule included, at the normal pace.
            self._slow_read_at = None
            await self.async_refresh()
            raise
        self._fast_steps = list(FAST_REFRESH_STEPS)
        await self.async_refresh()

    async def async_write_register(self, register: int, value: int) -> None:
        """Write one register of the model table."""
        try:
            validate_write(self.model, register, value)
        except RegisterNotWritableError as err:
            raise _invalid("register_not_writable", register=str(register)) from err
        except ValueOutOfRangeError as err:
            raise _invalid(
                "value_out_of_range",
                value=str(value),
                minimum=str(err.minimum),
                maximum=str(err.maximum),
            ) from err
        await self._async_command(lambda: self.client.set_register(register, value))

    async def async_set_power(self, on: bool) -> None:
        """Turn the stove on or off, if its current state allows it."""

        async def command() -> None:
            # The polled state can be half a minute old: read it again.
            state = StoveState.from_payloads(
                [await self.client.get_registers(CATEGORY_MAIN)]
            )
            if on:
                if state.in_alarm:
                    raise _invalid("turn_on_in_alarm")
                if state.is_on:
                    return
            else:
                if state.is_igniting and state.flame == 0:
                    raise _invalid("turn_off_during_ignition")
                if state.status_code == 0:
                    return
            await self.client.set_power(on)

        await self._async_command(command)

    async def async_set_schedule_enabled(self, enabled: bool) -> None:
        """Change the global switch of the schedule."""
        await self._async_change_schedule(
            lambda schedule: schedule.with_enabled(enabled)
        )

    async def async_set_program(self, slot: int, program: ScheduleProgram) -> None:
        """Store one program in a slot, 1 to 6."""
        _check_slot(slot)
        try:
            program.validate()
        except ScheduleValidationError as err:
            raise _invalid(f"schedule_{err.key}") from err
        await self._async_change_schedule(
            lambda schedule: schedule.with_program(slot, program)
        )

    async def async_delete_program(self, slot: int) -> None:
        """Free one slot, 1 to 6."""
        _check_slot(slot)

        async def command() -> None:
            current = Schedule.from_payload(await self.client.get_schedule())
            if current.programs[slot - 1] is None:
                self._schedule = current
                return
            await self.client.delete_program(slot - 1)
            await self._async_verify_schedule(current.with_program(slot, None))

        await self._async_command(command)

    async def _async_change_schedule(
        self, change: Callable[[Schedule], Schedule]
    ) -> None:
        """Read the table, change it, write it and read it back."""

        async def command() -> None:
            current = Schedule.from_payload(await self.client.get_schedule())
            wanted = change(current)
            await self.client.set_schedule(wanted.to_fields())
            await self._async_verify_schedule(wanted)

        await self._async_command(command)

    async def _async_verify_schedule(self, wanted: Schedule) -> None:
        stored = Schedule.from_payload(await self.client.get_schedule())
        self._schedule = stored
        if stored != wanted:
            raise _failed("schedule_mismatch")

    async def async_sync_clock(self) -> None:
        """Set the stove clock to the local time of Home Assistant."""
        writes = encode_clock(dt_util.now())

        async def command() -> None:
            for register, value in writes:
                validate_write(self.model, register, value)
                await self.client.set_register(register, value)

        await self._async_command(command)

    async def async_read_diagnostics(self) -> dict[str, Any]:
        """Read every register category, the status and the schedule.

        A request that fails gives the name of its error class in place of
        its answer; the message can hold the address of the module.
        """

        async def read(request: Awaitable[dict[str, Any]]) -> dict[str, Any] | str:
            try:
                return await request
            except WinetError as err:
                return type(err).__name__

        async with self._lock:
            categories = {
                str(category): await read(self.client.get_registers(category))
                for category in range(DIAGNOSTIC_CATEGORIES)
            }
            return {
                "system": await read(self.client.get_status()),
                "categories": categories,
                "schedule": await read(self.client.get_schedule()),
            }
