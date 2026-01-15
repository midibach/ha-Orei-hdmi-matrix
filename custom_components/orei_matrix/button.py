"""Button platform for Orei HDMI Matrix."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CEC_INPUT_COMMANDS,
    CEC_OUTPUT_COMMANDS,
    DOMAIN,
    NUM_INPUTS,
    NUM_OUTPUTS,
    NUM_PRESETS,
)
from .coordinator import OreiMatrixCoordinator
from .entity import OreiMatrixEntity, OreiMatrixInputEntity, OreiMatrixOutputEntity


@dataclass(frozen=True)
class OreiMatrixButtonDescription(ButtonEntityDescription):
    """Describe an Orei Matrix button entity."""

    action: str = ""


SYSTEM_BUTTONS: tuple[OreiMatrixButtonDescription, ...] = (
    OreiMatrixButtonDescription(
        key="reboot",
        translation_key="reboot",
        action="reboot",
        icon="mdi:restart",
    ),
    OreiMatrixButtonDescription(
        key="reset",
        translation_key="factory_reset",
        action="reset",
        icon="mdi:factory",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Orei Matrix button entities."""
    coordinator: OreiMatrixCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[ButtonEntity] = []

    # System buttons
    for description in SYSTEM_BUTTONS:
        entities.append(OreiMatrixSystemButton(coordinator, description))

    # Preset buttons
    for preset_num in range(1, NUM_PRESETS + 1):
        entities.append(OreiMatrixSavePresetButton(coordinator, preset_num))
        entities.append(OreiMatrixRecallPresetButton(coordinator, preset_num))
        entities.append(OreiMatrixClearPresetButton(coordinator, preset_num))

    # CEC input buttons
    for input_num in range(1, NUM_INPUTS + 1):
        for command in CEC_INPUT_COMMANDS:
            entities.append(OreiMatrixCecInputButton(coordinator, input_num, command))

    # CEC output buttons
    for output_num in range(1, NUM_OUTPUTS + 1):
        for command in CEC_OUTPUT_COMMANDS:
            entities.append(OreiMatrixCecOutputButton(coordinator, output_num, command))

    # Route all buttons
    for input_num in range(1, NUM_INPUTS + 1):
        entities.append(OreiMatrixRouteAllButton(coordinator, input_num))

    async_add_entities(entities)


class OreiMatrixSystemButton(OreiMatrixEntity, ButtonEntity):
    """System button for Orei HDMI Matrix."""

    entity_description: OreiMatrixButtonDescription

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        description: OreiMatrixButtonDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, description.key, description.key.replace("_", " ").title())
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle the button press."""
        action = self.entity_description.action
        if action == "reboot":
            await self.coordinator.async_reboot()
        elif action == "reset":
            await self.coordinator.async_reset()


class OreiMatrixSavePresetButton(OreiMatrixEntity, ButtonEntity):
    """Save preset button for Orei HDMI Matrix."""

    _attr_icon = "mdi:content-save"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        preset_num: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            coordinator,
            f"save_preset_{preset_num}",
            f"Save Preset {preset_num}",
        )
        self._preset_num = preset_num

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_save_preset(self._preset_num)


class OreiMatrixRecallPresetButton(OreiMatrixEntity, ButtonEntity):
    """Recall preset button for Orei HDMI Matrix."""

    _attr_icon = "mdi:playlist-play"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        preset_num: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            coordinator,
            f"recall_preset_{preset_num}",
            f"Recall Preset {preset_num}",
        )
        self._preset_num = preset_num

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_recall_preset(self._preset_num)


class OreiMatrixClearPresetButton(OreiMatrixEntity, ButtonEntity):
    """Clear preset button for Orei HDMI Matrix."""

    _attr_icon = "mdi:playlist-remove"
    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        preset_num: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            coordinator,
            f"clear_preset_{preset_num}",
            f"Clear Preset {preset_num}",
        )
        self._preset_num = preset_num

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_clear_preset(self._preset_num)


class OreiMatrixCecInputButton(OreiMatrixInputEntity, ButtonEntity):
    """CEC input command button for Orei HDMI Matrix."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        input_num: int,
        command: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            coordinator,
            input_num,
            f"cec_{command}",
            f"CEC {command.replace('-', ' ').title()}",
        )
        self._command = command
        self._attr_icon = self._get_icon(command)

    def _get_icon(self, command: str) -> str:
        """Get icon for CEC command."""
        icons = {
            "on": "mdi:power",
            "off": "mdi:power-off",
            "menu": "mdi:menu",
            "back": "mdi:arrow-left",
            "up": "mdi:arrow-up",
            "down": "mdi:arrow-down",
            "left": "mdi:arrow-left",
            "right": "mdi:arrow-right",
            "enter": "mdi:keyboard-return",
            "play": "mdi:play",
            "pause": "mdi:pause",
            "stop": "mdi:stop",
            "rew": "mdi:rewind",
            "ff": "mdi:fast-forward",
            "mute": "mdi:volume-mute",
            "vol-": "mdi:volume-minus",
            "vol+": "mdi:volume-plus",
            "previous": "mdi:skip-previous",
            "next": "mdi:skip-next",
        }
        return icons.get(command, "mdi:remote")

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_send_cec_input(self._input_num, self._command)


class OreiMatrixCecOutputButton(OreiMatrixOutputEntity, ButtonEntity):
    """CEC output command button for Orei HDMI Matrix."""

    _attr_entity_registry_enabled_default = False

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
        command: str,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            coordinator,
            output_num,
            f"cec_{command}",
            f"CEC {command.replace('-', ' ').title()}",
        )
        self._command = command
        self._attr_icon = self._get_icon(command)

    def _get_icon(self, command: str) -> str:
        """Get icon for CEC command."""
        icons = {
            "on": "mdi:power",
            "off": "mdi:power-off",
            "mute": "mdi:volume-mute",
            "vol-": "mdi:volume-minus",
            "vol+": "mdi:volume-plus",
            "active": "mdi:television",
        }
        return icons.get(command, "mdi:remote")

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_send_cec_output(self._output_num, self._command)


class OreiMatrixRouteAllButton(OreiMatrixEntity, ButtonEntity):
    """Route all outputs to input button for Orei HDMI Matrix."""

    _attr_icon = "mdi:video-input-hdmi"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        input_num: int,
    ) -> None:
        """Initialize the button."""
        super().__init__(
            coordinator,
            f"route_all_to_input_{input_num}",
            f"Route All to Input {input_num}",
        )
        self._input_num = input_num

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_set_output_source(0, self._input_num)
