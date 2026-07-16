"""Diagnostics support for the TerraMow CE integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from . import DOMAIN, TerraMowBasicData

# Host is a local IP/hostname and password is the MQTT credential -- neither
# is useful for troubleshooting and diagnostics dumps are often pasted into
# public GitHub issues, so both are redacted.
TO_REDACT = {CONF_HOST, CONF_PASSWORD}


def _enum_value(value: Any) -> Any:
    """Return the underlying value of an Enum, or the value unchanged."""
    return getattr(value, "value", value)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    basic_data: TerraMowBasicData = hass.data[DOMAIN][entry.entry_id]
    lawn_mower = basic_data.lawn_mower

    diagnostics: dict[str, Any] = {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "compatibility": {
            "status": basic_data.compatibility_status,
            "reason": basic_data.compatibility_reason,
            "message": basic_data.get_compatibility_message(),
            "firmware_version": basic_data.firmware_version,
        },
    }

    if lawn_mower is None:
        diagnostics["lawn_mower"] = None
        return diagnostics

    diagnostics["lawn_mower"] = {
        "device_model": lawn_mower.device_model,
        "activity": _enum_value(lawn_mower.activity),
        "mission": _enum_value(lawn_mower.mission),
        "sub_mission": _enum_value(lawn_mower.sub_mission),
        "mission_state": _enum_value(lawn_mower.mission_state),
        "power_mode": _enum_value(lawn_mower.power_mode),
        "has_error": lawn_mower.has_error,
        "back_to_station_reason": _enum_value(lawn_mower.back_to_station_reason),
        "fault_reason": lawn_mower.fault_reason,
        "battery_status": lawn_mower.battery_status,
        "current_work_data": lawn_mower.current_work_data,
        "statistics_data": lawn_mower.statistics_data,
        "base_station_time": lawn_mower.base_station_time,
        "blade_time": lawn_mower.blade_time,
        "schedule_data": lawn_mower.schedule_data,
        "global_params": lawn_mower.global_params,
        "map_status": lawn_mower.map_status,
    }

    return diagnostics
