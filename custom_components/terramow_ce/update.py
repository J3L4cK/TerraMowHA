"""Firmware compatibility update entity for the TerraMow CE integration."""
from __future__ import annotations

import logging

from homeassistant.components.update import UpdateDeviceClass, UpdateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN, TerraMowBasicData
from .const import MIN_REQUIRED_OVERALL_VERSION, CompatibilityStatus

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the TerraMow update entity."""
    basic_data = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([TerraMowFirmwareCompatibilityUpdate(basic_data, hass)])


class TerraMowFirmwareCompatibilityUpdate(UpdateEntity):
    """Surfaces the firmware/plugin compatibility check in HA's Updates UI.

    This integration has no way to check for or install the mower's
    latest firmware over MQTT -- that's only available through the
    TerraMow app/cloud, which this local-push integration does not talk
    to. What it does know reliably is the minimum firmware "overall"
    version this plugin release requires (MIN_REQUIRED_OVERALL_VERSION)
    and the firmware's actual reported "overall" version (dp_112).

    So this entity is intentionally read-only (no install support): it
    reports "update available" exactly when the existing compatibility
    check would say upgrade_required, using the minimum required version
    as the target. It does not claim to know the true latest firmware
    version, and never will unless a real version feed is added.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "firmware_compatibility"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = UpdateDeviceClass.FIRMWARE

    def __init__(
        self,
        basic_data: TerraMowBasicData,
        hass: HomeAssistant,
    ) -> None:
        """Initialize the update entity."""
        super().__init__()
        self.basic_data = basic_data
        self.host = basic_data.host
        self.hass = hass

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        model = None
        if self.basic_data.lawn_mower:
            model = self.basic_data.lawn_mower.device_model
        return DeviceInfo(
            identifiers={('TerraMowLawnMower', self.basic_data.host)},
            name='TerraMow',
            manufacturer='TerraMow',
            model=model,
        )

    @property
    def unique_id(self):
        """Return a unique ID for this entity."""
        return f"lawn_mower.terramow@{self.host}.firmware_compatibility"

    @property
    def available(self) -> bool:
        """Return True once we've received a compatibility payload."""
        return self.basic_data.firmware_version is not None

    @property
    def installed_version(self) -> str | None:
        """Return the firmware's reported overall version."""
        firmware = self.basic_data.firmware_version
        if not firmware:
            return None
        overall = firmware.get("overall")
        return str(overall) if overall is not None else None

    @property
    def latest_version(self) -> str | None:
        """Return the minimum required version if below it, else 'up to date'."""
        firmware = self.basic_data.firmware_version
        if not firmware:
            return None
        overall = firmware.get("overall")
        if overall is None:
            return None
        if (
            self.basic_data.compatibility_status == CompatibilityStatus.UPGRADE_REQUIRED
            and overall < MIN_REQUIRED_OVERALL_VERSION
        ):
            return str(MIN_REQUIRED_OVERALL_VERSION)
        # We only know a required minimum, not the true latest release,
        # so once that minimum is met we report "up to date" rather than
        # inventing a newer version number.
        return str(overall)

    @property
    def release_summary(self) -> str | None:
        """Return the existing human-readable compatibility message."""
        return self.basic_data.get_compatibility_message()
