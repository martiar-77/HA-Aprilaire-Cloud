"""HA-harness tests for the climate entity: state mapping and control services."""

from __future__ import annotations

import pytest

ENTITY = "climate.whole_home"
DEVICE_ID = "B4825501968E"


async def test_climate_state(hass, setup_integration):
    await setup_integration()
    state = hass.states.get(ENTITY)
    assert state is not None
    assert state.state == "cool"
    assert state.attributes["current_temperature"] == 21.0
    assert state.attributes["current_humidity"] == 68
    assert state.attributes["temperature"] == 21.5  # cool setpoint in cool mode
    assert state.attributes["fan_mode"] == "on"
    assert state.attributes["hvac_action"] == "cooling"


async def test_set_temperature_sets_cool_setpoint(hass, setup_integration, patched_cloud):
    await setup_integration()
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ENTITY, "temperature": 22.0},
        blocking=True,
    )
    patched_cloud.set_thermostat.assert_called_with(DEVICE_ID, "PZ1", heat=20.0, cool=22.22)


async def test_set_fan_mode(hass, setup_integration, patched_cloud):
    await setup_integration()
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": ENTITY, "fan_mode": "auto"},
        blocking=True,
    )
    patched_cloud.set_thermostat.assert_called_with(DEVICE_ID, "PZ1", fan="auto")


async def test_circulate_fan_mode_maps_to_circ(hass, setup_integration, patched_cloud):
    await setup_integration()
    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": ENTITY, "fan_mode": "circulate"},
        blocking=True,
    )
    patched_cloud.set_thermostat.assert_called_with(DEVICE_ID, "PZ1", fan="circ")


async def test_set_hvac_mode_off(hass, setup_integration, patched_cloud):
    await setup_integration()
    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": ENTITY, "hvac_mode": "off"},
        blocking=True,
    )
    patched_cloud.set_thermostat.assert_called_with(DEVICE_ID, "PZ1", mode="off")


async def test_heat_cool_uses_temperature_range(hass, cloud_state, setup_integration, patched_cloud):
    # Flip the device into auto-changeover *before* setup.
    cloud_state["settings"]["thermostatPZ1"]["mode"] = "auto"
    await setup_integration()

    state = hass.states.get(ENTITY)
    assert state.state == "heat_cool"
    assert state.attributes["target_temp_low"] == 20.0   # heat setpoint
    assert state.attributes["target_temp_high"] == 21.5  # cool setpoint
    assert state.attributes.get("temperature") is None

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ENTITY, "target_temp_low": 19.0, "target_temp_high": 23.0},
        blocking=True,
    )
    patched_cloud.set_thermostat.assert_called_with(DEVICE_ID, "PZ1", heat=18.89, cool=22.78)


async def test_sensors_and_binary_sensor(hass, setup_integration):
    await setup_integration()
    assert hass.states.get("sensor.whole_home_indoor_temperature").state == "21.0"
    assert hass.states.get("sensor.whole_home_indoor_humidity").state == "68"
    # Equipment run states are RUNNING binary sensors. Fixture status.json has
    # coolingStatus "comp1" (running), heatingStatus "inactive", isFanOn false,
    # and the humidifier equipmentStatus "inactive". The blower runs during a
    # cool call even though isFanOn is false, so the fan sensor reads "on".
    assert hass.states.get("binary_sensor.whole_home_fan").state == "on"
    assert hass.states.get("binary_sensor.whole_home_heating").state == "off"
    assert hass.states.get("binary_sensor.whole_home_cooling").state == "on"
    assert hass.states.get("binary_sensor.whole_home_humidifier_status").state == "off"


async def test_humidifier_controls(hass, patched_cloud, setup_integration):
    await setup_integration()

    # Fixture humidifier is {"mode": "on", "autoModeSetpoint": 1}.
    assert hass.states.get("switch.whole_home_humidifier").state == "on"
    assert hass.states.get("number.whole_home_humidifier_level").state == "1"

    # Setting a level turns the humidifier on at that level.
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": "number.whole_home_humidifier_level", "value": 4},
        blocking=True,
    )
    patched_cloud.set_humidifier.assert_called_with(DEVICE_ID, mode="on", autoModeSetpoint=4)

    # Turning the switch off sends mode=off.
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.whole_home_humidifier"},
        blocking=True,
    )
    patched_cloud.set_humidifier.assert_called_with(DEVICE_ID, mode="off")


async def test_fan_running_binary_sensor_true(hass, cloud_state, setup_integration):
    cloud_state["status"]["isFanOn"] = True
    await setup_integration()
    assert hass.states.get("binary_sensor.whole_home_fan").state == "on"


async def test_fan_running_off_when_all_equipment_idle(hass, cloud_state, setup_integration):
    # Blower is off only when nothing is running: no independent fan and no
    # heat/cool call driving it.
    cloud_state["status"]["isFanOn"] = False
    cloud_state["status"]["coolingStatus"] = "inactive"
    cloud_state["status"]["heatingStatus"] = "inactive"
    await setup_integration()
    assert hass.states.get("binary_sensor.whole_home_fan").state == "off"


async def test_heat_cool_deadband_pushes_cool(hass, cloud_state, setup_integration, patched_cloud):
    cloud_state["settings"]["thermostatPZ1"]["mode"] = "auto"
    await setup_integration()
    # Heat to 70F (21.11C) with cool at 71F -> cool pushed to 73F.
    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": ENTITY, "target_temp_low": 21.11, "target_temp_high": 21.5},
        blocking=True,
    )
    patched_cloud.set_thermostat.assert_called_with(DEVICE_ID, "PZ1", heat=21.11, cool=22.78)
