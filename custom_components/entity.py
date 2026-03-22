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
    STATUS_READ_TIMEOUT,
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
        self._http_lock = asyncio.Lock()
        self._connected = False
        self._last_command_time: float = 0
        self._http_session: aiohttp.ClientSession | None = None

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
        """Make HTTP POST request to the device.
        
        The device expects JSON payload with Content-Type: application/x-www-form-urlencoded
        and returns JSON but with Content-Type: text/plain (quirky!).
        """
        import json as json_module
        
        url = f"http://{self.host}{HTTP_API_PATH}"
        
        # Add language parameter
        data["language"] = 0
        
        # Serialize to JSON string
        json_body = json_module.dumps(data)
        
        _LOGGER.debug("HTTP request to %s: %s", url, data.get("comhead", "unknown"))
        
        try:
            session = await self._get_http_session()
            async with session.post(
                url,
                data=json_body,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Authorization": "Bearer null",
                },
            ) as response:
                if response.status != 200:
                    _LOGGER.warning("HTTP request failed: status %d", response.status)
                    raise OreiMatrixConnectionError(
                        f"HTTP request failed with status {response.status}"
                    )
                
                # Device returns JSON but with text/plain content-type
                # So we read as text and parse manually
                text = await response.text()
                _LOGGER.debug("HTTP response text: %s", text[:200] if len(text) > 200 else text)
                
                try:
                    result = json_module.loads(text)
                    _LOGGER.debug("HTTP response parsed: %s", result)
                    return result
                except json_module.JSONDecodeError as err:
                    _LOGGER.warning("Failed to parse HTTP response as JSON: %s", err)
                    raise OreiMatrixConnectionError(f"Invalid JSON response: {text[:100]}") from err
                    
        except aiohttp.ClientError as err:
            _LOGGER.warning("HTTP client error: %s", err)
            raise OreiMatrixConnectionError(f"HTTP request error: {err}") from err
        except OreiMatrixConnectionError:
            raise
        except Exception as err:
            _LOGGER.warning("HTTP request failed: %s", err)
            raise OreiMatrixConnectionError(f"HTTP request failed: {err}") from err

    async def get_input_names(self) -> list[str]:
        """Get input port names from HTTP API.
        
        Note: Authentication is NOT required to read names from this device.
        """
        async with self._http_lock:
            try:
                response = await self._http_request({
                    "comhead": "get input status",
                })
                
                names = response.get("inname", [])
                if names and len(names) == NUM_INPUTS:
                    _LOGGER.debug("Got input names: %s", names)
                    return names
                
                # Return defaults if no names in response
                _LOGGER.debug("No input names in response, using defaults. Fields: %s", 
                             list(response.keys()))
                return [f"Input {i}" for i in range(1, NUM_INPUTS + 1)]
                
            except OreiMatrixError as err:
                _LOGGER.debug("Failed to get input names: %s", err)
                return [f"Input {i}" for i in range(1, NUM_INPUTS + 1)]

    async def get_output_names(self) -> list[str]:
        """Get output port names from HTTP API.
        
        Note: Authentication is NOT required to read names from this device.
        """
        async with self._http_lock:
            try:
                response = await self._http_request({
                    "comhead": "get output status",
                })
                
                names = response.get("name", [])
                if names and len(names) == NUM_OUTPUTS:
                    _LOGGER.debug("Got output names: %s", names)
                    return names
                
                # Return defaults if no names in response
                _LOGGER.debug("No output names in response, using defaults. Fields: %s",
                             list(response.keys()))
                return [f"Output {i}" for i in range(1, NUM_OUTPUTS + 1)]
                
            except OreiMatrixError as err:
                _LOGGER.debug("Failed to get output names: %s", err)
                return [f"Output {i}" for i in range(1, NUM_OUTPUTS + 1)]

    async def set_input_name(self, index: int, name: str) -> bool:
        """Set input port name (index 1-8)."""
        if not 1 <= index <= NUM_INPUTS:
            raise ValueError(f"Input index must be 1-{NUM_INPUTS}")
        
        name = name[:MAX_PORT_NAME_LENGTH]
        
        async with self._http_lock:
            try:
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

    async def heartbeat(self) -> bool:
        """Send a heartbeat to check connection health.
        
        Returns True if connection is healthy, False otherwise.
        Uses 'r power!' as it returns a short, deterministic response.
        """
        try:
            response = await asyncio.wait_for(
                self.send_command("r power!"),
                timeout=5.0,
            )
            # Any response (even error) means connection is alive
            return bool(response)
        except (OreiMatrixError, asyncio.TimeoutError, OSError) as err:
            _LOGGER.warning("Heartbeat failed: %s", err)
            self._connected = False
            return False

    @property
    def is_connected(self) -> bool:
        """Return true if connected."""
        return self._connected and self._writer is not None

    async def reconnect(self) -> bool:
        """Force reconnection to the device."""
        _LOGGER.info("Forcing reconnection to Orei Matrix")
        await self.disconnect()
        try:
            return await self.connect()
        except OreiMatrixError as err:
            _LOGGER.warning("Reconnection failed: %s", err)
            return False

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
                
                # Check for errors - E00/E01/etc are error codes BUT only if it's a short response
                # In multi-line responses (like s status!), E00 appears as section dividers
                response_stripped = response.strip()
                if response_stripped.startswith("E0") and len(response_stripped) < 20:
                    # Short response starting with E0x is likely an error
                    error_msg = f"Command error: {response_stripped}"
                    _LOGGER.warning(error_msg)
                    raise OreiMatrixCommandError(error_msg)
                
                # Strip leading E00 section markers from multi-line responses
                if response_stripped.startswith("E00"):
                    response = response_stripped[3:].lstrip("\r\n ")
                
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
        consecutive_timeouts = 0
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = self.timeout - elapsed
            
            if remaining <= 0:
                _LOGGER.debug("Read timeout reached, response length: %d chars", 
                             len("".join(response_parts)))
                break
                
            try:
                data = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=min(remaining, 0.5),  # Shorter reads, check more often
                )
                if not data:
                    # Connection closed
                    break
                    
                consecutive_timeouts = 0  # Reset timeout counter
                response_parts.append(data.decode(errors="ignore"))
                full_response = "".join(response_parts)
                
                # Check if we've received a complete response
                if self._is_response_complete(full_response):
                    break
                    
            except asyncio.TimeoutError:
                consecutive_timeouts += 1
                full_response = "".join(response_parts)
                
                # For status responses, wait longer for complete data
                if "get the unit all status" in full_response.lower():
                    # Only give up after multiple consecutive timeouts
                    if consecutive_timeouts >= 4:  # 2 seconds of no data
                        _LOGGER.warning(
                            "Status response incomplete after %d timeouts, "
                            "response length: %d chars",
                            consecutive_timeouts, len(full_response)
                        )
                        break
                    continue  # Keep waiting
                
                # For other responses, break after some data received
                if response_parts and consecutive_timeouts >= 2:
                    break
                continue
        
        response = "".join(response_parts).strip()
        _LOGGER.debug("Read response: %d chars", len(response))
        return response

    def _is_response_complete(self, response: str) -> bool:
        """Check if the response is complete.
        
        For the full status response (s status!), we need to be very strict
        because partial responses cause entity toggling bugs.
        """
        if not response:
            return False
            
        response_lower = response.lower()
        
        # Full status response - MUST see mac address at the end
        # This is the definitive end marker for 's status!'
        if "get the unit all status" in response_lower:
            # This is a status response - only complete if we see the MAC address
            return "mac address:" in response_lower
        
        # For other multi-line responses, check for these end markers
        complete_markers = [
            "initialization finished",
        ]
        for marker in complete_markers:
            if marker in response_lower:
                return True
        
        # For single-line command responses, check if we have a complete line
        lines = response.strip().split("\n")
        if len(lines) == 1:
            last_line = lines[0].strip().lower()
            # Single line responses typically end with specific patterns
            if last_line.startswith("e0"):  # Error response
                return True
            if "->" in last_line:  # Routing response
                return True
            # Check for common single-line response endings
            if last_line.endswith(("on", "off", "enable", "disable")):
                return True
                
        # For multi-line non-status responses, be conservative
        # Wait for more data unless we have strong evidence we're done
        return False
        
        # If response ends with newline and has content
        if response.endswith("\n") and len(response.strip()) > 3:
            return True
            
        return False

    # ==================== System Commands ====================

    async def _read_status_response(self) -> str:
        """Read the full status response, waiting for MAC address as end marker.
        
        The status response is very long (100+ lines) and the device sends
        it slowly. We need to keep reading until we see the MAC address line
        or hit a longer timeout.
        """
        response_parts = []
        start_time = asyncio.get_event_loop().time()
        timeout = STATUS_READ_TIMEOUT  # Use longer timeout for status
        consecutive_empty_reads = 0
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            remaining = timeout - elapsed
            
            if remaining <= 0:
                _LOGGER.warning(
                    "Status read timeout after %ds, got %d chars",
                    timeout, len("".join(response_parts))
                )
                break
                
            try:
                data = await asyncio.wait_for(
                    self._reader.read(4096),
                    timeout=min(remaining, 0.5),
                )
                if not data:
                    # Connection closed
                    break
                    
                consecutive_empty_reads = 0
                response_parts.append(data.decode(errors="ignore"))
                full_response = "".join(response_parts)
                
                # Check for MAC address as definitive end marker
                if "mac address:" in full_response.lower():
                    _LOGGER.debug("Found MAC address, status complete")
                    # Read a bit more in case there's trailing data
                    await asyncio.sleep(0.2)
                    try:
                        extra = await asyncio.wait_for(
                            self._reader.read(1024), timeout=0.3
                        )
                        if extra:
                            response_parts.append(extra.decode(errors="ignore"))
                    except asyncio.TimeoutError:
                        pass
                    break
                    
            except asyncio.TimeoutError:
                consecutive_empty_reads += 1
                # Keep waiting for status - device is slow
                if consecutive_empty_reads >= 10:  # 5 seconds of no data
                    _LOGGER.warning(
                        "No data for 5s during status read, got %d chars",
                        len("".join(response_parts))
                    )
                    break
                continue
        
        response = "".join(response_parts).strip()
        _LOGGER.debug("Status response total: %d chars, %d lines", 
                     len(response), response.count('\n'))
        return response

    async def get_full_status(self) -> dict[str, Any]:
        """Get the full device status with all settings parsed."""
        # Send command
        async with self._lock:
            await self._ensure_connected()
            
            if not self._writer:
                raise OreiMatrixConnectionError("Not connected")
            
            # Send status command
            command = "s status!"
            _LOGGER.debug("Sending status command: %s", command)
            self._writer.write(f"{command}\r\n".encode())
            await self._writer.drain()
            
            await asyncio.sleep(COMMAND_DELAY)
            
            # Use specialized reader for status
            response = await self._read_status_response()
        
        # Log response info for debugging
        _LOGGER.debug(
            "Status response length: %d chars, first 300: %s", 
            len(response),
            response[:300] if len(response) > 300 else response
        )
        
        # Check if response looks complete
        if "mac address:" not in response.lower():
            _LOGGER.warning(
                "Status response appears incomplete (no MAC address). "
                "Got %d lines. Device may need more time.",
                response.count('\n')
            )
        
        parsed = self._parse_full_status(response)
        
        # Log key parsed values
        _LOGGER.debug(
            "Parsed status - power:%s beep:%s lock:%s routing_count:%d", 
            parsed.get("power"), 
            parsed.get("beep"), 
            parsed.get("lock"),
            len(parsed.get("routing", {}))
        )
        
        return parsed

    async def get_status(self) -> dict[str, Any]:
        """Get the full device status (alias for get_full_status)."""
        return await self.get_full_status()

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
        """Set output scaler/video mode (1=pass-through, 2=8k->4k, 3=8k/4k->1080p, 4=auto)."""
        # Device shows "video mode" in status, try that format first
        await self.send_command(f"s output {output_num} video mode {mode}!")

    async def get_output_hdr(self, output_num: int = 0) -> dict[int, str]:
        """Get output HDR mode (0=all)."""
        try:
            response = await self.send_command(f"r output {output_num} hdr!")
            return self._parse_output_setting(response, "hdr")
        except OreiMatrixError:
            return {}

    async def set_output_hdr(self, output_num: int, mode: int) -> None:
        """Set output HDR mode (1=pass-through, 2=hdr-to-sdr, 3=auto)."""
        # Device shows "hdr mode" in status, try that format
        await self.send_command(f"s output {output_num} hdr mode {mode}!")

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

    async def set_output_audio_mute(self, output_num: int, mute: bool) -> None:
        """Enable/disable output audio mute."""
        await self.send_command(f"s output {output_num} audio mute {1 if mute else 0}!")

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
        # Try dedicated command first
        try:
            response = await self.send_command("r mac addr!")
            match = re.search(r"([0-9A-Fa-f:]{17})", response)
            if match:
                return match.group(1)
        except OreiMatrixError:
            pass
        
        # Fall back to getting it from full status
        try:
            full_status = await self.get_full_status()
            return full_status.get("mac_address", "")
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

    def _parse_full_status(self, response: str) -> dict[str, Any]:
        """Parse the comprehensive status response from 's status!' command."""
        # Use None as default to track what was actually found
        status = {
            "power": None,  # Will be set if found
            "beep": None,   # Will be set if found
            "lock": None,   # Will be set if found
            "lcd_time": "30 seconds",
            "routing": {},
            "input_status": {},
            "output_status": {},
            "output_hdcp": {},
            "output_stream": {},
            "output_scaler": {},
            "output_hdr": {},
            "output_arc": {},
            "output_audio_mute": {},
            "input_edid": {},
            "output_ext_audio": {},
            "ext_audio_mode": "Bind to Input",
            "output_ext_audio_source": {},
            "ip_mode": "dhcp",
            "ip_address": "",
            "subnet_mask": "",
            "gateway": "",
            "tcp_port": "8000",
            "telnet_port": "23",
            "mac_address": "",
        }
        
        lines = response.split("\n")
        _LOGGER.debug("Parsing %d lines from status response", len(lines))
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Skip empty lines and E00 markers
            if not line_lower or (line_lower.startswith("e0") and len(line_lower) <= 3):
                continue
            
            # Skip header line
            if "get the unit all status" in line_lower:
                continue
            
            # System settings - be very specific to avoid false matches
            # Use EXACT line matching for these critical settings
            if line_lower == "power on":
                status["power"] = True
            elif line_lower == "power off":
                status["power"] = False
            
            # Beep - exact match only
            if line_lower == "beep on":
                status["beep"] = True
            elif line_lower == "beep off":
                status["beep"] = False
            
            # Lock - exact match for full line
            if line_lower == "panel button lock on":
                status["lock"] = True
            elif line_lower == "panel button lock off":
                status["lock"] = False
            
            # LCD time - line starts with "lcd on"
            if line_lower.startswith("lcd on "):
                lcd_value = line_lower[7:].strip()
                status["lcd_time"] = lcd_value
            
            # Input connection status: "hdmi input 1: sync"
            input_match = re.match(r"^hdmi\s+input\s+(\d+)\s*:\s*(\w+)$", line_lower)
            if input_match:
                port = int(input_match.group(1))
                state = input_match.group(2)
                status["input_status"][port] = CONNECTION_STATUS.get(state, state.capitalize())
            
            # Output connection status: "hdmi output 1: connect"
            output_match = re.match(r"^hdmi\s+output\s+(\d+)\s*:\s*(\w+)$", line_lower)
            if output_match:
                port = int(output_match.group(1))
                state = output_match.group(2)
                status["output_status"][port] = CONNECTION_STATUS.get(state, state.capitalize())
            
            # Routing: "output1->input1"
            routing_match = re.match(r"^output(\d+)->input(\d+)$", line_lower)
            if routing_match:
                output = int(routing_match.group(1))
                input_num = int(routing_match.group(2))
                status["routing"][output] = input_num
            
            # HDCP: "output 1 hdcp: follow sink"
            hdcp_match = re.match(r"^output\s+(\d+)\s+hdcp:\s*(.+)$", line_lower)
            if hdcp_match:
                port = int(hdcp_match.group(1))
                value = hdcp_match.group(2).strip()
                status["output_hdcp"][port] = self._normalize_hdcp_mode(value)
            
            # Stream: "output 1 stream: enable"
            stream_match = re.match(r"^output\s+(\d+)\s+stream:\s*(\w+)$", line_lower)
            if stream_match:
                port = int(stream_match.group(1))
                state = stream_match.group(2)
                status["output_stream"][port] = state in ("enable", "enabled", "on")
            
            # Video mode (scaler): "output 1 video mode: bypass"
            video_match = re.match(r"^output\s+(\d+)\s+video\s+mode:\s*(.+)$", line_lower)
            if video_match:
                port = int(video_match.group(1))
                mode = video_match.group(2).strip()
                status["output_scaler"][port] = self._normalize_scaler_mode(mode)
            
            # HDR mode: "output 1 hdr mode: pass-through"
            hdr_match = re.match(r"^output\s+(\d+)\s+hdr\s+mode:\s*(.+)$", line_lower)
            if hdr_match:
                port = int(hdr_match.group(1))
                mode = hdr_match.group(2).strip()
                status["output_hdr"][port] = self._normalize_hdr_mode(mode)
            
            # ARC: "output 1 arc: on"
            arc_match = re.match(r"^output\s+(\d+)\s+arc:\s*(\w+)$", line_lower)
            if arc_match:
                port = int(arc_match.group(1))
                state = arc_match.group(2)
                status["output_arc"][port] = state in ("on", "enable", "enabled")
            
            # Audio mute: "output 1 audio mute: off"
            mute_match = re.match(r"^output\s+(\d+)\s+audio\s+mute:\s*(\w+)$", line_lower)
            if mute_match:
                port = int(mute_match.group(1))
                state = mute_match.group(2)
                status["output_audio_mute"][port] = state in ("on", "mute", "muted")
            
            # EDID: "input 1 edid:copy from output 1" (note: no space before colon)
            edid_match = re.match(r"^input\s+(\d+)\s+edid:(.+)$", line_lower)
            if edid_match:
                port = int(edid_match.group(1))
                edid_value = edid_match.group(2).strip()
                status["input_edid"][port] = edid_value
            
            # Ext audio enable: "output 1 ext-audio: enable"
            ext_audio_match = re.match(r"^output\s+(\d+)\s+ext-audio:\s*(\w+)$", line_lower)
            if ext_audio_match:
                port = int(ext_audio_match.group(1))
                state = ext_audio_match.group(2)
                status["output_ext_audio"][port] = state in ("enable", "enabled", "on")
            
            # Ext audio mode: "output ext-audio mode: bind to input"
            ext_mode_match = re.match(r"^output\s+ext-audio\s+mode:\s*(.+)$", line_lower)
            if ext_mode_match:
                status["ext_audio_mode"] = ext_mode_match.group(1).strip().title()
            
            # Ext audio source: "output 1 ext-audio->input1"
            ext_src_match = re.match(r"^output\s+(\d+)\s+ext-audio->input(\d+)$", line_lower)
            if ext_src_match:
                port = int(ext_src_match.group(1))
                source = int(ext_src_match.group(2))
                status["output_ext_audio_source"][port] = source
            
            # IP settings - use startswith for more precise matching
            if line_lower.startswith("ip mode:"):
                status["ip_mode"] = line_lower[8:].strip()
            elif line_lower.startswith("ip:"):
                status["ip_address"] = line_lower[3:].strip()
            elif line_lower.startswith("subnet mask:"):
                status["subnet_mask"] = line_lower[12:].strip()
            elif line_lower.startswith("gateway:"):
                status["gateway"] = line_lower[8:].strip()
            elif line_lower.startswith("tcp/ip port:"):
                status["tcp_port"] = line_lower[12:].strip()
            elif line_lower.startswith("telnet port:"):
                status["telnet_port"] = line_lower[12:].strip()
            elif line_lower.startswith("mac address:"):
                status["mac_address"] = line_lower[12:].strip()
        
        # Set defaults only if not found in response
        if status["power"] is None:
            _LOGGER.debug("Power state not found in response, defaulting to True")
            status["power"] = True
        if status["beep"] is None:
            _LOGGER.debug("Beep state not found in response, defaulting to False")
            status["beep"] = False
        if status["lock"] is None:
            _LOGGER.debug("Lock state not found in response, defaulting to False")
            status["lock"] = False
        
        # Log what we parsed for debugging
        _LOGGER.debug(
            "Parsed: power=%s beep=%s lock=%s routing_count=%d",
            status["power"], status["beep"], status["lock"], len(status["routing"])
        )
        
        return status

    def _parse_status(self, response: str) -> dict[str, Any]:
        """Parse full status response (legacy alias)."""
        return self._parse_full_status(response)

    def _normalize_scaler_mode(self, mode: str) -> str:
        """Normalize scaler mode from device format to display format.
        
        Device returns: bypass, pass-through, 8k->4k, 8k/4k->1080p, auto
        We need:        Bypass, 8K to 4K, 8K/4K to 1080p, Auto (Follow Sink)
        """
        mode_lower = mode.lower().strip()
        
        if "bypass" in mode_lower:
            return "Bypass"
        elif "pass" in mode_lower:
            return "Bypass"  # Treat pass-through as bypass
        elif "8k/4k" in mode_lower or "8k/4k->1080" in mode_lower:
            return "8K/4K to 1080p"
        elif "8k->4k" in mode_lower or "8k to 4k" in mode_lower:
            return "8K to 4K"
        elif "auto" in mode_lower:
            return "Auto (Follow Sink)"
        else:
            # Unknown mode, return title-cased with arrow converted
            return mode.replace("->", " to ").title()

    def _normalize_hdr_mode(self, mode: str) -> str:
        """Normalize HDR mode from device format to display format.
        
        Device returns: pass-through, hdr to sdr, auto(follow sink edid)
        We need:        Pass-through, HDR to SDR, Auto (Follow Sink)
        """
        mode_lower = mode.lower().strip()
        
        if "pass" in mode_lower:
            return "Pass-through"
        elif "hdr to sdr" in mode_lower or "hdrtosdr" in mode_lower:
            return "HDR to SDR"
        elif "auto" in mode_lower or "follow sink" in mode_lower:
            return "Auto (Follow Sink)"
        else:
            # Unknown mode, return title-cased
            return mode.title()

    def _normalize_hdcp_mode(self, mode: str) -> str:
        """Normalize HDCP mode from device format to display format."""
        mode_lower = mode.lower().strip()
        
        if "1.4" in mode_lower or "hdcp1" in mode_lower:
            return "HDCP 1.4"
        elif "2.2" in mode_lower or "hdcp2" in mode_lower:
            return "HDCP 2.2"
        elif "follow sink" in mode_lower:
            return "Follow Sink"
        elif "follow source" in mode_lower:
            return "Follow Source"
        elif "user" in mode_lower:
            return "User Mode"
        else:
            return mode.title()

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
