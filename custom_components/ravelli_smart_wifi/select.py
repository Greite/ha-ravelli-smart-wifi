"""Select platform: the rear left fan of a KTR-AIR BLDC stove."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity
from .models import FAN_OPTIONS, REG_KTR_DUCT_FAN, option

# Selects of the 2026.10.6b4 to 2026.11.1b2 betas, removed: they moved no air.
# ponytail: drop this cleanup once no beta install holds them.
_REMOVED_KEYS = ("ducting_direction", "ducting_split")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the rear left fan of a stove in a configuration read on a stove."""
    registry = er.async_get(hass)
    device_id = entry.unique_id or entry.entry_id
    for key in _REMOVED_KEYS:
        if entity_id := registry.async_get_entity_id(
            "select", DOMAIN, f"{device_id}_{key}"
        ):
            registry.async_remove(entity_id)
    coordinator = entry.runtime_data
    if coordinator.model.ktr_ducting and coordinator.data.state.has_ducting_controls:
        async_add_entities([RavelliDuctingFan(coordinator)])


class RavelliDuctingFan(RavelliEntity, SelectEntity):
    """Register 188, written with the raw value of the option."""

    _attr_options = list(FAN_OPTIONS)

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the select."""
        super().__init__(coordinator, "ducting_fan")

    @property
    def available(self) -> bool:
        """Unavailable once the stove leaves the configuration read."""
        return super().available and self.coordinator.data.state.has_ducting_controls

    @property
    def current_option(self) -> str | None:
        """Return the option of the raw value."""
        return option(FAN_OPTIONS, self.coordinator.data.state.raw(REG_KTR_DUCT_FAN))

    async def async_select_option(self, option: str) -> None:
        """Write the raw value of the option."""
        await self.coordinator.async_write_register(
            REG_KTR_DUCT_FAN, FAN_OPTIONS.index(option)
        )
