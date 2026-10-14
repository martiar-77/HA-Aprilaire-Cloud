"""Climate platform for Aprilaire (Cloud)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AprilaireConfigEntry
from .const import (
    FAN_AUTO,
    FAN_CIRC,
    FAN_CIRCULATE,
    FAN_ON,
    MODE_AUTO,
    MODE_COOL,
    MODE_HEAT,
    MODE_OFF,
)
from .entity import AprilaireEntity, sensor_reading
from .setpoints import resolve_setpoints

# Aprilaire operates natively in Fahrenheit at 0.5 degF steps, but the API speaks
# Celsius. We report Celsius and let HA convert to the user's configured unit.
MIN_TEMP_C = 4.5   # ~40 degF
MAX_TEMP_C = 37.0  # ~99 degF
TEMP_STEP_C = 0.5

MODE_TO_HVAC = {
    MODE_OFF: HVACMode.OFF,
    MODE_HEAT: HVACMode.HEAT,
    MODE_COOL: HVACMode.COOL,
    MODE_AUTO: HVACMode.HEAT_COOL,
}
HVAC_TO_MODE = {v: k for k, v in MODE_TO_HVAC.items()}

FAN_TO_HA = {FAN_AUTO: FAN_AUTO, FAN_ON: FAN_ON, FAN_CIRC: FAN_CIRCULATE}
HA_TO_FAN = {v: k for k, v in FAN_TO_HA.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AprilaireConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Aprilaire climate entity."""
    async_add_entities([AprilaireClimate(entry.runtime_data)])


class AprilaireClimate(AprilaireEntity, ClimateEntity):
    """A single Aprilaire thermostat zone as an HA climate entity."""

    _attr_name = None  # the device name is the entity name
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = TEMP_STEP_C
    _attr_min_temp = MIN_TEMP_C
    _attr_max_temp = MAX_TEMP_C
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.HEAT_COOL]
    _attr_fan_modes = [FAN_AUTO, FAN_ON, FAN_CIRCULATE]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{self._device_id}_{coordinator.zone}_climate"

    # -- current readings -----------------------------------------------------

    @property
    def current_temperature(self) -> float | None:
        return sensor_reading(self._status.get("tempSensors"), "control")

    @property
    def current_humidity(self) -> float | None:
        value = sensor_reading(self._status.get("humSensors"), "control")
        return value

    @property
    def hvac_mode(self) -> HVACMode | None:
        return MODE_TO_HVAC.get(self._settings.get("mode"))

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        status = self._status
        if status.get("heatingStatus") not in (None, "inactive"):
            return HVACAction.HEATING
        if status.get("coolingStatus") not in (None, "inactive"):
            return HVACAction.COOLING
        if status.get("isFanOn"):
            return HVACAction.FAN
        return HVACAction.IDLE

    @property
    def fan_mode(self) -> str | None:
        return FAN_TO_HA.get(self._settings.get("fan"))

    # -- setpoints ------------------------------------------------------------

    @property
    def target_temperature(self) -> float | None:
        """Single setpoint in heat / cool modes; None in heat_cool (uses range)."""
        mode = self.hvac_mode
        if mode == HVACMode.HEAT:
            return self._settings.get("heat")
        if mode == HVACMode.COOL:
            return self._settings.get("cool")
        return None

    @property
    def target_temperature_low(self) -> float | None:
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._settings.get("heat")
        return None

    @property
    def target_temperature_high(self) -> float | None:
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return self._settings.get("cool")
        return None

    # -- commands -------------------------------------------------------------

    async def async_set_temperature(self, **kwargs: Any) -> None:
        heat: float | None = kwargs.get(ATTR_TARGET_TEMP_LOW)
        cool: float | None = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        if (temp := kwargs.get(ATTR_TEMPERATURE)) is not None:
            mode = self.hvac_mode
            if mode == HVACMode.HEAT:
                heat = temp
            elif mode == HVACMode.COOL:
                cool = temp
        if heat is None and cool is None:
            return
        # The device only honours whole-degF setpoints encoded as 2-decimal
        # Celsius, sent as a heat+cool pair that respects the 3 degF deadband.
        changes = resolve_setpoints(
            self._settings.get("heat"), self._settings.get("cool"), heat, cool
        )
        await self.coordinator.async_set_thermostat(**changes)

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self.coordinator.async_set_thermostat(mode=HVAC_TO_MODE[hvac_mode])

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self.coordinator.async_set_thermostat(fan=HA_TO_FAN[fan_mode])

    async def async_turn_off(self) -> None:
        await self.coordinator.async_set_thermostat(mode=MODE_OFF)

    async def async_turn_on(self) -> None:
        # Restore auto-changeover; the user can narrow to heat/cool afterwards.
        await self.coordinator.async_set_thermostat(mode=MODE_AUTO)
