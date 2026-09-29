"""Binary sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import RavelliConfigEntry, RavelliCoordinator, RavelliData
from .entity import RavelliEntity


@dataclass(frozen=True, kw_only=True)
class RavelliBinarySensorDescription(BinarySensorEntityDescription):
    """Describes one binary sensor and where its value comes from."""

    is_on_fn: Callable[[RavelliData], bool]
    exists_fn: Callable[[RavelliData], bool] = lambda data: True


BINARY_SENSORS: tuple[RavelliBinarySensorDescription, ...] = (
    RavelliBinarySensorDescription(
        key="alarm",
        device_class=BinarySensorDeviceClass.PROBLEM,
        is_on_fn=lambda data: data.state.has_alarm,
    ),
    RavelliBinarySensorDescription(
        key="flame",
        is_on_fn=lambda data: bool(data.state.flame),
        exists_fn=lambda data: data.state.flame is not None,
    ),
    RavelliBinarySensorDescription(
        key="firmware_update",
        device_class=BinarySensorDeviceClass.UPDATE,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda data: bool(data.system.get("fwUpdate")),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the binary sensors the stove has data for."""
    coordinator = entry.runtime_data
    async_add_entities(
        RavelliBinarySensor(coordinator, description)
        for description in BINARY_SENSORS
        if description.exists_fn(coordinator.data)
    )


class RavelliBinarySensor(RavelliEntity, BinarySensorEntity):
    """One on/off fact read from the stove."""

    entity_description: RavelliBinarySensorDescription

    def __init__(
        self,
        coordinator: RavelliCoordinator,
        description: RavelliBinarySensorDescription,
    ) -> None:
        """Keep the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return the fact."""
        return self.entity_description.is_on_fn(self.coordinator.data)
