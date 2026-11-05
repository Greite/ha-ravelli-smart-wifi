"""Select platform: the ducting settings of a KTR-AIR BLDC stove."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity
from .models import (
    DUCT_DIRECTION_OPTIONS,
    DUCT_SPLIT_OPTIONS,
    FAN_OPTIONS,
    REG_KTR_DUCT_DIRECTION,
    REG_KTR_DUCT_FAN,
    REG_KTR_DUCT_SPLIT,
    option,
)


@dataclass(frozen=True, kw_only=True)
class RavelliSelectDescription(SelectEntityDescription):
    """Describes one select; the raw value of an option is its index."""

    register: int
    choices: tuple[str, ...]


SELECTS: tuple[RavelliSelectDescription, ...] = (
    RavelliSelectDescription(
        key="ducting_fan", register=REG_KTR_DUCT_FAN, choices=FAN_OPTIONS
    ),
    RavelliSelectDescription(
        key="ducting_direction",
        register=REG_KTR_DUCT_DIRECTION,
        choices=DUCT_DIRECTION_OPTIONS,
    ),
    RavelliSelectDescription(
        key="ducting_split", register=REG_KTR_DUCT_SPLIT, choices=DUCT_SPLIT_OPTIONS
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the ducting selects of a stove in a configuration read on a stove."""
    coordinator = entry.runtime_data
    if coordinator.model.ktr_ducting and coordinator.data.state.has_ducting_controls:
        async_add_entities(
            RavelliSelect(coordinator, description) for description in SELECTS
        )


class RavelliSelect(RavelliEntity, SelectEntity):
    """One ducting register, written with the raw value of the option."""

    entity_description: RavelliSelectDescription

    def __init__(
        self, coordinator: RavelliCoordinator, description: RavelliSelectDescription
    ) -> None:
        """Keep the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        self._attr_options = list(description.choices)

    @property
    def available(self) -> bool:
        """Unavailable once the stove leaves the configuration read."""
        return super().available and self.coordinator.data.state.has_ducting_controls

    @property
    def current_option(self) -> str | None:
        """Return the option of the raw value."""
        description = self.entity_description
        return option(
            description.choices, self.coordinator.data.state.raw(description.register)
        )

    async def async_select_option(self, option: str) -> None:
        """Write the raw value of the option."""
        description = self.entity_description
        await self.coordinator.async_write_register(
            description.register, description.choices.index(option)
        )
