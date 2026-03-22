"""Number platform for Orei HDMI Matrix."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import OreiMatrixCoordinator
from .entity import OreiMatrixEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Orei Matrix number entities."""
    coordinator: OreiMatrixCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Currently no number entities needed since LCD time is better as a select
    # This platform is included for future expansion
    entities: list[NumberEntity] = []

    async_add_entities(entities)
