"""Config flow for the TerraMow integration."""

from __future__ import annotations

import json
import logging
from typing import Any

import paho.mqtt.client as mqtt_client
import voluptuous as vol

from homeassistant.config_entries import ConfigFlow as BaseConfigFlow, OptionsFlow
# 移除 ConfigFlowResult 导入
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import MQTT_PORT, MQTT_USERNAME, DOMAIN, CONF_ZONE_NAMES

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """验证用户输入并测试MQTT连接."""
    try:
        def mqtt_connect() -> bool:
            client = mqtt_client.Client()
            client.username_pw_set(MQTT_USERNAME, data[CONF_PASSWORD])
            try:
                client.connect(data[CONF_HOST], MQTT_PORT, 5)
                client.disconnect()
                return True
            except Exception as err:
                _LOGGER.error("Connection failed: %s", err)
                return False

        # 在executor中运行同步MQTT连接测试
        is_valid = await hass.async_add_executor_job(mqtt_connect)

        if not is_valid:
            raise InvalidAuth

        return {"title": f"TerraMow CE ({data[CONF_HOST]})"}

    except Exception as err:
        _LOGGER.exception("Unexpected error: %s", err)
        raise CannotConnect from err

class ConfigFlow(BaseConfigFlow, domain=DOMAIN):
    """Handle a config flow for TerraMow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ):  # 移除返回值类型注解
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                host = user_input[CONF_HOST]
                _LOGGER.info('Setting up for host "%s"', host)
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=info["title"],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ):
        """Handle reconfiguration of an existing entry.

        Lets the user update host/password (e.g. after a DHCP IP change,
        or a rotated MQTT password) from Settings > Devices & Services >
        Reconfigure, instead of having to delete and re-add the
        integration from scratch.
        """
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # unique_id 与 host 绑定；这里允许 host 真的发生变化（例如
                # 割草机换了 IP），只需确保没有和另一个已存在的条目冲突。
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    title=info["title"],
                    data=user_input,
                )

        current_data = reconfigure_entry.data
        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_data.get(CONF_HOST, "")): str,
                vol.Required(CONF_PASSWORD, default=current_data.get(CONF_PASSWORD, "")): str,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry) -> "TerraMowOptionsFlowHandler":
        """入口：Settings > Devices & Services > TerraMow > Configure。"""
        return TerraMowOptionsFlowHandler()


class TerraMowOptionsFlowHandler(OptionsFlow):
    """让用户为分区（sub_region）自定义显示名称。

    设备/App 里的分区经常没有为 sub_region 单独起名（只有父 region 才有自定义名），
    这会导致 select.terramow_..._region_select 的选项只能显示类似
    "Sub-zone 3 (ID: 3)" 这种没有实际信息量的标签。这里允许用户直接在 HA 里
    为每个已知的 zone id 指定一个名称，存进 entry.options[CONF_ZONE_NAMES]，
    select.py 读取时优先使用这个覆盖值。
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ):
        errors: dict[str, str] = {}
        zones = self._get_known_zones()
        existing_overrides: dict[str, str] = dict(
            self.config_entry.options.get(CONF_ZONE_NAMES, {})
        )

        if user_input is not None:
            if zones:
                zone_names: dict[str, str] = {}
                for zone_id, _current_name in zones:
                    value = user_input.get(f"zone_name_{zone_id}", "")
                    if value and value.strip():
                        zone_names[str(zone_id)] = value.strip()
                return self.async_create_entry(title="", data={CONF_ZONE_NAMES: zone_names})

            # 地图/分区信息还不可用时的兜底方案：直接输入 JSON 映射。
            raw = user_input.get("zone_names_json", "").strip()
            zone_names = existing_overrides
            if raw:
                try:
                    parsed = json.loads(raw)
                    if not isinstance(parsed, dict):
                        raise ValueError("zone_names_json must be a JSON object")
                    zone_names = {
                        str(zone_id): str(name).strip()
                        for zone_id, name in parsed.items()
                        if str(name).strip()
                    }
                except (ValueError, TypeError):
                    errors["base"] = "invalid_zone_names_json"

            if not errors:
                return self.async_create_entry(title="", data={CONF_ZONE_NAMES: zone_names})

        if zones:
            schema_dict: dict[Any, Any] = {}
            zone_list_lines = [
                f"#{zone_id}: {current_name}" for zone_id, current_name in zones
            ]
            for zone_id, _current_name in zones:
                default = existing_overrides.get(str(zone_id), "")
                schema_dict[vol.Optional(f"zone_name_{zone_id}", default=default)] = str

            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema(schema_dict),
                description_placeholders={"zone_list": "\n".join(zone_list_lines)},
                errors=errors,
            )

        # 还没有可用的分区列表（地图尚未加载/设备没有分区）：退回到 JSON 输入兜底方案。
        default_json = json.dumps(existing_overrides, ensure_ascii=False) if existing_overrides else ""
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional("zone_names_json", default=default_json): str,
                }
            ),
            description_placeholders={
                "zone_list": "(no zones detected yet — wait for the map to load, or enter a JSON mapping below)"
            },
            errors=errors,
        )

    def _get_known_zones(self) -> list[tuple[int, str]]:
        """从已缓存的地图信息中枚举当前已知的 sub_region，返回 [(id, 当前展示名), ...]。"""
        hass = self.hass
        basic_data = hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        lawn_mower = getattr(basic_data, "lawn_mower", None) if basic_data else None
        map_info = getattr(lawn_mower, "map_info", None) if lawn_mower else None
        if not isinstance(map_info, dict) or not map_info:
            return []

        zones: list[tuple[int, str]] = []
        for region in map_info.get("regions", []) or []:
            region_name = (region.get("name") or "").strip()
            for sub_zone in region.get("sub_regions", []) or []:
                zone_id = sub_zone.get("id")
                if zone_id is None:
                    continue
                sub_name = (sub_zone.get("name") or "").strip()
                display = sub_name or region_name or f"Sub-zone {zone_id}"
                zones.append((zone_id, display))
        return zones


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""