"""Number platform."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity
from .models import REG_COMFORT_DELAY, REG_COMFORT_DELTA, REG_POWER, WRITE_BOUNDS


@dataclass(frozen=True, kw_only=True)
class RavelliNumberDescription(NumberEntityDescription):
    """Describes one number and the register behind it."""

    register: int


NUMBERS: tuple[RavelliNumberDescription, ...] = (
    RavelliNumberDescription(
        key="power",
        register=REG_POWER,
        mode=NumberMode.SLIDER,
    ),
    RavelliNumberDescription(
        key="comfort_delta",
        register=REG_COMFORT_DELTA,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
    ),
    RavelliNumberDescription(
        key="comfort_delay",
        register=REG_COMFORT_DELAY,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.CONFIG,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the numbers of one stove."""
    async_add_entities(
        RavelliNumber(entry.runtime_data, description) for description in NUMBERS
    )


class RavelliNumber(RavelliEntity, NumberEntity):
    """One writable register, bounded like in the vendor UI."""

    entity_description: RavelliNumberDescription
    _attr_native_step = 1

    def __init__(
        self, coordinator: RavelliCoordinator, description: RavelliNumberDescription
    ) -> None:
        """Take the bounds from the register table."""
        super().__init__(coordinator, description.key)
        self.entity_description = description
        minimum, maximum = WRITE_BOUNDS[description.register]
        self._attr_native_min_value = minimum
        self._attr_native_max_value = maximum

    @property
    def native_value(self) -> float | None:
        """Return the raw value of the register."""
        return self.coordinator.data.state.raw(self.entity_description.register)

    async def async_set_native_value(self, value: float) -> None:
        """Write the register."""
        await self.coordinator.async_write_register(
            self.entity_description.register, int(value)
        )
