"""Select platform for Orei HDMI Matrix."""
from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    EDID_OPTIONS,
    EDID_OPTIONS_REVERSE,
    EXT_AUDIO_MODE_OPTIONS,
    EXT_AUDIO_MODE_OPTIONS_REVERSE,
    EXT_AUDIO_SOURCE_OPTIONS,
    EXT_AUDIO_SOURCE_OPTIONS_REVERSE,
    HDCP_OPTIONS,
    HDCP_OPTIONS_REVERSE,
    HDR_OPTIONS,
    HDR_OPTIONS_REVERSE,
    LCD_TIME_OPTIONS,
    LCD_TIME_OPTIONS_REVERSE,
    NUM_INPUTS,
    NUM_OUTPUTS,
    SCALER_OPTIONS,
    SCALER_OPTIONS_REVERSE,
)
from .coordinator import OreiMatrixCoordinator
from .entity import OreiMatrixEntity, OreiMatrixInputEntity, OreiMatrixOutputEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Orei Matrix select entities."""
    coordinator: OreiMatrixCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SelectEntity] = []

    # Output routing selects
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputRoutingSelect(coordinator, output_num))

    # Output HDCP selects
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputHdcpSelect(coordinator, output_num))

    # Output scaler selects
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputScalerSelect(coordinator, output_num))

    # Output HDR selects
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputHdrSelect(coordinator, output_num))

    # Input EDID selects
    for input_num in range(1, NUM_INPUTS + 1):
        entities.append(OreiMatrixInputEdidSelect(coordinator, input_num))

    # Output external audio source selects
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputExtAudioSourceSelect(coordinator, output_num))

    # System selects
    entities.append(OreiMatrixExtAudioModeSelect(coordinator))
    entities.append(OreiMatrixLcdTimeSelect(coordinator))

    async_add_entities(entities)


class OreiMatrixOutputRoutingSelect(OreiMatrixOutputEntity, SelectEntity):
    """Output routing select for Orei HDMI Matrix."""

    _attr_icon = "mdi:video-input-hdmi"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, output_num, "routing", "Source")
        self._attr_options = [f"Input {i}" for i in range(1, NUM_INPUTS + 1)]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None
        routing = self.coordinator.data.get("routing", {})
        input_num = routing.get(self._output_num)
        if input_num:
            return f"Input {input_num}"
        return None

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        input_num = int(option.replace("Input ", ""))
        await self.coordinator.async_set_output_source(self._output_num, input_num)


class OreiMatrixOutputHdcpSelect(OreiMatrixOutputEntity, SelectEntity):
    """Output HDCP select for Orei HDMI Matrix."""

    _attr_icon = "mdi:shield-lock"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, output_num, "hdcp", "HDCP")
        self._attr_options = list(HDCP_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None
        hdcp_settings = self.coordinator.data.get("output_hdcp", {})
        hdcp_value = hdcp_settings.get(self._output_num)
        if hdcp_value:
            # Try to match the response to our options
            hdcp_lower = hdcp_value.lower()
            for option in self._attr_options:
                if option.lower() in hdcp_lower or hdcp_lower in option.lower():
                    return option
        return "Follow Sink"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = HDCP_OPTIONS_REVERSE.get(option, 3)
        await self.coordinator.async_set_output_hdcp(self._output_num, mode)


class OreiMatrixOutputScalerSelect(OreiMatrixOutputEntity, SelectEntity):
    """Output scaler select for Orei HDMI Matrix."""

    _attr_icon = "mdi:resize"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, output_num, "scaler", "Scaler")
        self._attr_options = list(SCALER_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None
        scaler_settings = self.coordinator.data.get("output_scaler", {})
        scaler_value = scaler_settings.get(self._output_num)
        if scaler_value:
            scaler_lower = scaler_value.lower()
            for option in self._attr_options:
                if option.lower() in scaler_lower or scaler_lower in option.lower():
                    return option
        return "Pass-through"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = SCALER_OPTIONS_REVERSE.get(option, 1)
        await self.coordinator.async_set_output_scaler(self._output_num, mode)


class OreiMatrixOutputHdrSelect(OreiMatrixOutputEntity, SelectEntity):
    """Output HDR select for Orei HDMI Matrix."""

    _attr_icon = "mdi:hdr"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, output_num, "hdr", "HDR Mode")
        self._attr_options = list(HDR_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None
        hdr_settings = self.coordinator.data.get("output_hdr", {})
        hdr_value = hdr_settings.get(self._output_num)
        if hdr_value:
            hdr_lower = hdr_value.lower()
            for option in self._attr_options:
                if option.lower() in hdr_lower or hdr_lower in option.lower():
                    return option
        return "Pass-through"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = HDR_OPTIONS_REVERSE.get(option, 1)
        await self.coordinator.async_set_output_hdr(self._output_num, mode)


class OreiMatrixInputEdidSelect(OreiMatrixInputEntity, SelectEntity):
    """Input EDID select for Orei HDMI Matrix."""

    _attr_icon = "mdi:card-bulleted"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        input_num: int,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, input_num, "edid", "EDID")
        self._attr_options = list(EDID_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None
        edid_settings = self.coordinator.data.get("input_edid", {})
        edid_value = edid_settings.get(self._input_num)
        if edid_value:
            # Try to find matching option
            edid_normalized = edid_value.replace("_", " ").replace(",", ", ")
            for option in self._attr_options:
                if self._normalize_edid(option) == self._normalize_edid(edid_normalized):
                    return option
            # Fallback - try partial match
            for option in self._attr_options:
                if self._edid_match(option, edid_value):
                    return option
        return "8K FRL12G HDR, 7.1CH"

    def _normalize_edid(self, value: str) -> str:
        """Normalize EDID string for comparison."""
        return value.lower().replace(" ", "").replace("_", "").replace(",", "").replace(":", "")

    def _edid_match(self, option: str, value: str) -> bool:
        """Check if EDID values match."""
        option_norm = self._normalize_edid(option)
        value_norm = self._normalize_edid(value)
        return option_norm in value_norm or value_norm in option_norm

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = EDID_OPTIONS_REVERSE.get(option, 36)
        await self.coordinator.async_set_input_edid(self._input_num, mode)


class OreiMatrixOutputExtAudioSourceSelect(OreiMatrixOutputEntity, SelectEntity):
    """Output external audio source select for Orei HDMI Matrix."""

    _attr_icon = "mdi:speaker"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, output_num, "ext_audio_source", "Ext Audio Source")
        self._attr_options = list(EXT_AUDIO_SOURCE_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None
        source_settings = self.coordinator.data.get("output_ext_audio_source", {})
        source = source_settings.get(self._output_num)
        if source and source in EXT_AUDIO_SOURCE_OPTIONS:
            return EXT_AUDIO_SOURCE_OPTIONS[source]
        return f"Input {self._output_num}"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        source = EXT_AUDIO_SOURCE_OPTIONS_REVERSE.get(option, self._output_num)
        await self.coordinator.async_set_output_ext_audio_source(self._output_num, source)


class OreiMatrixExtAudioModeSelect(OreiMatrixEntity, SelectEntity):
    """External audio mode select for Orei HDMI Matrix."""

    _attr_icon = "mdi:audio-video"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, "ext_audio_mode", "External Audio Mode")
        self._attr_options = list(EXT_AUDIO_MODE_OPTIONS.values())

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self.coordinator.data is None:
            return None
        mode = self.coordinator.data.get("ext_audio_mode", "Bind to Input")
        # Normalize and match
        mode_lower = mode.lower()
        for option in self._attr_options:
            if option.lower() in mode_lower or mode_lower in option.lower():
                return option
        return "Bind to Input"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = EXT_AUDIO_MODE_OPTIONS_REVERSE.get(option, 0)
        await self.coordinator.async_set_ext_audio_mode(mode)


class OreiMatrixLcdTimeSelect(OreiMatrixEntity, SelectEntity):
    """LCD on time select for Orei HDMI Matrix."""

    _attr_icon = "mdi:monitor"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
    ) -> None:
        """Initialize the select."""
        super().__init__(coordinator, "lcd_time", "LCD On Time")
        self._attr_options = list(LCD_TIME_OPTIONS.values())
        self._current = "Always On"

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return self._current

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        mode = LCD_TIME_OPTIONS_REVERSE.get(option, 1)
        await self.coordinator.async_set_lcd_time(mode)
        self._current = option
        self.async_write_ha_state()
