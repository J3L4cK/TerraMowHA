"""Local rendering-preference switches for the TerraMow map camera.

These switches don't reflect anything on the device itself - they're pure
UI/rendering preferences read by camera.py when it draws the map.
"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import DOMAIN, TerraMowBasicData

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TerraMow switch entities."""
    basic_data = hass.data[DOMAIN][config_entry.entry_id]

    async_add_entities([TerraMowShowObstaclesSwitch(basic_data, hass)])


class TerraMowShowObstaclesSwitch(SwitchEntity, RestoreEntity):
    """Toggle whether obstacles are drawn on the map camera."""

    _attr_has_entity_name = True
    _attr_translation_key = "show_obstacles"
    _attr_icon = "mdi:image-filter-center-focus"
    _attr_entity_category = EntityCategory.CONFIG

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
        # 挂在和 camera.py 的地图相机相同的 "TerraMow Map" 子设备下，而不是主设备，
        # 这样这个纯本地渲染开关不会和割草机本身的传感器/配置混在一起，
        # 也让它更清楚地表明自己控制的是地图上的显示，而不是割草机的实际行为。
        return DeviceInfo(
            identifiers={("TerraMowLawnMower", f"{self.basic_data.host}_map")},
            name="TerraMow Map",
            manufacturer="TerraMow",
            model=self.basic_data.lawn_mower.device_model,
            via_device=("TerraMowLawnMower", self.basic_data.host),
        )

    @property
    def unique_id(self) -> str:
        return f"lawn_mower.terramow@{self.host}.show_obstacles"

    @property
    def is_on(self) -> bool:
        return self.basic_data.show_obstacles

    @property
    def available(self) -> bool:
        return self.basic_data.lawn_mower is not None

    async def async_added_to_hass(self) -> None:
        """Restore the previous toggle state after a restart."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self.basic_data.show_obstacles = last_state.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        await self._set_show_obstacles(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self._set_show_obstacles(False)

    async def _set_show_obstacles(self, value: bool) -> None:
        self.basic_data.show_obstacles = value
        self.async_write_ha_state()
        map_camera = self.basic_data.map_camera
        if map_camera is not None:
            await map_camera.async_refresh_after_settings_change()
