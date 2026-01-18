"""Select platform for Orei HDMI Matrix."""
from __future__ import annotations

import re
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    EDID_ALL_OPTIONS,
    EDID_ALL_OPTIONS_REVERSE,
    EDID_COPY_OPTIONS,
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
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
            
        if self.coordinator.data is None:
            return f"Input {self._output_num}"  # Default 1:1 mapping
        routing = self.coordinator.data.get("routing", {})
        input_num = routing.get(self._output_num, self._output_num)
        return f"Input {input_num}"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._optimistic_option = option
        self.async_write_ha_state()
        
        input_num = int(option.replace("Input ", ""))
        try:
            await self.coordinator.async_set_output_source(self._output_num, input_num)
        except Exception:
            self._optimistic_option = None
            self.async_write_ha_state()
            raise

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_option = None
        super()._handle_coordinator_update()


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
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
            
        if self.coordinator.data is None:
            return "Follow Sink"
        hdcp_settings = self.coordinator.data.get("output_hdcp", {})
        hdcp_value = hdcp_settings.get(self._output_num, "Follow Sink")
        
        # Try to match the response to our options
        if isinstance(hdcp_value, str):
            hdcp_lower = hdcp_value.lower()
            for option in self._attr_options:
                if option.lower() in hdcp_lower or hdcp_lower in option.lower():
                    return option
        return "Follow Sink"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._optimistic_option = option
        self.async_write_ha_state()
        
        mode = HDCP_OPTIONS_REVERSE.get(option, 3)
        try:
            await self.coordinator.async_set_output_hdcp(self._output_num, mode)
        except Exception:
            self._optimistic_option = None
            self.async_write_ha_state()
            raise

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_option = None
        super()._handle_coordinator_update()


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
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
            
        if self.coordinator.data is None:
            return "Pass-through"
        scaler_settings = self.coordinator.data.get("output_scaler", {})
        scaler_value = scaler_settings.get(self._output_num, "Pass-through")
        
        if isinstance(scaler_value, str):
            scaler_lower = scaler_value.lower()
            for option in self._attr_options:
                if option.lower() in scaler_lower or scaler_lower in option.lower():
                    return option
        return "Pass-through"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._optimistic_option = option
        self.async_write_ha_state()
        
        mode = SCALER_OPTIONS_REVERSE.get(option, 1)
        try:
            await self.coordinator.async_set_output_scaler(self._output_num, mode)
        except Exception:
            self._optimistic_option = None
            self.async_write_ha_state()
            raise

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_option = None
        super()._handle_coordinator_update()


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
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
            
        if self.coordinator.data is None:
            return "Pass-through"
        hdr_settings = self.coordinator.data.get("output_hdr", {})
        hdr_value = hdr_settings.get(self._output_num, "Pass-through")
        
        if isinstance(hdr_value, str):
            hdr_norm = self._normalize(hdr_value)
            # Check specific patterns
            if "passthrough" in hdr_norm or "pass-through" in hdr_norm:
                return "Pass-through"
            if "hdrtosdr" in hdr_norm or "hdr-sdr" in hdr_norm or "hdr to sdr" in hdr_norm:
                return "HDR to SDR"
            if "auto" in hdr_norm or "followsink" in hdr_norm:
                return "Auto (Follow Sink)"
        return "Pass-through"

    def _normalize(self, value: str) -> str:
        """Normalize string for comparison."""
        return value.lower().replace(" ", "").replace("(", "").replace(")", "").replace("-", "")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._optimistic_option = option
        self.async_write_ha_state()
        
        mode = HDR_OPTIONS_REVERSE.get(option, 1)
        try:
            await self.coordinator.async_set_output_hdr(self._output_num, mode)
        except Exception:
            self._optimistic_option = None
            self.async_write_ha_state()
            raise

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_option = None
        super()._handle_coordinator_update()


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
        # Include both preset options and copy from output options
        self._attr_options = list(EDID_OPTIONS.values()) + list(EDID_COPY_OPTIONS.values())
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
            
        if self.coordinator.data is None:
            return "8K FRL12G HDR, 7.1CH"
        edid_settings = self.coordinator.data.get("input_edid", {})
        edid_value = edid_settings.get(self._input_num, "8K FRL12G HDR, 7.1CH")
        
        if isinstance(edid_value, str):
            # Check for "copy from output X" pattern first
            copy_match = re.search(r"copy\s*from\s*output\s*(\d+)", edid_value, re.IGNORECASE)
            if copy_match:
                output_num = int(copy_match.group(1))
                return f"Copy from Output {output_num}"
            
            # Try to find matching preset option
            for option in EDID_OPTIONS.values():
                if self._edid_match(option, edid_value):
                    return option
                    
        return "8K FRL12G HDR, 7.1CH"

    def _edid_match(self, option: str, value: str) -> bool:
        """Check if EDID values match."""
        option_norm = self._normalize_edid(option)
        value_norm = self._normalize_edid(value)
        return option_norm in value_norm or value_norm in option_norm

    def _normalize_edid(self, value: str) -> str:
        """Normalize EDID string for comparison."""
        return value.lower().replace(" ", "").replace("_", "").replace(",", "").replace(":", "")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._optimistic_option = option
        self.async_write_ha_state()
        
        # Check if it's a "Copy from Output X" option
        copy_match = re.search(r"Copy from Output (\d+)", option)
        if copy_match:
            output_num = int(copy_match.group(1))
            try:
                await self.coordinator.async_copy_edid(self._input_num, output_num)
            except Exception:
                self._optimistic_option = None
                self.async_write_ha_state()
                raise
        else:
            # Use preset mode
            mode = EDID_OPTIONS_REVERSE.get(option, 36)
            try:
                await self.coordinator.async_set_input_edid(self._input_num, mode)
            except Exception:
                self._optimistic_option = None
                self.async_write_ha_state()
                raise

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_option = None
        super()._handle_coordinator_update()


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
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
            
        if self.coordinator.data is None:
            return f"Input {self._output_num}"
        source_settings = self.coordinator.data.get("output_ext_audio_source", {})
        source = source_settings.get(self._output_num, self._output_num)
        if source in EXT_AUDIO_SOURCE_OPTIONS:
            return EXT_AUDIO_SOURCE_OPTIONS[source]
        return f"Input {self._output_num}"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._optimistic_option = option
        self.async_write_ha_state()
        
        source = EXT_AUDIO_SOURCE_OPTIONS_REVERSE.get(option, self._output_num)
        try:
            await self.coordinator.async_set_output_ext_audio_source(self._output_num, source)
        except Exception:
            self._optimistic_option = None
            self.async_write_ha_state()
            raise

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_option = None
        super()._handle_coordinator_update()


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
        self._optimistic_option: str | None = None

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        if self._optimistic_option is not None:
            return self._optimistic_option
            
        if self.coordinator.data is None:
            return "Bind to Input"
        mode = self.coordinator.data.get("ext_audio_mode", "Bind to Input")
        
        # Normalize and match
        if isinstance(mode, str):
            mode_lower = mode.lower()
            for option in self._attr_options:
                if option.lower() in mode_lower or mode_lower in option.lower():
                    return option
        return "Bind to Input"

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        self._optimistic_option = option
        self.async_write_ha_state()
        
        mode = EXT_AUDIO_MODE_OPTIONS_REVERSE.get(option, 0)
        try:
            await self.coordinator.async_set_ext_audio_mode(mode)
        except Exception:
            self._optimistic_option = None
            self.async_write_ha_state()
            raise

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._optimistic_option = None
        super()._handle_coordinator_update()


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
