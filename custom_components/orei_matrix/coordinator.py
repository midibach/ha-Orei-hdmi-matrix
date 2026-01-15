"""Data update coordinator for Orei HDMI Matrix."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OreiMatrixAPI, OreiMatrixConnectionError, OreiMatrixError
from .const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NUM_INPUTS,
    NUM_OUTPUTS,
)

_LOGGER = logging.getLogger(__name__)


class OreiMatrixCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching data from the Orei Matrix."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: OreiMatrixAPI,
        name: str,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.api = api
        self._device_info: dict[str, Any] = {}
        self._available = True

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self._available

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        return self._device_info

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the matrix."""
        try:
            data = await self._fetch_all_data()
            self._available = True
            return data
        except OreiMatrixConnectionError as err:
            self._available = False
            raise UpdateFailed(f"Connection error: {err}") from err
        except OreiMatrixError as err:
            raise UpdateFailed(f"Error communicating with matrix: {err}") from err

    async def _fetch_all_data(self) -> dict[str, Any]:
        """Fetch all data from the matrix."""
        data: dict[str, Any] = {
            "power": False,
            "beep": False,
            "lock": False,
            "routing": {},
            "input_status": {},
            "output_status": {},
            "output_hdcp": {},
            "output_stream": {},
            "output_scaler": {},
            "output_hdr": {},
            "output_arc": {},
            "input_edid": {},
            "output_ext_audio": {},
            "ext_audio_mode": "Bind to Input",
            "output_ext_audio_source": {},
            "ip_config": {},
        }

        # Get basic status
        try:
            data["power"] = await self.api.get_power()
        except OreiMatrixError:
            _LOGGER.debug("Failed to get power state")

        try:
            data["beep"] = await self.api.get_beep()
        except OreiMatrixError:
            _LOGGER.debug("Failed to get beep state")

        try:
            data["lock"] = await self.api.get_lock()
        except OreiMatrixError:
            _LOGGER.debug("Failed to get lock state")

        # Get routing information
        try:
            data["routing"] = await self.api.get_output_source(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get routing")

        # Get connection status
        try:
            data["input_status"] = await self.api.get_input_status(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get input status")

        try:
            data["output_status"] = await self.api.get_output_status(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get output status")

        # Get output settings (batched to reduce polling time)
        try:
            data["output_hdcp"] = await self.api.get_output_hdcp(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get HDCP settings")

        try:
            data["output_stream"] = await self.api.get_output_stream(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get stream settings")

        try:
            data["output_scaler"] = await self.api.get_output_scaler(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get scaler settings")

        try:
            data["output_hdr"] = await self.api.get_output_hdr(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get HDR settings")

        try:
            data["output_arc"] = await self.api.get_output_arc(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get ARC settings")

        # Get EDID settings
        try:
            data["input_edid"] = await self.api.get_input_edid(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get EDID settings")

        # Get external audio settings
        try:
            data["output_ext_audio"] = await self.api.get_output_ext_audio(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get ext audio settings")

        try:
            data["ext_audio_mode"] = await self.api.get_ext_audio_mode()
        except OreiMatrixError:
            _LOGGER.debug("Failed to get ext audio mode")

        try:
            data["output_ext_audio_source"] = await self.api.get_output_ext_audio_source(0)
        except OreiMatrixError:
            _LOGGER.debug("Failed to get ext audio sources")

        return data

    async def async_fetch_device_info(self) -> None:
        """Fetch device information."""
        try:
            model = await self.api.get_model()
            firmware = await self.api.get_firmware_version()
            mac = await self.api.get_mac_address()
            ip_config = await self.api.get_ip_config()

            self._device_info = {
                "model": model,
                "firmware_version": firmware,
                "mac_address": mac or ip_config.get("mac_address", ""),
                "ip_config": ip_config,
            }
            _LOGGER.debug("Device info: %s", self._device_info)
        except OreiMatrixError as err:
            _LOGGER.warning("Failed to fetch device info: %s", err)

    # ==================== Command Methods ====================

    async def async_set_power(self, state: bool) -> None:
        """Set power state."""
        await self.api.set_power(state)
        await self.async_request_refresh()

    async def async_set_beep(self, state: bool) -> None:
        """Set beep state."""
        await self.api.set_beep(state)
        await self.async_request_refresh()

    async def async_set_lock(self, state: bool) -> None:
        """Set panel lock state."""
        await self.api.set_lock(state)
        await self.async_request_refresh()

    async def async_set_output_source(self, output: int, source: int) -> None:
        """Set output source."""
        await self.api.set_output_source(output, source)
        await self.async_request_refresh()

    async def async_set_output_hdcp(self, output: int, mode: int) -> None:
        """Set output HDCP mode."""
        await self.api.set_output_hdcp(output, mode)
        await self.async_request_refresh()

    async def async_set_output_stream(self, output: int, enable: bool) -> None:
        """Set output stream enable."""
        await self.api.set_output_stream(output, enable)
        await self.async_request_refresh()

    async def async_set_output_scaler(self, output: int, mode: int) -> None:
        """Set output scaler mode."""
        await self.api.set_output_scaler(output, mode)
        await self.async_request_refresh()

    async def async_set_output_hdr(self, output: int, mode: int) -> None:
        """Set output HDR mode."""
        await self.api.set_output_hdr(output, mode)
        await self.async_request_refresh()

    async def async_set_output_arc(self, output: int, enable: bool) -> None:
        """Set output ARC enable."""
        await self.api.set_output_arc(output, enable)
        await self.async_request_refresh()

    async def async_set_input_edid(self, input_num: int, edid_mode: int) -> None:
        """Set input EDID mode."""
        await self.api.set_input_edid(input_num, edid_mode)
        await self.async_request_refresh()

    async def async_copy_edid(self, input_num: int, output_num: int) -> None:
        """Copy EDID from output to input."""
        await self.api.copy_edid_from_output(input_num, output_num)
        await self.async_request_refresh()

    async def async_set_output_ext_audio(self, output: int, enable: bool) -> None:
        """Set output external audio enable."""
        await self.api.set_output_ext_audio(output, enable)
        await self.async_request_refresh()

    async def async_set_ext_audio_mode(self, mode: int) -> None:
        """Set external audio mode."""
        await self.api.set_ext_audio_mode(mode)
        await self.async_request_refresh()

    async def async_set_output_ext_audio_source(self, output: int, source: int) -> None:
        """Set output external audio source."""
        await self.api.set_output_ext_audio_source(output, source)
        await self.async_request_refresh()

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
