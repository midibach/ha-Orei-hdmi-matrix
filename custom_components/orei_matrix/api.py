"""API Client for Orei HDMI Matrix communication."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from .const import (
    COMMAND_DELAY,
    CONNECTION_STATUS,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    EDID_OPTIONS,
    EXT_AUDIO_MODE_OPTIONS,
    EXT_AUDIO_SOURCE_OPTIONS,
    HDCP_OPTIONS,
    HDR_OPTIONS,
    IP_MODE_OPTIONS,
    LCD_TIME_OPTIONS,
    NUM_INPUTS,
    NUM_OUTPUTS,
    SCALER_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)


class OreiMatrixError(Exception):
    """Base exception for Orei Matrix errors."""


class OreiMatrixConnectionError(OreiMatrixError):
    """Connection error."""


class OreiMatrixCommandError(OreiMatrixError):
    """Command execution error."""


class OreiMatrixAPI:
    """API client for Orei HDMI Matrix."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the API client."""
        self.host = host
        self.port = port
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._connected = False

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected

    async def connect(self) -> bool:
        """Establish connection to the matrix."""
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
            self._connected = True
            _LOGGER.debug("Connected to Orei Matrix at %s:%s", self.host, self.port)
            return True
        except asyncio.TimeoutError as err:
            self._connected = False
            raise OreiMatrixConnectionError(
                f"Connection timeout to {self.host}:{self.port}"
            ) from err
        except OSError as err:
            self._connected = False
            raise OreiMatrixConnectionError(
                f"Failed to connect to {self.host}:{self.port}: {err}"
            ) from err

    async def disconnect(self) -> None:
        """Close the connection."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        self._writer = None
        self._reader = None
        self._connected = False
        _LOGGER.debug("Disconnected from Orei Matrix")

    async def _ensure_connected(self) -> None:
        """Ensure we have an active connection."""
        if not self._connected or not self._writer:
            await self.connect()

    async def send_command(self, command: str) -> str:
        """Send a command and return the response."""
        async with self._lock:
            try:
                await self._ensure_connected()
                
                # Ensure command ends with !
                if not command.endswith("!"):
                    command = f"{command}!"
                
                _LOGGER.debug("Sending command: %s", command)
                
                self._writer.write(command.encode())
                await self._writer.drain()
                
                # Small delay to allow device to process
                await asyncio.sleep(COMMAND_DELAY)
                
                # Read response
                response_parts = []
                try:
                    while True:
                        data = await asyncio.wait_for(
                            self._reader.read(4096),
                            timeout=self.timeout,
                        )
                        if not data:
                            break
                        response_parts.append(data.decode(errors="ignore"))
                        # Check if we've received a complete response
                        full_response = "".join(response_parts)
                        if self._is_response_complete(full_response):
                            break
                except asyncio.TimeoutError:
                    pass
                
                response = "".join(response_parts).strip()
                _LOGGER.debug("Received response: %s", response)
                
                # Check for errors
                if response.startswith("E0"):
                    raise OreiMatrixCommandError(f"Command error: {response}")
                
                return response
                
            except (OSError, ConnectionError) as err:
                self._connected = False
                raise OreiMatrixConnectionError(f"Communication error: {err}") from err

    def _is_response_complete(self, response: str) -> bool:
        """Check if the response is complete."""
        # Most responses end with a newline
        if response.endswith("\n") or response.endswith("\r"):
            return True
        # Status command returns multiple lines
        if "initialization finished" in response.lower():
            return True
        # Single line responses
        if any(
            x in response.lower()
            for x in ["on", "off", "enable", "disable", "->", "mode:", "hdcp:"]
        ):
            return True
        return False

    # ==================== System Commands ====================

    async def get_status(self) -> dict[str, Any]:
        """Get the full device status."""
        response = await self.send_command("status!")
        return self._parse_status(response)

    async def get_model(self) -> str:
        """Get device model."""
        response = await self.send_command("r type!")
        return response.strip()

    async def get_firmware_version(self) -> str:
        """Get firmware version."""
        response = await self.send_command("r fw version!")
        match = re.search(r"version\s*([\d.]+)", response, re.IGNORECASE)
        return match.group(1) if match else response.strip()

    async def get_power(self) -> bool:
        """Get power state."""
        response = await self.send_command("r power!")
        return "on" in response.lower()

    async def set_power(self, state: bool) -> None:
        """Set power state."""
        await self.send_command(f"power {1 if state else 0}!")

    async def get_beep(self) -> bool:
        """Get beep state."""
        response = await self.send_command("r beep!")
        return "on" in response.lower()

    async def set_beep(self, state: bool) -> None:
        """Set beep state."""
        await self.send_command(f"s beep {1 if state else 0}!")

    async def get_lock(self) -> bool:
        """Get panel lock state."""
        response = await self.send_command("r lock!")
        return "on" in response.lower()

    async def set_lock(self, state: bool) -> None:
        """Set panel lock state."""
        await self.send_command(f"s lock {1 if state else 0}!")

    async def get_lcd_mode(self) -> str:
        """Get LCD on time mode."""
        response = await self.send_command("r lcd mode!")
        return response.strip()

    async def set_lcd_time(self, mode: int) -> None:
        """Set LCD on time (0=off, 1=always, 2=15s, 3=30s, 4=60s)."""
        await self.send_command(f"s lcd on time {mode}!")

    async def set_logo(self, line: int, text: str) -> None:
        """Set logo text (line 1, max 16 chars)."""
        text = text[:16]
        await self.send_command(f"s logo{line} {text}!")

    async def reboot(self) -> None:
        """Reboot the device."""
        await self.send_command("reboot!")

    async def reset(self) -> None:
        """Reset to factory defaults."""
        await self.send_command("reset!")

    # ==================== Input/Output Status ====================

    async def get_input_status(self, input_num: int = 0) -> dict[int, str]:
        """Get input connection status (0=all)."""
        response = await self.send_command(f"r link in {input_num}!")
        return self._parse_link_status(response, "input")

    async def get_output_status(self, output_num: int = 0) -> dict[int, str]:
        """Get output connection status (0=all)."""
        response = await self.send_command(f"r link out {output_num}!")
        return self._parse_link_status(response, "output")

    # ==================== Routing Commands ====================

    async def get_output_source(self, output_num: int = 0) -> dict[int, int]:
        """Get which input is routed to output (0=all)."""
        response = await self.send_command(f"r output {output_num} in source!")
        return self._parse_routing(response)

    async def set_output_source(self, output_num: int, input_num: int) -> None:
        """Route input to output (output 0=all)."""
        await self.send_command(f"s output {output_num} in source {input_num}!")

    async def set_all_outputs_to_input(self, input_num: int) -> None:
        """Route all outputs to a single input."""
        await self.send_command(f"s output 0 in source {input_num}!")

    # ==================== Preset Commands ====================

    async def save_preset(self, preset_num: int) -> None:
        """Save current routing to preset (1-8)."""
        await self.send_command(f"s save preset {preset_num}!")

    async def recall_preset(self, preset_num: int) -> None:
        """Recall preset (1-8)."""
        await self.send_command(f"s recall preset {preset_num}!")

    async def clear_preset(self, preset_num: int) -> None:
        """Clear preset (1-8)."""
        await self.send_command(f"s clear preset {preset_num}!")

    async def get_preset(self, preset_num: int) -> str:
        """Get preset information (1-8)."""
        response = await self.send_command(f"r preset {preset_num}!")
        return response.strip()

    # ==================== Output Settings ====================

    async def get_output_hdcp(self, output_num: int = 0) -> dict[int, str]:
        """Get output HDCP mode (0=all)."""
        response = await self.send_command(f"r output {output_num} hdcp!")
        return self._parse_output_setting(response, "hdcp")

    async def set_output_hdcp(self, output_num: int, mode: int) -> None:
        """Set output HDCP mode (1-5)."""
        await self.send_command(f"s output {output_num} hdcp {mode}!")

    async def get_output_stream(self, output_num: int = 0) -> dict[int, bool]:
        """Get output stream enable state (0=all)."""
        response = await self.send_command(f"r output {output_num} stream!")
        return self._parse_output_bool(response, "stream")

    async def set_output_stream(self, output_num: int, enable: bool) -> None:
        """Enable/disable output stream."""
        await self.send_command(f"s output {output_num} stream {1 if enable else 0}!")

    async def get_output_scaler(self, output_num: int = 0) -> dict[int, str]:
        """Get output scaler mode (0=all)."""
        response = await self.send_command(f"r output {output_num} scaler!")
        return self._parse_output_setting(response, "scaler")

    async def set_output_scaler(self, output_num: int, mode: int) -> None:
        """Set output scaler mode (1-4)."""
        await self.send_command(f"s output {output_num} scaler {mode}!")

    async def get_output_hdr(self, output_num: int = 0) -> dict[int, str]:
        """Get output HDR mode (0=all)."""
        response = await self.send_command(f"r output {output_num} hdr!")
        return self._parse_output_setting(response, "hdr")

    async def set_output_hdr(self, output_num: int, mode: int) -> None:
        """Set output HDR mode (1-3)."""
        await self.send_command(f"s output {output_num} hdr {mode}!")

    async def get_output_arc(self, output_num: int = 0) -> dict[int, bool]:
        """Get output ARC state (0=all)."""
        response = await self.send_command(f"r output {output_num} arc!")
        return self._parse_output_bool(response, "arc")

    async def set_output_arc(self, output_num: int, enable: bool) -> None:
        """Enable/disable output ARC."""
        await self.send_command(f"s output {output_num} arc {1 if enable else 0}!")

    # ==================== EDID Commands ====================

    async def get_input_edid(self, input_num: int = 0) -> dict[int, str]:
        """Get input EDID mode (0=all)."""
        response = await self.send_command(f"r input {input_num} EDID!")
        return self._parse_input_edid(response)

    async def set_input_edid(self, input_num: int, edid_mode: int) -> None:
        """Set input EDID mode (1-39)."""
        await self.send_command(f"s input {input_num} EDID {edid_mode}!")

    async def copy_edid_from_output(self, input_num: int, output_num: int) -> None:
        """Copy EDID from output to input (output 1-4)."""
        await self.send_command(f"s input {input_num} edid copy output {output_num}!")

    async def get_user_edid(self, user_num: int) -> str:
        """Get user EDID data (1-3)."""
        response = await self.send_command(f"r user {user_num} edid!")
        return response.strip()

    async def set_user_edid(self, user_num: int, edid_data: str) -> None:
        """Set user EDID data (1-3)."""
        await self.send_command(f"s user {user_num} edid {edid_data}!")

    # ==================== External Audio Commands ====================

    async def get_output_ext_audio(self, output_num: int = 0) -> dict[int, bool]:
        """Get output external audio enable state (0=all)."""
        response = await self.send_command(f"r output {output_num} exa!")
        return self._parse_output_bool(response, "ext-audio")

    async def set_output_ext_audio(self, output_num: int, enable: bool) -> None:
        """Enable/disable output external audio."""
        await self.send_command(f"s output {output_num} exa {1 if enable else 0}!")

    async def get_ext_audio_mode(self) -> str:
        """Get external audio mode."""
        response = await self.send_command("r output exa mode!")
        # Parse mode from response like "output ext-audio mode: bind to input"
        for mode_name in EXT_AUDIO_MODE_OPTIONS.values():
            if mode_name.lower() in response.lower():
                return mode_name
        return response.strip()

    async def set_ext_audio_mode(self, mode: int) -> None:
        """Set external audio mode (0=bind to input, 1=bind to output, 2=matrix)."""
        await self.send_command(f"s output exa mode {mode}!")

    async def get_output_ext_audio_source(self, output_num: int = 0) -> dict[int, int]:
        """Get output external audio source (0=all)."""
        response = await self.send_command(f"r output {output_num} exa in source!")
        return self._parse_ext_audio_routing(response)

    async def set_output_ext_audio_source(self, output_num: int, source: int) -> None:
        """Set output external audio source (1-16)."""
        await self.send_command(f"s output {output_num} exa in source {source}!")

    # ==================== CEC Commands ====================

    async def send_cec_input(self, input_num: int, command: str) -> None:
        """Send CEC command to input (0=all)."""
        await self.send_command(f"s cec in {input_num} {command}!")

    async def send_cec_output(self, output_num: int, command: str) -> None:
        """Send CEC command to output (0=all)."""
        await self.send_command(f"s cec hdmi out {output_num} {command}!")

    # ==================== Network Commands ====================

    async def get_ip_config(self) -> dict[str, str]:
        """Get IP configuration."""
        response = await self.send_command("r ipconfig!")
        return self._parse_ip_config(response)

    async def get_mac_address(self) -> str:
        """Get MAC address."""
        response = await self.send_command("r mac addr!")
        match = re.search(r"([0-9A-Fa-f:]{17})", response)
        return match.group(1) if match else ""

    async def get_ip_mode(self) -> str:
        """Get IP mode (Static/DHCP)."""
        response = await self.send_command("r ip mode!")
        return "DHCP" if "dhcp" in response.lower() else "Static"

    async def set_ip_mode(self, dhcp: bool) -> None:
        """Set IP mode (0=Static, 1=DHCP)."""
        await self.send_command(f"s ip mode {1 if dhcp else 0}!")

    async def set_ip_address(self, ip: str) -> None:
        """Set IP address."""
        await self.send_command(f"s ip addr {ip}!")

    async def set_subnet(self, subnet: str) -> None:
        """Set subnet mask."""
        await self.send_command(f"s subnet {subnet}!")

    async def set_gateway(self, gateway: str) -> None:
        """Set gateway."""
        await self.send_command(f"s gateway {gateway}!")

    async def set_tcp_port(self, port: int) -> None:
        """Set TCP/IP port."""
        await self.send_command(f"s tcp/ip port {port}!")

    async def set_telnet_port(self, port: int) -> None:
        """Set Telnet port."""
        await self.send_command(f"s telnet port {port}!")

    async def network_reboot(self) -> None:
        """Reboot network module."""
        await self.send_command("s net reboot!")

    # ==================== Response Parsing ====================

    def _parse_status(self, response: str) -> dict[str, Any]:
        """Parse full status response."""
        status = {
            "power": False,
            "beep": False,
            "lock": False,
            "routing": {},
            "inputs": {},
            "outputs": {},
        }
        
        lines = response.lower().split("\n")
        for line in lines:
            if "power on" in line:
                status["power"] = True
            elif "power off" in line:
                status["power"] = False
            if "beep on" in line:
                status["beep"] = True
            if "lock on" in line:
                status["lock"] = True
        
        return status

    def _parse_link_status(self, response: str, port_type: str) -> dict[int, str]:
        """Parse link status response."""
        status = {}
        lines = response.strip().split("\n")
        
        for line in lines:
            match = re.search(
                rf"{port_type}\s*(\d+):\s*(\w+)", line, re.IGNORECASE
            )
            if match:
                port_num = int(match.group(1))
                state = match.group(2).lower()
                status[port_num] = CONNECTION_STATUS.get(state, state)
        
        return status

    def _parse_routing(self, response: str) -> dict[int, int]:
        """Parse routing response."""
        routing = {}
        lines = response.strip().split("\n")
        
        for line in lines:
            match = re.search(r"output(\d+)->input(\d+)", line, re.IGNORECASE)
            if match:
                output_num = int(match.group(1))
                input_num = int(match.group(2))
                routing[output_num] = input_num
        
        return routing

    def _parse_output_setting(self, response: str, setting: str) -> dict[int, str]:
        """Parse output setting response."""
        settings = {}
        lines = response.strip().split("\n")
        
        for line in lines:
            match = re.search(
                rf"output\s*(\d+)\s*{setting}[:\s]+(.+)", line, re.IGNORECASE
            )
            if match:
                output_num = int(match.group(1))
                value = match.group(2).strip()
                settings[output_num] = value
        
        return settings

    def _parse_output_bool(self, response: str, setting: str) -> dict[int, bool]:
        """Parse output boolean setting response."""
        settings = {}
        lines = response.strip().split("\n")
        
        for line in lines:
            match = re.search(
                rf"output\s*(\d+)\s*{setting}[:\s]+(\w+)", line, re.IGNORECASE
            )
            if match:
                output_num = int(match.group(1))
                value = match.group(2).lower()
                settings[output_num] = value in ("on", "enable", "enabled")
        
        return settings

    def _parse_input_edid(self, response: str) -> dict[int, str]:
        """Parse input EDID response."""
        edids = {}
        lines = response.strip().split("\n")
        
        for line in lines:
            match = re.search(r"input\s*(\d+)\s*EDID[:\s]+(.+)", line, re.IGNORECASE)
            if match:
                input_num = int(match.group(1))
                edid = match.group(2).strip()
                edids[input_num] = edid
        
        return edids

    def _parse_ext_audio_routing(self, response: str) -> dict[int, int]:
        """Parse external audio routing response."""
        routing = {}
        lines = response.strip().split("\n")
        
        for line in lines:
            # Match patterns like "output1 ext-audio ->input1" or "output1 ext-audio->output1 ARC"
            match = re.search(
                r"output(\d+)\s*ext-audio\s*-?>?\s*(input(\d+)|output(\d+)\s*ARC)",
                line,
                re.IGNORECASE,
            )
            if match:
                output_num = int(match.group(1))
                if match.group(3):  # Input source
                    routing[output_num] = int(match.group(3))
                elif match.group(4):  # ARC source
                    routing[output_num] = int(match.group(4)) + 8  # ARC sources are 9-16
        
        return routing

    def _parse_ip_config(self, response: str) -> dict[str, str]:
        """Parse IP configuration response."""
        config = {}
        
        patterns = {
            "ip_mode": r"IP\s*Mode:\s*(\w+)",
            "ip_address": r"IP:\s*([\d.]+)",
            "subnet": r"Subnet\s*Mask:\s*([\d.]+)",
            "gateway": r"Gateway:\s*([\d.]+)",
            "tcp_port": r"TCP/IP\s*port:\s*(\d+)",
            "telnet_port": r"Telnet\s*port:\s*(\d+)",
            "mac_address": r"Mac\s*address:\s*([0-9A-Fa-f:]+)",
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                config[key] = match.group(1)
        
        return config
