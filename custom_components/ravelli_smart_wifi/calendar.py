"""Calendar platform: a read-only view of the schedule of the stove."""

from __future__ import annotations

from datetime import date, datetime, timedelta, tzinfo

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity
from .models import MANUAL_SETPOINT, WEEKDAYS, Schedule, ScheduleProgram

# Length given to a program that only starts or only stops the stove.
SINGLE_TIME_LENGTH = timedelta(minutes=15)
# How far the entity looks for its next event: a week and a day.
LOOKAHEAD = timedelta(days=8)


def _event(program: ScheduleProgram, day: date, zone: tzinfo) -> CalendarEvent | None:
    """Return the event of a program on one day."""
    first = program.start or program.end
    if first is None:
        return None
    begin = datetime.combine(day, first, zone)
    if program.start is not None and program.end is not None:
        finish = datetime.combine(day, program.end, zone)
        note = ""
    else:
        finish = begin + SINGLE_TIME_LENGTH
        note = ", start only" if program.start is not None else ", stop only"
    target = (
        "manual"
        if program.temperature == MANUAL_SETPOINT
        else f"{program.temperature} °C"
    )
    return CalendarEvent(
        start=begin,
        end=finish,
        summary=program.name,
        description=f"{target}, power {program.power}{note}",
    )


def schedule_events(
    schedule: Schedule, start: datetime, end: datetime
) -> list[CalendarEvent]:
    """Return the events of the schedule that overlap a window."""
    if not schedule.enabled:
        return []
    start = dt_util.as_local(start)
    end = dt_util.as_local(end)
    zone = start.tzinfo
    assert zone is not None
    events: list[CalendarEvent] = []
    day = start.date()
    while day <= end.date():
        weekday = WEEKDAYS[day.weekday()]
        for program in schedule.programs:
            if program is None or not program.enabled:
                continue
            if weekday not in program.weekdays:
                continue
            event = _event(program, day, zone)
            if event is not None and event.end > start and event.start < end:
                events.append(event)
        day += timedelta(days=1)
    return sorted(events, key=lambda event: event.start)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the calendar of one stove."""
    async_add_entities([RavelliScheduleCalendar(entry.runtime_data)])


class RavelliScheduleCalendar(RavelliEntity, CalendarEntity):
    """Shows when the stove will run by itself."""

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the calendar."""
        super().__init__(coordinator, "schedule")

    @property
    def event(self) -> CalendarEvent | None:
        """Return the event under way, or the next one."""
        now = dt_util.now()
        events = schedule_events(self.coordinator.data.schedule, now, now + LOOKAHEAD)
        return events[0] if events else None

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the events of a window."""
        return schedule_events(self.coordinator.data.schedule, start_date, end_date)
