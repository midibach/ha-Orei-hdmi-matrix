"""Switch platform for Orei HDMI Matrix."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NUM_OUTPUTS
from .coordinator import OreiMatrixCoordinator
from .entity import OreiMatrixEntity, OreiMatrixOutputEntity


@dataclass(frozen=True)
class OreiMatrixSwitchDescription(SwitchEntityDescription):
    """Describe an Orei Matrix switch entity."""

    data_key: str = ""


SYSTEM_SWITCHES: tuple[OreiMatrixSwitchDescription, ...] = (
    OreiMatrixSwitchDescription(
        key="power",
        translation_key="power",
        data_key="power",
        icon="mdi:power",
    ),
    OreiMatrixSwitchDescription(
        key="beep",
        translation_key="beep",
        data_key="beep",
        icon="mdi:volume-high",
    ),
    OreiMatrixSwitchDescription(
        key="lock",
        translation_key="panel_lock",
        data_key="lock",
        icon="mdi:lock",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Orei Matrix switch entities."""
    coordinator: OreiMatrixCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SwitchEntity] = []

    # System switches
    for description in SYSTEM_SWITCHES:
        entities.append(OreiMatrixSystemSwitch(coordinator, description))

    # Output stream switches
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputStreamSwitch(coordinator, output_num))

    # Output ARC switches
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputArcSwitch(coordinator, output_num))

    # Output external audio switches
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputExtAudioSwitch(coordinator, output_num))

    async_add_entities(entities)


class OreiMatrixSystemSwitch(OreiMatrixEntity, SwitchEntity):
    """System switch for Orei HDMI Matrix."""

    entity_description: OreiMatrixSwitchDescription

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        description: OreiMatrixSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, description.key, description.key.replace("_", " ").title())
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.data_key, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        key = self.entity_description.key
        if key == "power":
            await self.coordinator.async_set_power(True)
        elif key == "beep":
            await self.coordinator.async_set_beep(True)
        elif key == "lock":
            await self.coordinator.async_set_lock(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        key = self.entity_description.key
        if key == "power":
            await self.coordinator.async_set_power(False)
        elif key == "beep":
            await self.coordinator.async_set_beep(False)
        elif key == "lock":
            await self.coordinator.async_set_lock(False)


class OreiMatrixOutputStreamSwitch(OreiMatrixOutputEntity, SwitchEntity):
    """Output stream switch for Orei HDMI Matrix."""

    _attr_icon = "mdi:video"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, output_num, "stream", "Stream")

    @property
    def is_on(self) -> bool | None:
        """Return true if the stream is enabled."""
        if self.coordinator.data is None:
            return None
        output_stream = self.coordinator.data.get("output_stream", {})
        return output_stream.get(self._output_num, True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the stream."""
        await self.coordinator.async_set_output_stream(self._output_num, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the stream."""
        await self.coordinator.async_set_output_stream(self._output_num, False)


class OreiMatrixOutputArcSwitch(OreiMatrixOutputEntity, SwitchEntity):
    """Output ARC switch for Orei HDMI Matrix."""

    _attr_icon = "mdi:audio-video"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, output_num, "arc", "ARC")

    @property
    def is_on(self) -> bool | None:
        """Return true if ARC is enabled."""
        if self.coordinator.data is None:
            return None
        output_arc = self.coordinator.data.get("output_arc", {})
        return output_arc.get(self._output_num, False)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable ARC."""
        await self.coordinator.async_set_output_arc(self._output_num, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable ARC."""
        await self.coordinator.async_set_output_arc(self._output_num, False)


class OreiMatrixOutputExtAudioSwitch(OreiMatrixOutputEntity, SwitchEntity):
    """Output external audio switch for Orei HDMI Matrix."""

    _attr_icon = "mdi:speaker"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, output_num, "ext_audio", "External Audio")

    @property
    def is_on(self) -> bool | None:
        """Return true if external audio is enabled."""
        if self.coordinator.data is None:
            return None
        output_ext_audio = self.coordinator.data.get("output_ext_audio", {})
        return output_ext_audio.get(self._output_num, True)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable external audio."""
        await self.coordinator.async_set_output_ext_audio(self._output_num, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable external audio."""
        await self.coordinator.async_set_output_ext_audio(self._output_num, False)
