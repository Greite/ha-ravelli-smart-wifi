"""Sensor platform."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from .coordinator import RavelliConfigEntry, RavelliCoordinator, RavelliData
from .entity import RavelliEntity
from .models import REG_ALARM, STATUS_KEYS, STATUS_UNKNOWN

ALARM_NONE = "none"


def _status(data: RavelliData) -> str | None:
    """Return the status key; None gives the unknown state."""
    key = data.state.status_key
    return None if key == STATUS_UNKNOWN else key


@dataclass(frozen=True, kw_only=True)
class RavelliSensorDescription(SensorEntityDescription):
    """Describes one sensor and where its value comes from."""

    value_fn: Callable[[RavelliData], StateType]
    raw_fn: Callable[[RavelliData], int | None] | None = None


SENSORS: tuple[RavelliSensorDescription, ...] = (
    RavelliSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_KEYS.values()),
        value_fn=_status,
        raw_fn=lambda data: data.state.status_code,
    ),
    RavelliSensorDescription(
        key="alarm",
        value_fn=lambda data: data.state.alarm_text or ALARM_NONE,
        raw_fn=lambda data: data.state.raw(REG_ALARM),
    ),
    RavelliSensorDescription(
        key="ambient_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.state.ambient_temperature,
    ),
    RavelliSensorDescription(
        key="flue_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.state.flue_temperature,
    ),
    # The scale of this register is not verified: raw value, no unit.
    RavelliSensorDescription(
        key="extractor_speed",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.state.extractor_speed,
    ),
    RavelliSensorDescription(
        key="wifi_signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.system.get("rssi"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the sensors of one stove."""
    async_add_entities(
        RavelliSensor(entry.runtime_data, description) for description in SENSORS
    )


class RavelliSensor(RavelliEntity, SensorEntity):
    """One value read from the stove."""

    entity_description: RavelliSensorDescription

    def __init__(
        self, coordinator: RavelliCoordinator, description: RavelliSensorDescription
    ) -> None:
        """Keep the description."""
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the decoded value."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the raw code of the status and of the alarm."""
        if self.entity_description.raw_fn is None:
            return None
        return {"raw_value": self.entity_description.raw_fn(self.coordinator.data)}
