"""Local rendering-preference switches for the TerraMow map camera.

These switches don't reflect anything on the device itself - they're pure
UI/rendering preferences read by camera.py when it draws the map.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, TerraMowBasicData

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class MapDisplayToggleDescription:
    """描述一个"地图显示开关"：attr_name 对应 TerraMowBasicData 上的同名布尔字段，
    camera.py 在渲染时会读取这个字段来决定是否画出对应的内容。"""

    attr_name: str
    translation_key: str
    icon: str
    default: bool = True  # 必须和 TerraMowBasicData 里同名字段的 dataclass 默认值保持一致


# 注意：show_obstacles 的 attr_name / translation_key 保持不变以保证向后兼容
# （unique_id 由 attr_name 派生，改名会导致现有安装的这个开关被视为新实体）。
MAP_DISPLAY_TOGGLES: tuple[MapDisplayToggleDescription, ...] = (
    MapDisplayToggleDescription("show_obstacles", "show_obstacles", "mdi:image-filter-center-focus"),
    MapDisplayToggleDescription("show_path", "show_path", "mdi:map-marker-path"),
    MapDisplayToggleDescription("show_no_go_zones", "show_no_go_zones", "mdi:block-helper"),
    MapDisplayToggleDescription("show_info_panel", "show_info_panel", "mdi:card-text-outline"),
    MapDisplayToggleDescription("show_scale_bar", "show_scale_bar", "mdi:ruler"),
    MapDisplayToggleDescription("show_compass", "show_compass", "mdi:compass-outline"),
    MapDisplayToggleDescription("show_origin_marker", "show_origin_marker", "mdi:crosshairs"),
    MapDisplayToggleDescription("show_legend", "show_legend", "mdi:format-list-bulleted"),
    # 默认关闭：这个开关会把整张地图旋转，行为变化比其它纯显示/隐藏开关更大，
    # 所以新装用户默认保持和旧版本一致（不旋转），需要的人自己打开。
    MapDisplayToggleDescription("lock_map_north_up", "lock_map_north_up", "mdi:compass-outline", default=False),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TerraMow switch entities."""
    basic_data = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities(
        [
            TerraMowMapDisplaySwitch(basic_data, hass, description)
            for description in MAP_DISPLAY_TOGGLES
        ]
    )


class TerraMowMapDisplaySwitch(SwitchEntity, RestoreEntity):
    """一个纯本地渲染偏好开关：切换 TerraMowBasicData 上的一个布尔字段，
    camera.py 画图时读取同一个字段。不与设备通信，不影响割草机行为。"""

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
        description: MapDisplayToggleDescription,
    ) -> None:
        super().__init__()
        self.basic_data = basic_data
        self.host = basic_data.host
        self.hass = hass
        self._description = description
        self._attr_translation_key = description.translation_key
        self._attr_icon = description.icon

    @property
    def device_info(self) -> DeviceInfo:
        # 挂在和 camera.py 的地图相机相同的 "TerraMow Map" 子设备下，而不是主设备，
        # 这样这些纯本地渲染开关不会和割草机本身的传感器/配置混在一起，
        # 也让它们更清楚地表明自己控制的是地图上的显示，而不是割草机的实际行为。
        return DeviceInfo(
            identifiers={("TerraMowLawnMower", f"{self.basic_data.host}_map")},
            name="TerraMow Map",
            manufacturer="TerraMow",
            model=self.basic_data.lawn_mower.device_model,
            via_device=("TerraMowLawnMower", self.basic_data.host),
        )

    @property
    def unique_id(self) -> str:
        return f"lawn_mower.terramow@{self.host}.{self._description.attr_name}"

    @property
    def is_on(self) -> bool:
        return getattr(self.basic_data, self._description.attr_name, self._description.default)

    @property
    def available(self) -> bool:
        return self.basic_data.lawn_mower is not None

    async def async_added_to_hass(self) -> None:
        """Restore the previous toggle state after a restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            setattr(self.basic_data, self._description.attr_name, last_state.state == "on")

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_value(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_value(False)

    async def _set_value(self, value: bool) -> None:
        setattr(self.basic_data, self._description.attr_name, value)
        self.async_write_ha_state()
        map_camera = self.basic_data.map_camera
        if map_camera is not None:
            await map_camera.async_refresh_after_settings_change()
