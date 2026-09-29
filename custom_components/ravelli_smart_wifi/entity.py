"""Base entity."""

from __future__ import annotations

from homeassistant.const import CONF_HOST, CONF_MAC
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER
from .coordinator import RavelliCoordinator


class RavelliEntity(CoordinatorEntity[RavelliCoordinator]):
    """Entity of one stove; unavailable when the module stops answering."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: RavelliCoordinator, key: str) -> None:
        """Name the entity after its key and attach it to the device."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        device_id = entry.unique_id or entry.entry_id
        mac = entry.data.get(CONF_MAC)
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections={(CONNECTION_NETWORK_MAC, mac)} if mac else set(),
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=coordinator.model.name,
            sw_version=coordinator.data.system.get("fwVer"),
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )
