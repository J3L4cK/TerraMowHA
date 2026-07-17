from __future__ import annotations
import logging
import json

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TerraMowBasicData, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TerraMow binary sensor entities."""
    basic_data = hass.data[DOMAIN][config_entry.entry_id]

    entities = [
        TerraMowChargingSensor(basic_data, hass),
        TerraMowMqttConnectedSensor(basic_data, hass),
        TerraMowNaviLocatedSensor(basic_data, hass),
        TerraMowUpgradingSensor(basic_data, hass),
        TerraMowSavingDataSensor(basic_data, hass),
        TerraMowDataConversionSensor(basic_data, hass),
        TerraMowPowerSwitchSensor(basic_data, hass),
    ]

    async_add_entities(entities)


class TerraMowChargingSensor(BinarySensorEntity):
    """Binary sensor for the TerraMow charging state."""

    _attr_has_entity_name = True
    _attr_translation_key = "charging_state"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the charging sensor."""
        super().__init__()
        self.basic_data = basic_data
        self.host = self.basic_data.host
        self.hass = hass
        self._attr_is_on: bool | None = None
        _LOGGER.info("TerraMowChargingSensor entity created") # Callback is no longer needed here

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={('TerraMowLawnMower', self.basic_data.host)}, # Corrected typo in identifier
            name='TerraMow',
            manufacturer='TerraMow',
            model=self.basic_data.lawn_mower.device_model # Use dynamically updated model
        )

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.charging_state"

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        if not hasattr(self.basic_data, 'lawn_mower') or not self.basic_data.lawn_mower:
            return None

        battery_status = self.basic_data.lawn_mower.battery_status
        charger_connected = battery_status.get('charger_connected')

        return bool(charger_connected) if charger_connected is not None else None

    @property
    def available(self):
        """Return True if entity is available."""
        return self.basic_data.lawn_mower is not None


class TerraMowMqttConnectedSensor(BinarySensorEntity):
    """Whether the integration currently has an MQTT connection to the mower.

    lawn_mower.py used to fold "we lost the MQTT connection" and "the
    mower itself reported a fault" into the same activity=ERROR state,
    with no way to tell them apart from the UI. This entity reflects
    connectivity on its own.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "mqtt_connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the connectivity sensor."""
        super().__init__()
        self.basic_data = basic_data
        self.host = self.basic_data.host
        self.hass = hass

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={('TerraMowLawnMower', self.basic_data.host)},
            name='TerraMow',
            manufacturer='TerraMow',
            model=self.basic_data.lawn_mower.device_model
        )

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.mqtt_connected"

    @property
    def is_on(self) -> bool | None:
        """Return true if MQTT is currently connected."""
        if not hasattr(self.basic_data, 'lawn_mower') or not self.basic_data.lawn_mower:
            return None
        return self.basic_data.lawn_mower.mqtt_connected


class _TerraMowLawnMowerFlagSensor(BinarySensorEntity):
    """Shared boilerplate for simple dp_107-boolean-backed binary sensors."""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _flag_attr: str = ""  # name of the attribute on TerraMowLawnMowerEntity to read
    _unique_id_suffix: str = ""

    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        super().__init__()
        self.basic_data = basic_data
        self.host = self.basic_data.host
        self.hass = hass

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={('TerraMowLawnMower', self.basic_data.host)},
            name='TerraMow',
            manufacturer='TerraMow',
            model=self.basic_data.lawn_mower.device_model
        )

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.{self._unique_id_suffix}"

    @property
    def is_on(self) -> bool | None:
        """Return the underlying dp_107 flag."""
        if not hasattr(self.basic_data, 'lawn_mower') or not self.basic_data.lawn_mower:
            return None
        return getattr(self.basic_data.lawn_mower, self._flag_attr)


class TerraMowNaviLocatedSensor(_TerraMowLawnMowerFlagSensor):
    """Whether the mower currently has accurate navigation/localization.

    dp_107's is_robot_navi_located was parsed and immediately discarded.
    It matters: if this goes false, the mower has lost track of where it
    is (picked up, moved, vision confused) and navigation/mowing accuracy
    is not trustworthy until it recovers.
    """

    _attr_translation_key = "navi_located"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _flag_attr = "is_robot_navi_located"
    _unique_id_suffix = "navi_located"

    @property
    def is_on(self) -> bool | None:
        """Return True (problem) when navigation is NOT located."""
        if not hasattr(self.basic_data, 'lawn_mower') or not self.basic_data.lawn_mower:
            return None
        located = self.basic_data.lawn_mower.is_robot_navi_located
        if located is None:
            return None
        return not located


class TerraMowUpgradingSensor(_TerraMowLawnMowerFlagSensor):
    """Whether the mower is currently applying a firmware update (dp_107)."""

    _attr_translation_key = "upgrading"
    _attr_icon = "mdi:tray-arrow-down"
    _flag_attr = "is_upgrading"
    _unique_id_suffix = "upgrading"


class TerraMowSavingDataSensor(_TerraMowLawnMowerFlagSensor):
    """Whether the mower is currently saving data (dp_107).

    Per TerraMow's own docs: "the robot may not respond to operation
    commands" while this is true -- previously invisible, so a command
    sent during this window just silently appeared to do nothing.
    """

    _attr_translation_key = "saving_data"
    _attr_icon = "mdi:content-save-outline"
    _flag_attr = "is_saving_data"
    _unique_id_suffix = "saving_data"


class TerraMowDataConversionSensor(_TerraMowLawnMowerFlagSensor):
    """Whether the mower is converting data for compatibility (dp_107),
    e.g. migrating stored data after a firmware update."""

    _attr_translation_key = "data_conversion_in_progress"
    _attr_icon = "mdi:database-sync-outline"
    _flag_attr = "is_data_conversion_in_progress"
    _unique_id_suffix = "data_conversion_in_progress"


class TerraMowPowerSwitchSensor(BinarySensorEntity):
    """Physical power switch state, promoted out of dp_108.

    is_switch_on was already available -- it's parsed as part of
    battery_status -- but only ever surfaced nested inside BatterySensor's
    extra_state_attributes, unusable directly in automations/dashboards.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "power_switch"
    _attr_device_class = BinarySensorDeviceClass.POWER
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the power switch sensor."""
        super().__init__()
        self.basic_data = basic_data
        self.host = self.basic_data.host
        self.hass = hass

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={('TerraMowLawnMower', self.basic_data.host)},
            name='TerraMow',
            manufacturer='TerraMow',
            model=self.basic_data.lawn_mower.device_model
        )

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.power_switch"

    @property
    def is_on(self) -> bool | None:
        """Return true if the mower's physical power switch is on."""
        if not hasattr(self.basic_data, 'lawn_mower') or not self.basic_data.lawn_mower:
            return None

        battery_status = self.basic_data.lawn_mower.battery_status
        if not battery_status:
            return None

        is_switch_on = battery_status.get('is_switch_on')
        return bool(is_switch_on) if is_switch_on is not None else None

    @property
    def available(self):
        """Return True if entity is available."""
        return self.basic_data.lawn_mower is not None
