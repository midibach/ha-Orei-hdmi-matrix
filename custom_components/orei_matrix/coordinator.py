"""Data update coordinator for Orei HDMI Matrix."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OreiMatrixAPI, OreiMatrixConnectionError, OreiMatrixError
from .const import (
    CONF_SYNC_NAMES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NAME_SYNC_INTERVAL,
    NUM_INPUTS,
    NUM_OUTPUTS,
)

_LOGGER = logging.getLogger(__name__)


class OreiMatrixCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching data from the Orei Matrix."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        api: OreiMatrixAPI,
        entry: ConfigEntry,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=entry.title,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self.config_entry = entry
        self._device_info: dict[str, Any] = {}
        self._available = True
        self._last_known_data: dict[str, Any] = self._get_default_data()
        self._optimistic_state: dict[str, Any] = {}
        self._init_complete = False
        self._name_sync_unsub: callable | None = None
        
        # Port names - stored separately for stability
        self._input_names: list[str] = [f"Input {i}" for i in range(1, NUM_INPUTS + 1)]
        self._output_names: list[str] = [f"Output {i}" for i in range(1, NUM_OUTPUTS + 1)]
        self._names_loaded = False

    def _get_default_data(self) -> dict[str, Any]:
        """Return default data structure."""
        return {
            "power": True,
            "beep": False,
            "lock": False,
            "routing": {i: i for i in range(1, NUM_OUTPUTS + 1)},  # Default 1:1 routing
            "input_status": {i: "Unknown" for i in range(1, NUM_INPUTS + 1)},
            "output_status": {i: "Unknown" for i in range(1, NUM_OUTPUTS + 1)},
            "output_hdcp": {i: "Follow Sink" for i in range(1, NUM_OUTPUTS + 1)},
            "output_stream": {i: True for i in range(1, NUM_OUTPUTS + 1)},
            "output_scaler": {i: "Pass-through" for i in range(1, NUM_OUTPUTS + 1)},
            "output_hdr": {i: "Pass-through" for i in range(1, NUM_OUTPUTS + 1)},
            "output_arc": {i: False for i in range(1, NUM_OUTPUTS + 1)},
            "output_audio_mute": {i: False for i in range(1, NUM_OUTPUTS + 1)},
            "input_edid": {i: "8K FRL12G HDR, 7.1CH" for i in range(1, NUM_INPUTS + 1)},
            "output_ext_audio": {i: True for i in range(1, NUM_OUTPUTS + 1)},
            "ext_audio_mode": "Bind to Input",
            "output_ext_audio_source": {i: i for i in range(1, NUM_OUTPUTS + 1)},
        }

    @property
    def input_names(self) -> list[str]:
        """Return input port names."""
        return self._input_names

    @property
    def output_names(self) -> list[str]:
        """Return output port names."""
        return self._output_names

    def get_input_name(self, index: int) -> str:
        """Get input name by index (1-based)."""
        if 1 <= index <= len(self._input_names):
            name = self._input_names[index - 1]
            # Check if it's a default name like "Input1" or "Input 1"
            default_patterns = [f"Input{index}", f"Input {index}", f"input{index}", f"input {index}"]
            if name in default_patterns:
                return f"Input {index}"
            return name
        return f"Input {index}"

    def get_output_name(self, index: int) -> str:
        """Get output name by index (1-based)."""
        if 1 <= index <= len(self._output_names):
            name = self._output_names[index - 1]
            # Check if it's a default name like "Output1" or "Output 1"
            default_patterns = [f"Output{index}", f"Output {index}", f"output{index}", f"output {index}"]
            if name in default_patterns:
                return f"Output {index}"
            return name
        return f"Output {index}"

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self._device_info

    def set_optimistic_state(self, key: str, value: Any, sub_key: int | None = None) -> None:
        """Set optimistic state for immediate UI feedback."""
        if sub_key is not None:
            if key not in self._optimistic_state:
                self._optimistic_state[key] = {}
            self._optimistic_state[key][sub_key] = value
        else:
            self._optimistic_state[key] = value
        
        # Trigger entity updates
        self.async_set_updated_data(self._merge_data(self._last_known_data))

    def clear_optimistic_state(self, key: str, sub_key: int | None = None) -> None:
        """Clear optimistic state after confirmation."""
        if sub_key is not None:
            if key in self._optimistic_state and sub_key in self._optimistic_state[key]:
                del self._optimistic_state[key][sub_key]
                if not self._optimistic_state[key]:
                    del self._optimistic_state[key]
        elif key in self._optimistic_state:
            del self._optimistic_state[key]

    def _merge_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Merge actual data with optimistic state."""
        merged = data.copy()
        
        for key, value in self._optimistic_state.items():
            if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                merged[key] = merged[key].copy()
                merged[key].update(value)
            else:
                merged[key] = value
        
        return merged

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the matrix."""
        try:
            data = await self._fetch_all_data()
            self._available = True
            self._last_known_data = data
            
            # Clear optimistic state since we have real data now
            self._optimistic_state.clear()
            
            return data
        except OreiMatrixConnectionError as err:
            self._available = False
            _LOGGER.warning("Connection error during update: %s", err)
            # Return last known data instead of failing completely
            if self._last_known_data:
                return self._last_known_data
            raise UpdateFailed(f"Connection error: {err}") from err
        except OreiMatrixError as err:
            _LOGGER.warning("Error communicating with matrix: %s", err)
            # Return last known data
            if self._last_known_data:
                return self._last_known_data
            raise UpdateFailed(f"Error communicating with matrix: {err}") from err

    async def _fetch_all_data(self) -> dict[str, Any]:
        """Fetch all data from the matrix using single 's status!' command."""
        # Start with last known data or defaults to avoid "Unknown" flickering
        if not self._last_known_data:
            self._last_known_data = self._get_default_data()

        try:
            # Single command gets everything!
            full_status = await self.api.get_full_status()
            self._update_data_from_status(full_status)
            
            # Store IP/network info for device info
            if full_status.get("mac_address"):
                self._device_info["mac_address"] = full_status["mac_address"]
            
            _LOGGER.debug("Fetched full status successfully")
            
        except OreiMatrixError as err:
            _LOGGER.warning("Failed to get full status: %s", err)
            # Keep last known data

        self._init_complete = True
        return self._last_known_data.copy()

    async def async_fetch_device_info(self) -> None:
        """Fetch device information using consolidated status command."""
        try:
            # Get model and firmware with quick dedicated commands
            model = await self.api.get_model()
            firmware = await self.api.get_firmware_version()
            
            # Get MAC and IP from full status (faster than separate calls)
            full_status = await self.api.get_full_status()
            
            self._device_info = {
                "model": model or "Orei HDMI Matrix",
                "firmware_version": firmware or "Unknown",
                "mac_address": full_status.get("mac_address", ""),
                "ip_config": {
                    "ip_mode": full_status.get("ip_mode", ""),
                    "ip_address": full_status.get("ip_address", ""),
                    "subnet_mask": full_status.get("subnet_mask", ""),
                    "gateway": full_status.get("gateway", ""),
                    "tcp_port": full_status.get("tcp_port", "8000"),
                    "telnet_port": full_status.get("telnet_port", "23"),
                },
            }
            
            # Also populate initial data from this status call
            self._last_known_data = self._get_default_data()
            self._update_data_from_status(full_status)
            
            _LOGGER.debug("Device info: %s", self._device_info)
        except OreiMatrixError as err:
            _LOGGER.warning("Failed to fetch device info: %s", err)
            self._device_info = {
                "model": "Orei HDMI Matrix",
                "firmware_version": "Unknown",
                "mac_address": "",
                "ip_config": {},
            }

    def _update_data_from_status(self, full_status: dict[str, Any]) -> None:
        """Update internal data from full status response."""
        if "power" in full_status:
            self._last_known_data["power"] = full_status["power"]
        if "beep" in full_status:
            self._last_known_data["beep"] = full_status["beep"]
        if "lock" in full_status:
            self._last_known_data["lock"] = full_status["lock"]
        
        if full_status.get("routing"):
            self._last_known_data["routing"] = full_status["routing"]
        if full_status.get("input_status"):
            self._last_known_data["input_status"].update(full_status["input_status"])
        if full_status.get("output_status"):
            self._last_known_data["output_status"].update(full_status["output_status"])
        if full_status.get("output_hdcp"):
            self._last_known_data["output_hdcp"].update(full_status["output_hdcp"])
        if full_status.get("output_stream"):
            self._last_known_data["output_stream"].update(full_status["output_stream"])
        if full_status.get("output_scaler"):
            self._last_known_data["output_scaler"].update(full_status["output_scaler"])
        if full_status.get("output_hdr"):
            self._last_known_data["output_hdr"].update(full_status["output_hdr"])
        if full_status.get("output_arc"):
            self._last_known_data["output_arc"].update(full_status["output_arc"])
        if full_status.get("output_audio_mute"):
            self._last_known_data["output_audio_mute"] = full_status["output_audio_mute"]
        if full_status.get("input_edid"):
            self._last_known_data["input_edid"].update(full_status["input_edid"])
        if full_status.get("output_ext_audio"):
            self._last_known_data["output_ext_audio"].update(full_status["output_ext_audio"])
        if full_status.get("ext_audio_mode"):
            self._last_known_data["ext_audio_mode"] = full_status["ext_audio_mode"]
        if full_status.get("output_ext_audio_source"):
            self._last_known_data["output_ext_audio_source"].update(full_status["output_ext_audio_source"])

    async def async_fetch_names(self) -> bool:
        """Fetch port names from HTTP API."""
        sync_names = self.config_entry.options.get(CONF_SYNC_NAMES, True)
        if not sync_names:
            _LOGGER.debug("Name sync disabled, using defaults")
            return False

        try:
            names = await self.api.get_all_names()
            
            input_names = names.get("input_names", [])
            output_names = names.get("output_names", [])
            
            if input_names and len(input_names) == NUM_INPUTS:
                self._input_names = input_names
                _LOGGER.debug("Loaded input names: %s", input_names)
            
            if output_names and len(output_names) == NUM_OUTPUTS:
                self._output_names = output_names
                _LOGGER.debug("Loaded output names: %s", output_names)
            
            self._names_loaded = True
            
            # Notify entities of name changes by triggering a data update
            if self.data:
                self.async_set_updated_data(self.data)
            
            return True
        except Exception as err:
            _LOGGER.warning("Failed to fetch port names: %s", err)
            return False

    def start_name_sync(self) -> None:
        """Start periodic name sync."""
        if self._name_sync_unsub is not None:
            return  # Already running
        
        sync_names = self.config_entry.options.get(CONF_SYNC_NAMES, True)
        if not sync_names:
            return
        
        @callback
        def _async_name_sync(now: Any = None) -> None:
            """Trigger name sync."""
            self.hass.async_create_task(self.async_fetch_names())
        
        self._name_sync_unsub = async_track_time_interval(
            self.hass,
            _async_name_sync,
            timedelta(seconds=NAME_SYNC_INTERVAL),
        )
        _LOGGER.debug("Started name sync with %ds interval", NAME_SYNC_INTERVAL)

    def stop_name_sync(self) -> None:
        """Stop periodic name sync."""
        if self._name_sync_unsub is not None:
            self._name_sync_unsub()
            self._name_sync_unsub = None
            _LOGGER.debug("Stopped name sync")

    async def async_set_input_name(self, index: int, name: str) -> bool:
        """Set input port name."""
        success = await self.api.set_input_name(index, name)
        if success:
            # Update local cache
            if 1 <= index <= len(self._input_names):
                self._input_names[index - 1] = name
            # Refresh names to confirm
            await self.async_fetch_names()
        return success

    async def async_set_output_name(self, index: int, name: str) -> bool:
        """Set output port name."""
        success = await self.api.set_output_name(index, name)
        if success:
            # Update local cache
            if 1 <= index <= len(self._output_names):
                self._output_names[index - 1] = name
            # Refresh names to confirm
            await self.async_fetch_names()
        return success

    # ==================== Command Methods with Optimistic Updates ====================

    async def async_set_power(self, state: bool) -> None:
        """Set power state."""
        self.set_optimistic_state("power", state)
        try:
            await self.api.set_power(state)
        except OreiMatrixError:
            self.clear_optimistic_state("power")
            raise
        # Schedule refresh to confirm
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_beep(self, state: bool) -> None:
        """Set beep state."""
        self.set_optimistic_state("beep", state)
        try:
            await self.api.set_beep(state)
        except OreiMatrixError:
            self.clear_optimistic_state("beep")
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_lock(self, state: bool) -> None:
        """Set panel lock state."""
        self.set_optimistic_state("lock", state)
        try:
            await self.api.set_lock(state)
        except OreiMatrixError:
            self.clear_optimistic_state("lock")
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_source(self, output: int, source: int) -> None:
        """Set output source."""
        self.set_optimistic_state("routing", source, output)
        try:
            await self.api.set_output_source(output, source)
        except OreiMatrixError:
            self.clear_optimistic_state("routing", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_hdcp(self, output: int, mode: int) -> None:
        """Set output HDCP mode."""
        from .const import HDCP_OPTIONS
        mode_name = HDCP_OPTIONS.get(mode, "Follow Sink")
        self.set_optimistic_state("output_hdcp", mode_name, output)
        try:
            await self.api.set_output_hdcp(output, mode)
        except OreiMatrixError:
            self.clear_optimistic_state("output_hdcp", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_stream(self, output: int, enable: bool) -> None:
        """Set output stream enable."""
        self.set_optimistic_state("output_stream", enable, output)
        try:
            await self.api.set_output_stream(output, enable)
        except OreiMatrixError:
            self.clear_optimistic_state("output_stream", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_scaler(self, output: int, mode: int) -> None:
        """Set output scaler mode."""
        from .const import SCALER_OPTIONS
        mode_name = SCALER_OPTIONS.get(mode, "Pass-through")
        self.set_optimistic_state("output_scaler", mode_name, output)
        try:
            await self.api.set_output_scaler(output, mode)
        except OreiMatrixError:
            self.clear_optimistic_state("output_scaler", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_hdr(self, output: int, mode: int) -> None:
        """Set output HDR mode."""
        from .const import HDR_OPTIONS
        mode_name = HDR_OPTIONS.get(mode, "Pass-through")
        self.set_optimistic_state("output_hdr", mode_name, output)
        try:
            await self.api.set_output_hdr(output, mode)
        except OreiMatrixError:
            self.clear_optimistic_state("output_hdr", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_arc(self, output: int, enable: bool) -> None:
        """Set output ARC enable."""
        self.set_optimistic_state("output_arc", enable, output)
        try:
            await self.api.set_output_arc(output, enable)
        except OreiMatrixError:
            self.clear_optimistic_state("output_arc", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_audio_mute(self, output: int, mute: bool) -> None:
        """Set output audio mute."""
        self.set_optimistic_state("output_audio_mute", mute, output)
        try:
            await self.api.set_output_audio_mute(output, mute)
        except OreiMatrixError:
            self.clear_optimistic_state("output_audio_mute", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_input_edid(self, input_num: int, edid_mode: int) -> None:
        """Set input EDID mode."""
        from .const import EDID_OPTIONS
        edid_name = EDID_OPTIONS.get(edid_mode, "8K FRL12G HDR, 7.1CH")
        self.set_optimistic_state("input_edid", edid_name, input_num)
        try:
            await self.api.set_input_edid(input_num, edid_mode)
        except OreiMatrixError:
            self.clear_optimistic_state("input_edid", input_num)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_copy_edid(self, input_num: int, output_num: int) -> None:
        """Copy EDID from output to input."""
        try:
            await self.api.copy_edid_from_output(input_num, output_num)
        except OreiMatrixError:
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_ext_audio(self, output: int, enable: bool) -> None:
        """Set output external audio enable."""
        self.set_optimistic_state("output_ext_audio", enable, output)
        try:
            await self.api.set_output_ext_audio(output, enable)
        except OreiMatrixError:
            self.clear_optimistic_state("output_ext_audio", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_ext_audio_mode(self, mode: int) -> None:
        """Set external audio mode."""
        from .const import EXT_AUDIO_MODE_OPTIONS
        mode_name = EXT_AUDIO_MODE_OPTIONS.get(mode, "Bind to Input")
        self.set_optimistic_state("ext_audio_mode", mode_name)
        try:
            await self.api.set_ext_audio_mode(mode)
        except OreiMatrixError:
            self.clear_optimistic_state("ext_audio_mode")
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_output_ext_audio_source(self, output: int, source: int) -> None:
        """Set output external audio source."""
        self.set_optimistic_state("output_ext_audio_source", source, output)
        try:
            await self.api.set_output_ext_audio_source(output, source)
        except OreiMatrixError:
            self.clear_optimistic_state("output_ext_audio_source", output)
            raise
        self.hass.async_create_task(self._delayed_refresh())

    async def async_set_lcd_time(self, mode: int) -> None:
        """Set LCD on time mode."""
        await self.api.set_lcd_time(mode)

    async def async_set_logo(self, text: str) -> None:
        """Set logo text."""
        await self.api.set_logo(1, text)

    async def async_save_preset(self, preset: int) -> None:
        """Save current routing to preset."""
        await self.api.save_preset(preset)

    async def async_recall_preset(self, preset: int) -> None:
        """Recall preset."""
        await self.api.recall_preset(preset)
        await self.async_request_refresh()

    async def async_clear_preset(self, preset: int) -> None:
        """Clear preset."""
        await self.api.clear_preset(preset)

    async def async_reboot(self) -> None:
        """Reboot the device."""
        await self.api.reboot()

    async def async_reset(self) -> None:
        """Reset to factory defaults."""
        await self.api.reset()

    async def async_send_cec_input(self, input_num: int, command: str) -> None:
        """Send CEC command to input."""
        await self.api.send_cec_input(input_num, command)

    async def async_send_cec_output(self, output_num: int, command: str) -> None:
        """Send CEC command to output."""
        await self.api.send_cec_output(output_num, command)

    async def async_send_command(self, command: str) -> str:
        """Send raw command."""
        return await self.api.send_command(command)

    async def _delayed_refresh(self, delay: float = 1.0) -> None:
        """Schedule a delayed refresh to confirm state."""
        await asyncio.sleep(delay)
        await self.async_request_refresh()
