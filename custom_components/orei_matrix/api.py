"""API Client for Orei HDMI Matrix communication."""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

import aiohttp

from .const import (
    COMMAND_DELAY,
    COMMAND_RETRY_DELAY,
    CONNECTION_STATUS,
    DEFAULT_HTTP_PORT,
    DEFAULT_PORT,
    DEFAULT_TIMEOUT,
    EXT_AUDIO_MODE_OPTIONS,
    HTTP_API_PATH,
    HTTP_TIMEOUT,
    MAX_PORT_NAME_LENGTH,
    MAX_RETRIES,
    NUM_INPUTS,
    NUM_OUTPUTS,
)

_LOGGER = logging.getLogger(__name__)


class OreiMatrixError(Exception):
    """Base exception for Orei Matrix errors."""


class OreiMatrixConnectionError(OreiMatrixError):
    """Connection error."""


class OreiMatrixCommandError(OreiMatrixError):
    """Command execution error."""


class OreiMatrixAuthError(OreiMatrixError):
    """Authentication error."""


class OreiMatrixAPI:
    """API client for Orei HDMI Matrix."""

    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
        password: str | None = None,
    ) -> None:
        """Initialize the API client."""
        self.host = host
        self.port = port
        self.timeout = timeout
        self._password = password or ""
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._http_lock = asyncio.Lock()
        self._connected = False
        self._last_command_time: float = 0
        self._http_session: aiohttp.ClientSession | None = None
        self._http_authenticated = False

    @property
    def connected(self) -> bool:
        """Return connection status."""
        return self._connected

    # ==================== HTTP API Methods ====================

    async def _get_http_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=HTTP_TIMEOUT)
            )
        return self._http_session

    async def _http_request(self, data: dict[str, Any]) -> dict[str, Any]:
        """Make HTTP POST request to the device."""
        url = f"http://{self.host}{HTTP_API_PATH}"
        
        # Add language parameter
        data["language"] = 0
        
        # Convert to form data
        form_data = "&".join(f"{k}={v}" for k, v in data.items())
        
        try:
            session = await self._get_http_session()
            async with session.post(
                url,
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            ) as response:
                if response.status != 200:
                    raise OreiMatrixConnectionError(
                        f"HTTP request failed with status {response.status}"
                    )
                return await response.json()
        except aiohttp.ClientError as err:
            raise OreiMatrixConnectionError(f"HTTP request error: {err}") from err
        except Exception as err:
            raise OreiMatrixConnectionError(f"HTTP request failed: {err}") from err

    async def http_login(self) -> bool:
        """Authenticate with the HTTP API."""
        async with self._http_lock:
            try:
                response = await self._http_request({
                    "comhead": "login",
                    "user": "Admin",
                    "password": self._password,
                })
                self._http_authenticated = response.get("result") == 1
                if not self._http_authenticated:
                    _LOGGER.warning("HTTP authentication failed")
                return self._http_authenticated
            except OreiMatrixError:
                self._http_authenticated = False
                return False

    async def get_input_names(self) -> list[str]:
        """Get input port names from HTTP API."""
        async with self._http_lock:
            try:
                # Try without auth first
                response = await self._http_request({
                    "comhead": "get input status",
                })
                names = response.get("inname", [])
                if names and len(names) == NUM_INPUTS:
                    return names
                # Return defaults if response is unexpected
                return [f"Input{i}" for i in range(1, NUM_INPUTS + 1)]
            except OreiMatrixError as err:
                _LOGGER.debug("Failed to get input names: %s", err)
                return [f"Input{i}" for i in range(1, NUM_INPUTS + 1)]

    async def get_output_names(self) -> list[str]:
        """Get output port names from HTTP API."""
        async with self._http_lock:
            try:
                response = await self._http_request({
                    "comhead": "get output status",
                })
                names = response.get("name", [])
                if names and len(names) == NUM_OUTPUTS:
                    return names
                return [f"Output{i}" for i in range(1, NUM_OUTPUTS + 1)]
            except OreiMatrixError as err:
                _LOGGER.debug("Failed to get output names: %s", err)
                return [f"Output{i}" for i in range(1, NUM_OUTPUTS + 1)]

    async def set_input_name(self, index: int, name: str) -> bool:
        """Set input port name (index 1-8)."""
        if not 1 <= index <= NUM_INPUTS:
            raise ValueError(f"Input index must be 1-{NUM_INPUTS}")
        
        name = name[:MAX_PORT_NAME_LENGTH]
        
        async with self._http_lock:
            try:
                # May need to authenticate first
                if self._password and not self._http_authenticated:
                    await self.http_login()
                
                response = await self._http_request({
                    "comhead": "set input name",
                    "name": name,
                    "index": index,
                })
                return response.get("result", 0) == 1 or "name" in str(response).lower()
            except OreiMatrixError as err:
                _LOGGER.error("Failed to set input name: %s", err)
                return False

    async def set_output_name(self, index: int, name: str) -> bool:
        """Set output port name (index 1-8)."""
        if not 1 <= index <= NUM_OUTPUTS:
            raise ValueError(f"Output index must be 1-{NUM_OUTPUTS}")
        
        name = name[:MAX_PORT_NAME_LENGTH]
        
        async with self._http_lock:
            try:
                if self._password and not self._http_authenticated:
                    await self.http_login()
                
                response = await self._http_request({
                    "comhead": "set output name",
                    "name": name,
                    "index": index,
                })
                return response.get("result", 0) == 1 or "name" in str(response).lower()
            except OreiMatrixError as err:
                _LOGGER.error("Failed to set output name: %s", err)
                return False

    async def get_all_names(self) -> dict[str, list[str]]:
        """Get all input and output names."""
        input_names = await self.get_input_names()
        output_names = await self.get_output_names()
        return {
            "input_names": input_names,
            "output_names": output_names,
        }

    async def close_http_session(self) -> None:
        """Close HTTP session."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        self._http_session = None
        self._http_authenticated = False

    async def connect(self) -> bool:
        """Establish connection to the matrix."""
        if self._connected and self._writer:
            return True
            
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=self.timeout,
            )
            self._connected = True
            _LOGGER.debug("Connected to Orei Matrix at %s:%s", self.host, self.port)
            
            # Clear any initial buffer
            try:
                await asyncio.wait_for(self._reader.read(4096), timeout=0.5)
            except asyncio.TimeoutError:
                pass
                
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
        
        # Close HTTP session too
        await self.close_http_session()
        
        _LOGGER.debug("Disconnected from Orei Matrix")

    async def _ensure_connected(self) -> None:
        """Ensure we have an active connection."""
        if not self._connected or not self._writer:
            await self.disconnect()
            await self.connect()

    async def send_command(self, command: str, retry: bool = True) -> str:
        """Send a command and return the response."""
        async with self._lock:
            return await self._send_command_locked(command, retry)

    async def _send_command_locked(self, command: str, retry: bool = True) -> str:
        """Send a command with the lock already held."""
        last_error: Exception | None = None
        retries = MAX_RETRIES if retry else 1
        
        for attempt in range(retries):
            try:
                await self._ensure_connected()
                
                # Ensure command ends with !
                if not command.endswith("!"):
                    command = f"{command}!"
                
                # Rate limit commands
                now = asyncio.get_event_loop().time()
                time_since_last = now - self._last_command_time
                if time_since_last < COMMAND_DELAY:
                    await asyncio.sleep(COMMAND_DELAY - time_since_last)
                
                _LOGGER.debug("Sending command (attempt %d): %s", attempt + 1, command)
                
                # Clear any pending data in buffer
                if self._reader:
                    try:
                        while not self._reader.at_eof():
                            data = await asyncio.wait_for(self._reader.read(1024), timeout=0.1)
                            if not data:
                                break
                    except asyncio.TimeoutError:
                        pass
                
                self._writer.write(command.encode())
                await self._writer.drain()
                self._last_command_time = asyncio.get_event_loop().time()
                
                # Read response with multiple attempts
                response = await self._read_response()
                
                _LOGGER.debug("Received response: %s", response[:200] if response else "empty")
                
                # Check for errors - E00 is success, E01+ are actual errors
                # Strip E00 from response as it's just a success marker
                if response.startswith("E00"):
                    response = response[3:].lstrip("\r\n ")
                elif response.startswith("E0") and len(response) > 2 and response[2].isdigit():
                    # E01, E02, etc. are actual errors
                    error_code = response[:3]
                    if error_code != "E00":
                        error_msg = f"Command error {error_code}: {response}"
                        _LOGGER.warning(error_msg)
                        raise OreiMatrixCommandError(error_msg)
                
                return response
                
            except (OSError, ConnectionError, BrokenPipeError) as err:
                _LOGGER.debug("Connection error on attempt %d: %s", attempt + 1, err)
                last_error = OreiMatrixConnectionError(f"Communication error: {err}")
                self._connected = False
                await self.disconnect()
                if attempt < retries - 1:
                    await asyncio.sleep(COMMAND_RETRY_DELAY)
            except asyncio.TimeoutError as err:
                _LOGGER.debug("Timeout on attempt %d", attempt + 1)
                last_error = OreiMatrixConnectionError("Response timeout")
                if attempt < retries - 1:
                    await asyncio.sleep(COMMAND_RETRY_DELAY)
        
        if last_error:
            raise last_error
        raise OreiMatrixConnectionError("Unknown error")

    async def _read_response(self) -> str:
        """Read response from the device."""
        response_parts = []
        start_time = asyncio.get_event_loop().time()
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = self.timeout - elapsed
            
            if remaining <= 0:
                break
                
            try:
                data = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=min(remaining, 1.0),
                )
                if not data:
                    break
                    
                response_parts.append(data.decode(errors="ignore"))
                full_response = "".join(response_parts)
                
                # Check if we've received a complete response
                if self._is_response_complete(full_response):
                    break
                    
            except asyncio.TimeoutError:
                # If we have some data, check if it's complete enough
                if response_parts:
                    break
                continue
        
        return "".join(response_parts).strip()

    def _is_response_complete(self, response: str) -> bool:
        """Check if the response is complete."""
        if not response:
            return False
            
        response_lower = response.lower()
        
        # Multi-line responses that indicate completion
        complete_markers = [
            "initialization finished",
            "mac address:",
            "telnet port:",
        ]
        for marker in complete_markers:
            if marker in response_lower:
                return True
        
        # Single line responses - check for common endings
        lines = response.strip().split("\n")
        if lines:
            last_line = lines[-1].strip().lower()
            # Common response patterns
            if any(x in last_line for x in [
                "on", "off", "enable", "disable", "->", 
                "mode:", "hdcp:", "preset", "edid:", "arc:",
                "connect", "disconnect", "sync",
                "scaler", "hdr", "stream"
            ]):
                return True
        
        # If response ends with newline and has content
        if response.endswith("\n") and len(response.strip()) > 3:
            return True
            
        return False

    # ==================== System Commands ====================

    async def get_status(self) -> dict[str, Any]:
        """Get the full device status."""
        response = await self.send_command("status!")
        return self._parse_status(response)

    async def get_model(self) -> str:
        """Get device model."""
        try:
            response = await self.send_command("r type!")
            return response.strip() or "Orei HDMI Matrix"
        except OreiMatrixError:
            return "Orei HDMI Matrix"

    async def get_firmware_version(self) -> str:
        """Get firmware version."""
        try:
            response = await self.send_command("r fw version!")
            match = re.search(r"version\s*([\d.]+)", response, re.IGNORECASE)
            return match.group(1) if match else response.strip() or "Unknown"
        except OreiMatrixError:
            return "Unknown"

    async def get_power(self) -> bool:
        """Get power state."""
        try:
            response = await self.send_command("r power!")
            return "on" in response.lower()
        except OreiMatrixError:
            return True  # Assume on if we can communicate

    async def set_power(self, state: bool) -> None:
        """Set power state."""
        await self.send_command(f"power {1 if state else 0}!")

    async def get_beep(self) -> bool:
        """Get beep state."""
        try:
            response = await self.send_command("r beep!")
            return "on" in response.lower()
        except OreiMatrixError:
            return False

    async def set_beep(self, state: bool) -> None:
        """Set beep state."""
        await self.send_command(f"s beep {1 if state else 0}!")

    async def get_lock(self) -> bool:
        """Get panel lock state."""
        try:
            response = await self.send_command("r lock!")
            return "on" in response.lower()
        except OreiMatrixError:
            return False

    async def set_lock(self, state: bool) -> None:
        """Set panel lock state."""
        await self.send_command(f"s lock {1 if state else 0}!")

    async def get_lcd_mode(self) -> str:
        """Get LCD on time mode."""
        try:
            response = await self.send_command("r lcd mode!")
            return response.strip()
        except OreiMatrixError:
            return "Always On"

    async def set_lcd_time(self, mode: int) -> None:
        """Set LCD on time (0=off, 1=always, 2=15s, 3=30s, 4=60s)."""
        await self.send_command(f"s lcd on time {mode}!")

    async def set_logo(self, line: int, text: str) -> None:
        """Set logo text (line 1, max 16 chars)."""
        text = text[:16]
        await self.send_command(f"s logo{line} {text}!")

    async def reboot(self) -> None:
        """Reboot the device."""
        try:
            await self.send_command("reboot!", retry=False)
        except OreiMatrixError:
            pass  # Device will disconnect during reboot

    async def reset(self) -> None:
        """Reset to factory defaults."""
        try:
            await self.send_command("reset!", retry=False)
        except OreiMatrixError:
            pass  # Device will disconnect during reset

    # ==================== Input/Output Status ====================

    async def get_input_status(self, input_num: int = 0) -> dict[int, str]:
        """Get input connection status (0=all)."""
        try:
            response = await self.send_command(f"r link in {input_num}!")
            return self._parse_link_status(response, "input")
        except OreiMatrixError:
            return {}

    async def get_output_status(self, output_num: int = 0) -> dict[int, str]:
        """Get output connection status (0=all)."""
        try:
            response = await self.send_command(f"r link out {output_num}!")
            return self._parse_link_status(response, "output")
        except OreiMatrixError:
            return {}

    # ==================== Routing Commands ====================

    async def get_output_source(self, output_num: int = 0) -> dict[int, int]:
        """Get which input is routed to output (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} in source!")
            return self._parse_routing(response)
        except OreiMatrixError:
            return {}

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
        try:
            response = await self.send_command(f"r preset {preset_num}!")
            return response.strip()
        except OreiMatrixError:
            return ""

    # ==================== Output Settings ====================

    async def get_output_hdcp(self, output_num: int = 0) -> dict[int, str]:
        """Get output HDCP mode (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} hdcp!")
            return self._parse_output_setting(response, "hdcp")
        except OreiMatrixError:
            return {}

    async def set_output_hdcp(self, output_num: int, mode: int) -> None:
        """Set output HDCP mode (1-5)."""
        await self.send_command(f"s output {output_num} hdcp {mode}!")

    async def get_output_stream(self, output_num: int = 0) -> dict[int, bool]:
        """Get output stream enable state (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} stream!")
            return self._parse_output_bool(response, "stream")
        except OreiMatrixError:
            return {}

    async def set_output_stream(self, output_num: int, enable: bool) -> None:
        """Enable/disable output stream."""
        await self.send_command(f"s output {output_num} stream {1 if enable else 0}!")

    async def get_output_scaler(self, output_num: int = 0) -> dict[int, str]:
        """Get output scaler mode (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} scaler!")
            return self._parse_output_setting(response, "scaler")
        except OreiMatrixError:
            return {}

    async def set_output_scaler(self, output_num: int, mode: int) -> None:
        """Set output scaler mode (1-4)."""
        await self.send_command(f"s output {output_num} scaler {mode}!")

    async def get_output_hdr(self, output_num: int = 0) -> dict[int, str]:
        """Get output HDR mode (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} hdr!")
            return self._parse_output_setting(response, "hdr")
        except OreiMatrixError:
            return {}

    async def set_output_hdr(self, output_num: int, mode: int) -> None:
        """Set output HDR mode (1-3)."""
        await self.send_command(f"s output {output_num} hdr {mode}!")

    async def get_output_arc(self, output_num: int = 0) -> dict[int, bool]:
        """Get output ARC state (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} arc!")
            return self._parse_output_bool(response, "arc")
        except OreiMatrixError:
            return {}

    async def set_output_arc(self, output_num: int, enable: bool) -> None:
        """Enable/disable output ARC."""
        await self.send_command(f"s output {output_num} arc {1 if enable else 0}!")

    # ==================== EDID Commands ====================

    async def get_input_edid(self, input_num: int = 0) -> dict[int, str]:
        """Get input EDID mode (0=all)."""
        try:
            response = await self.send_command(f"r input {input_num} EDID!")
            return self._parse_input_edid(response)
        except OreiMatrixError:
            return {}

    async def set_input_edid(self, input_num: int, edid_mode: int) -> None:
        """Set input EDID mode (1-39)."""
        await self.send_command(f"s input {input_num} EDID {edid_mode}!")

    async def copy_edid_from_output(self, input_num: int, output_num: int) -> None:
        """Copy EDID from output to input (output 1-4)."""
        await self.send_command(f"s input {input_num} edid copy output {output_num}!")

    async def get_user_edid(self, user_num: int) -> str:
        """Get user EDID data (1-3)."""
        try:
            response = await self.send_command(f"r user {user_num} edid!")
            return response.strip()
        except OreiMatrixError:
            return ""

    async def set_user_edid(self, user_num: int, edid_data: str) -> None:
        """Set user EDID data (1-3)."""
        await self.send_command(f"s user {user_num} edid {edid_data}!")

    # ==================== External Audio Commands ====================

    async def get_output_ext_audio(self, output_num: int = 0) -> dict[int, bool]:
        """Get output external audio enable state (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} exa!")
            return self._parse_output_bool(response, "ext-audio")
        except OreiMatrixError:
            return {}

    async def set_output_ext_audio(self, output_num: int, enable: bool) -> None:
        """Enable/disable output external audio."""
        await self.send_command(f"s output {output_num} exa {1 if enable else 0}!")

    async def get_ext_audio_mode(self) -> str:
        """Get external audio mode."""
        try:
            response = await self.send_command("r output exa mode!")
            # Parse mode from response like "output ext-audio mode: bind to input"
            for mode_name in EXT_AUDIO_MODE_OPTIONS.values():
                if mode_name.lower() in response.lower():
                    return mode_name
            return "Bind to Input"
        except OreiMatrixError:
            return "Bind to Input"

    async def set_ext_audio_mode(self, mode: int) -> None:
        """Set external audio mode (0=bind to input, 1=bind to output, 2=matrix)."""
        await self.send_command(f"s output exa mode {mode}!")

    async def get_output_ext_audio_source(self, output_num: int = 0) -> dict[int, int]:
        """Get output external audio source (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} exa in source!")
            return self._parse_ext_audio_routing(response)
        except OreiMatrixError:
            return {}

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
        try:
            response = await self.send_command("r ipconfig!")
            return self._parse_ip_config(response)
        except OreiMatrixError:
            return {}

    async def get_mac_address(self) -> str:
        """Get MAC address."""
        try:
            response = await self.send_command("r mac addr!")
            match = re.search(r"([0-9A-Fa-f:]{17})", response)
            return match.group(1) if match else ""
        except OreiMatrixError:
            return ""

    async def get_ip_mode(self) -> str:
        """Get IP mode (Static/DHCP)."""
        try:
            response = await self.send_command("r ip mode!")
            return "DHCP" if "dhcp" in response.lower() else "Static"
        except OreiMatrixError:
            return "Static"

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
            "power": True,
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
            # Handle both "hdmi input 1:" and "input 1:" formats
            match = re.search(
                rf"(?:hdmi\s+)?{port_type}\s*(\d+)\s*:\s*(\w+)", line, re.IGNORECASE
            )
            if match:
                port_num = int(match.group(1))
                state = match.group(2).lower()
                status[port_num] = CONNECTION_STATUS.get(state, state.capitalize())
        
        return status

    def _parse_routing(self, response: str) -> dict[int, int]:
        """Parse routing response."""
        routing = {}
        lines = response.strip().split("\n")
        
        for line in lines:
            match = re.search(r"output\s*(\d+)\s*->\s*input\s*(\d+)", line, re.IGNORECASE)
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
            # Match patterns like "output 1 HDCP: HDCP 2.2" or "output 1 scaler mode: 8k->4k"
            match = re.search(
                rf"output\s*(\d+)\s*(?:{setting}|{setting}\s*mode)[:\s]+(.+)", 
                line, 
                re.IGNORECASE
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
                r"output\s*(\d+)\s*ext-?audio\s*-?>?\s*(input\s*(\d+)|output\s*(\d+)\s*ARC)",
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
