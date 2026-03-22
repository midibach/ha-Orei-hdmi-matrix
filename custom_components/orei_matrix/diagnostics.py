"""Diagnostics support for Orei HDMI Matrix."""
from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import OreiMatrixCoordinator

TO_REDACT = {
    CONF_HOST,
    "ip_address",
    "mac_address",
    "gateway",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    coordinator: OreiMatrixCoordinator = hass.data[DOMAIN][entry.entry_id]

    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": dict(entry.options),
        },
        "device_info": async_redact_data(coordinator.device_info, TO_REDACT),
        "data": async_redact_data(coordinator.data or {}, TO_REDACT),
        "available": coordinator.available,
    }
