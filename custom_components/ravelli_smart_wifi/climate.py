"""Climate platform."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, PRECISION_HALVES, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import RavelliConfigEntry, RavelliCoordinator
from .entity import RavelliEntity
from .models import (
    DUCT_EXTERNAL,
    DUCT_OFF,
    MANUAL_SETPOINT,
    REG_DUCT_LEFT_SETPOINT,
    REG_DUCT_LEFT_TEMP,
    REG_DUCT_RIGHT_SETPOINT,
    REG_DUCT_RIGHT_TEMP,
    REG_POWER,
    REG_SETPOINT,
    REG_WATER_SETPOINT,
    WATER_MANUAL_SETPOINT,
)

PRESET_MANUAL = "manual"
PRESET_EXTERNAL = "external_thermostat"

# Key of the entity: set point register, temperature register.
DUCTS: dict[str, tuple[int, int]] = {
    "duct_right": (REG_DUCT_RIGHT_SETPOINT, REG_DUCT_RIGHT_TEMP),
    "duct_left": (REG_DUCT_LEFT_SETPOINT, REG_DUCT_LEFT_TEMP),
}

HVAC_ACTIONS: dict[int, HVACAction] = {
    0: HVACAction.OFF,
    1: HVACAction.PREHEATING,
    2: HVACAction.PREHEATING,
    3: HVACAction.PREHEATING,
    4: HVACAction.PREHEATING,
    5: HVACAction.HEATING,
    6: HVACAction.OFF,
    7: HVACAction.IDLE,
    8: HVACAction.OFF,
    9: HVACAction.OFF,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RavelliConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the thermostats the stove model has."""
    coordinator = entry.runtime_data
    entities: list[ClimateEntity] = [RavelliStoveClimate(coordinator)]
    if coordinator.model.has_ducting:
        entities.extend(RavelliDuctClimate(coordinator, key) for key in DUCTS)
    if coordinator.model.has_water:
        entities.append(RavelliWaterClimate(coordinator))
    async_add_entities(entities)


class RavelliSetpointClimate(RavelliEntity, ClimateEntity):
    """Thermostat backed by one set point register with special values."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 1
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _register: int
    # Raw values of the register that are a mode, not a temperature.
    _presets: dict[int, str]
    _default_target = 20

    def __init__(self, coordinator: RavelliCoordinator, key: str) -> None:
        """Remember the target the stove has when Home Assistant starts."""
        super().__init__(coordinator, key)
        self._attr_preset_modes = [PRESET_NONE, *self._presets.values()]
        self._last_target = self._numeric_target()

    def _raw(self) -> int | None:
        """Return the raw value of the set point register."""
        return self.coordinator.data.state.raw(self._register)

    def _numeric_target(self) -> int | None:
        """Return the set point when it is a temperature."""
        raw = self._raw()
        if raw is None or raw in self._presets:
            return None
        return raw if self.min_temp <= raw <= self.max_temp else None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Keep the last temperature for the way back from a preset."""
        if (target := self._numeric_target()) is not None:
            self._last_target = target
        super()._handle_coordinator_update()

    @property
    def target_temperature(self) -> float | None:
        """Return the target, None while a preset replaces it."""
        return self._numeric_target()

    @property
    def preset_mode(self) -> str:
        """Return the preset the set point register stands for."""
        raw = self._raw()
        return PRESET_NONE if raw is None else self._presets.get(raw, PRESET_NONE)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Write a target in whole degrees."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        value = round(temperature)
        if not self.min_temp <= value <= self.max_temp:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="value_out_of_range",
                translation_placeholders={
                    "value": str(value),
                    "minimum": str(self.min_temp),
                    "maximum": str(self.max_temp),
                },
            )
        await self.coordinator.async_write_register(self._register, value)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Write the special value of a preset, or the last target."""
        if preset_mode == PRESET_NONE:
            value = self._last_target or self._default_target
        else:
            value = next(
                raw for raw, name in self._presets.items() if name == preset_mode
            )
        await self.coordinator.async_write_register(self._register, value)


class RavelliPowerClimate(RavelliSetpointClimate):
    """Thermostat whose mode is the on/off state of the stove."""

    @property
    def hvac_mode(self) -> HVACMode:
        """Return heat while the stove runs or is about to."""
        return HVACMode.HEAT if self.coordinator.data.state.is_on else HVACMode.OFF

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the stove on or off."""
        await self.coordinator.async_set_power(hvac_mode == HVACMode.HEAT)

    async def async_turn_on(self) -> None:
        """Turn the stove on."""
        await self.coordinator.async_set_power(True)

    async def async_turn_off(self) -> None:
        """Turn the stove off."""
        await self.coordinator.async_set_power(False)


class RavelliStoveClimate(RavelliPowerClimate):
    """The stove: ambient target, power level and manual mode."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_fan_modes = ["1", "2", "3", "4", "5"]
    _attr_min_temp = 5
    _attr_max_temp = 40
    _attr_precision = PRECISION_HALVES
    _register = REG_SETPOINT
    _presets = {MANUAL_SETPOINT: PRESET_MANUAL}

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the thermostat of the stove."""
        super().__init__(coordinator, "stove")

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return what the stove is doing."""
        return HVAC_ACTIONS.get(self.coordinator.data.state.status_code)

    @property
    def current_temperature(self) -> float | None:
        """Return the ambient temperature."""
        return self.coordinator.data.state.ambient_temperature

    @property
    def fan_mode(self) -> str | None:
        """Return the power level as a fan mode."""
        power = self.coordinator.data.state.power
        return None if power is None else str(power)

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Write the power level."""
        await self.coordinator.async_write_register(REG_POWER, int(fan_mode))


class RavelliDuctClimate(RavelliSetpointClimate):
    """One ducted air outlet; the module cannot tell whether it is fitted."""

    _attr_entity_registry_enabled_default = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 7
    _attr_max_temp = 41
    _presets = {DUCT_EXTERNAL: PRESET_EXTERNAL}

    def __init__(self, coordinator: RavelliCoordinator, key: str) -> None:
        """Pick the registers of the right or of the left outlet."""
        self._register, self._temperature_register = DUCTS[key]
        super().__init__(coordinator, key)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return off for the raw value 5."""
        raw = self._raw()
        return HVACMode.OFF if raw is None or raw == DUCT_OFF else HVACMode.HEAT

    @property
    def current_temperature(self) -> float | None:
        """Return the temperature of the outlet, None without a reading."""
        return self.coordinator.data.state.raw(self._temperature_register) or None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Turn the outlet off, or back on at its last target."""
        if hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_register(self._register, DUCT_OFF)
        elif self.hvac_mode == HVACMode.OFF:
            await self.coordinator.async_write_register(
                self._register, self._last_target or self._default_target
            )

    async def async_turn_on(self) -> None:
        """Turn the outlet on."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn the outlet off."""
        await self.async_set_hvac_mode(HVACMode.OFF)


class RavelliWaterClimate(RavelliPowerClimate):
    """Water circuit of a hydro stove."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_min_temp = 30
    _attr_max_temp = 80
    _register = REG_WATER_SETPOINT
    _presets = {WATER_MANUAL_SETPOINT: PRESET_MANUAL}
    _default_target = 60

    def __init__(self, coordinator: RavelliCoordinator) -> None:
        """Create the thermostat of the water circuit."""
        super().__init__(coordinator, "water")

    @property
    def current_temperature(self) -> float | None:
        """Return the water temperature."""
        return self.coordinator.data.state.water_temperature
