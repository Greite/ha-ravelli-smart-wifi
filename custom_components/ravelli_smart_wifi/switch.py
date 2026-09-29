"""Switch platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the switch of one stove."""
    async_add_entities([RavelliScheduleSwitch(entry.runtime_data)])


class RavelliScheduleSwitch(RavelliEntity, SwitchEntity):
    """Global switch of the schedule stored in the stove."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the switch."""
        super().__init__(coordinator, "schedule")

    @property
    def available(self) -> bool:
        """Unavailable while the schedule cannot be read."""
        return super().available and self.coordinator.data.schedule is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the stove follows its programs."""
        schedule = self.coordinator.data.schedule
        return None if schedule is None else schedule.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Make the stove follow its programs."""
        await self.coordinator.async_set_schedule_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Make the stove ignore its programs."""
        await self.coordinator.async_set_schedule_enabled(False)
