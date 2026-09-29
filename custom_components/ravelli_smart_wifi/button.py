"""Button platform."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
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
    """Create the button of one stove."""
    async_add_entities([RavelliSyncClockButton(entry.runtime_data)])


class RavelliSyncClockButton(RavelliEntity, ButtonEntity):
    """Sets the clock of the stove, which its schedule relies on."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the button."""
        super().__init__(coordinator, "sync_clock")

    async def async_press(self) -> None:
        """Write the local time of Home Assistant to the stove."""
        await self.coordinator.async_sync_clock()
