"""Text platform for Orei HDMI Matrix."""
from __future__ import annotations

from homeassistant.components.text import TextEntity, TextMode
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
    """Set up the Orei Matrix text entities."""
    coordinator: OreiMatrixCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[TextEntity] = [
        OreiMatrixLogoText(coordinator),
    ]

    async_add_entities(entities)


class OreiMatrixLogoText(OreiMatrixEntity, TextEntity):
    """Logo text entity for Orei HDMI Matrix."""

    _attr_icon = "mdi:format-text"
    _attr_native_max = 16
    _attr_mode = TextMode.TEXT
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: OreiMatrixCoordinator) -> None:
        """Initialize the text entity."""
        super().__init__(coordinator, "logo", "LCD Logo")
        self._value = "Matrix Switch"

    @property
    def native_value(self) -> str:
        """Return the current logo text."""
        return self._value

    async def async_set_value(self, value: str) -> None:
        """Set the logo text."""
        # Truncate to 16 characters
        value = value[:16]
        await self.coordinator.async_set_logo(value)
        self._value = value
        self.async_write_ha_state()
