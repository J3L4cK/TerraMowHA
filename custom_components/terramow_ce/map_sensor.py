from __future__ import annotations
from typing import Any

from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.device_registry import DeviceInfo

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from homeassistant.const import (
    EntityCategory,
    UnitOfArea
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import TerraMowBasicData, DOMAIN
# 移除硬编码的映射，使用翻译系统

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up TerraMow map sensors."""
    basic_data = hass.data[DOMAIN][config_entry.entry_id]
    
    # 创建地图传感器实体
    entities = [
        TerraMowMapStatusSensor(basic_data, hass),
        TerraMowMapAreaSensor(basic_data, hass),
        TerraMowCleanModeSensor(basic_data, hass),
        TerraMowMapBackupCountSensor(basic_data, hass),
        TerraMowHighGrassEdgeTrimModeSensor(basic_data, hass),
    ]
    
    async_add_entities(entities)

class TerraMowMapSensorBase(SensorEntity):
    """地图传感器基类

    回调注册曾经只在 __init__ 里做一次，且只在那一刻
    basic_data.lawn_mower 恰好已经存在时才生效。但 lawn_mower 和 sensor
    platform 是被 HA 并发启动的（hass.config_entries.async_forward_entry_setups），
    先后顺序没有保证，一旦这个 sensor 实体先于 lawn_mower 实体构造出来，
    回调就永远注册不上，self._map_info 永远是空字典，依赖它的子类
    （TerraMowMapAreaSensor、TerraMowCleanModeSensor）就会永远显示
    "Unknown"。现改为在 async_added_to_hass 里注册，并提供一个懒读取
    兜底方法，即使回调没注册上也能靠轮询自愈。
    """
    
    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        super().__init__()
        self.basic_data = basic_data
        self.host = basic_data.host
        self.hass = hass
        self._map_info: dict[str, Any] = {}
        self._callback_registered = False

    async def async_added_to_hass(self) -> None:
        """Register the map-info callback once attached to hass."""
        await super().async_added_to_hass()
        self._try_register_callback()

    def _try_register_callback(self) -> None:
        if self._callback_registered:
            return
        lawn_mower = getattr(self.basic_data, 'lawn_mower', None)
        if lawn_mower:
            lawn_mower.register_map_callback(self._on_map_info)
            self._callback_registered = True

    def _current_map_info(self) -> dict[str, Any]:
        """Return the latest map info, falling back to a live read from
        the lawn_mower entity if the push callback hasn't populated
        anything yet."""
        if self._map_info:
            return self._map_info
        lawn_mower = getattr(self.basic_data, 'lawn_mower', None)
        return (lawn_mower.map_info if lawn_mower else {}) or {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={('TerraMowLawnMower', self.basic_data.host)}, # Corrected typo in identifier
            name='TerraMow',
            manufacturer='TerraMow',
            model=self.basic_data.lawn_mower.device_model # Use dynamically updated model
        )
    
    async def _on_map_info(self, map_info: dict[str, Any]) -> None:
        """处理地图信息更新"""
        self._map_info = map_info
        self.async_write_ha_state()

class TerraMowMapStatusSensor(SensorEntity):
    """地图状态传感器 - 使用dp_117数据"""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:map"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "map_status"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["MAP_STATE_EMPTY", "MAP_STATE_INCOMPLETE", "MAP_STATE_COMPLETE"]
    
    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        super().__init__()
        self.basic_data = basic_data
        self.host = basic_data.host
        self.hass = hass
    
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
        return f"lawn_mower.terramow@{self.host}.map_status"
    
    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if not hasattr(self.basic_data, 'lawn_mower') or not self.basic_data.lawn_mower:
            return None
            
        map_status = self.basic_data.lawn_mower.map_status
        if not map_status:
            return None
            
        return map_status.get('map_state')
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        if not hasattr(self.basic_data, 'lawn_mower') or not self.basic_data.lawn_mower:
            return {}
            
        map_status = self.basic_data.lawn_mower.map_status
        if not map_status:
            return {}
        
        return {
            'is_map_detected': map_status.get('is_map_detected', False),
            'map_id': map_status.get('map_id'),
            'map_number': map_status.get('map_number', 0),
            'is_backing_up_map': map_status.get('is_backing_up_map', False),
            'backup_map_id': map_status.get('backup_map_id'),
            'main_direction_angle': map_status.get('main_direction_angle'),
            'is_spot_mode_map': map_status.get('is_spot_mode_map', False),
            'spot_mode_map_number': map_status.get('spot_mode_map_number', 0),
            'is_able_to_run_build_map': map_status.get('is_able_to_run_build_map', False),
        }

class TerraMowMapAreaSensor(TerraMowMapSensorBase):
    """地图面积传感器"""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:texture-box"
    _attr_native_unit_of_measurement = UnitOfArea.SQUARE_METERS
    _attr_device_class = None  # 没有标准的面积设备类
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "map_area"
    
    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        super().__init__(basic_data, hass)
    
    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.map_area"
    
    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        map_info = self._current_map_info()
        if not map_info:
            return None
        
        # total_area单位为0.1平方米，转换为平方米
        total_area = map_info.get('total_area', 0)
        return round(total_area / 10, 1) if total_area else None


class TerraMowCleanModeSensor(TerraMowMapSensorBase):
    """清洁模式传感器"""
    
    _attr_has_entity_name = True
    _attr_icon = "mdi:broom"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "clean_mode"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["MAP_CLEAN_INFO_MODE_GLOBAL", "MAP_CLEAN_INFO_MODE_SELECT_REGION", "MAP_CLEAN_INFO_MODE_DRAW_REGION", "MAP_CLEAN_INFO_MODE_MOVE_TO_TARGET_POINT"]
    
    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        super().__init__(basic_data, hass)
    
    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.clean_mode"
    
    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        map_info = self._current_map_info()
        if not map_info:
            return None
        
        clean_info = map_info.get('clean_info', {})
        mode = clean_info.get('mode', '')
        
        return mode if mode else None
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        map_info = self._current_map_info()
        if not map_info:
            return {}
        
        clean_info = map_info.get('clean_info', {})
        attrs = {}
        
        # 根据不同的作业模式显示详细信息
        if 'select_region' in clean_info:
            region_ids = clean_info['select_region'].get('region_id', [])
            attrs['selected_regions'] = region_ids
            attrs['selected_regions_count'] = len(region_ids)
        
        return attrs


class _TerraMowMapDataSensorBase(SensorEntity):
    """Shared boilerplate for sensors reading the HTTP-fetched map body
    (ha_map_v1), same source camera.py uses for rendering. Previously
    only visible bundled into the map camera entity's attributes.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        super().__init__()
        self.basic_data = basic_data
        self.host = basic_data.host
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

    def _map_data(self) -> dict:
        if not hasattr(self.basic_data, 'lawn_mower') or not self.basic_data.lawn_mower:
            return {}
        return self.basic_data.lawn_mower.map_data or {}


class TerraMowMapBackupCountSensor(_TerraMowMapDataSensorBase):
    """Number of saved map backups (map body's backup_info_list)."""

    _attr_icon = "mdi:backup-restore"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "map_backup_count"

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.map_backup_count"

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        map_data = self._map_data()
        if not map_data:
            return None
        backup_info = map_data.get('backup_info_list')
        if isinstance(backup_info, list):
            return len(backup_info)
        return 1 if map_data.get('has_backup') else 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        map_data = self._map_data()
        if not map_data:
            return {}
        return {'has_backup': map_data.get('has_backup', False)}


class TerraMowHighGrassEdgeTrimModeSensor(_TerraMowMapDataSensorBase):
    """High-grass edge trim mode (map body's
    mow_param.high_grass_edge_trim_mode.mode)."""

    _attr_icon = "mdi:grass"
    _attr_translation_key = "high_grass_edge_trim_mode"

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.high_grass_edge_trim_mode"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        mow_param = self._map_data().get('mow_param')
        if not isinstance(mow_param, dict):
            return None
        trim_mode = mow_param.get('high_grass_edge_trim_mode')
        if not isinstance(trim_mode, dict):
            return None
        return trim_mode.get('mode')
