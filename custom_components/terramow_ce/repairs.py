"""Repairs support for the TerraMow CE integration.

Firmware/plugin version compatibility (dp_112) can only be resolved by the
user updating firmware through the TerraMow app, or updating this
integration -- Home Assistant can't do either automatically. So these are
informational issues (is_fixable=False): they make the existing
compatibility check visible in Settings > Repairs instead of only as
sensor.version_compatibility's state text, which is easy to miss.
"""
from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN, CompatibilityStatus

_SEVERITY_BY_STATUS = {
    CompatibilityStatus.UPGRADE_REQUIRED: ir.IssueSeverity.WARNING,
    CompatibilityStatus.DOWNGRADE_RECOMMENDED: ir.IssueSeverity.WARNING,
    CompatibilityStatus.INCOMPATIBLE: ir.IssueSeverity.ERROR,
}

_TRANSLATION_KEY_BY_STATUS = {
    CompatibilityStatus.UPGRADE_REQUIRED: "firmware_upgrade_required",
    CompatibilityStatus.DOWNGRADE_RECOMMENDED: "plugin_downgrade_recommended",
    CompatibilityStatus.INCOMPATIBLE: "firmware_incompatible",
}


def _issue_id(host: str) -> str:
    """Return a stable, per-device issue id."""
    return f"firmware_compatibility_{host}"


def async_update_compatibility_issue(
    hass: HomeAssistant,
    host: str,
    status: str,
    message: str,
) -> None:
    """Create, update, or clear the compatibility Repairs issue for a mower."""
    issue_id = _issue_id(host)

    if status == CompatibilityStatus.COMPATIBLE:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return

    translation_key = _TRANSLATION_KEY_BY_STATUS.get(status, "firmware_incompatible")
    severity = _SEVERITY_BY_STATUS.get(status, ir.IssueSeverity.WARNING)

    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=severity,
        translation_key=translation_key,
        translation_placeholders={"host": host, "message": message},
        learn_more_url="https://github.com/TerraMow/TerraMowHA/issues",
    )


def async_clear_compatibility_issue(hass: HomeAssistant, host: str) -> None:
    """Remove the compatibility issue, e.g. when the entity is unloaded."""
    ir.async_delete_issue(hass, DOMAIN, _issue_id(host))
