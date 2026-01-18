"""The Orei HDMI Matrix integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from .api import OreiMatrixAPI, OreiMatrixConnectionError
from .const import (
    CONF_PASSWORD,
    CONF_SYNC_NAMES,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    NUM_INPUTS,
    NUM_OUTPUTS,
    NUM_PRESETS,
    SERVICE_CEC_COMMAND,
    SERVICE_CLEAR_PRESET,
    SERVICE_COPY_EDID,
    SERVICE_RECALL_PRESET,
    SERVICE_REFRESH_NAMES,
    SERVICE_SAVE_PRESET,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_ALL_ROUTING,
    SERVICE_SET_INPUT_NAME,
    SERVICE_SET_LOGO,
    SERVICE_SET_OUTPUT_NAME,
    SERVICE_SET_ROUTING,
)
from .coordinator import OreiMatrixCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SWITCH,
    Platform.SELECT,
    Platform.BUTTON,
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.TEXT,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Orei HDMI Matrix from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data.get(CONF_PORT, DEFAULT_PORT)
    password = entry.data.get(CONF_PASSWORD, "")
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

    _LOGGER.info(
        "Setting up Orei Matrix at %s:%s with %ds scan interval",
        host,
        port,
        scan_interval,
    )

    api = OreiMatrixAPI(host, port, password=password)
    
    try:
        await api.connect()
    except OreiMatrixConnectionError as err:
        _LOGGER.error("Failed to connect to Orei Matrix at %s:%s: %s", host, port, err)
        raise ConfigEntryNotReady(f"Failed to connect to {host}:{port}") from err

    coordinator = OreiMatrixCoordinator(
        hass,
        api,
        entry,
        scan_interval=scan_interval,
    )

    # Fetch device info - don't fail if this errors
    try:
        await coordinator.async_fetch_device_info()
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Failed to fetch device info, using defaults: %s", err)

    # Fetch port names from HTTP API
    try:
        await coordinator.async_fetch_names()
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Failed to fetch port names, using defaults: %s", err)

    # Fetch initial data - don't fail completely if some queries error
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception as err:  # noqa: BLE001
        _LOGGER.warning("Initial data fetch had errors, continuing: %s", err)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Start periodic name sync
    coordinator.start_name_sync()

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass)

    # Listen for options updates
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Orei Matrix integration setup complete for %s", entry.title)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator: OreiMatrixCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.stop_name_sync()
        await coordinator.api.disconnect()

    # Remove services if no more entries
    if not hass.data.get(DOMAIN):
        await async_unload_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for the integration."""
    
    # Check if services already registered
    if hass.services.has_service(DOMAIN, SERVICE_SEND_COMMAND):
        return
    
    async def handle_send_command(call: ServiceCall) -> None:
        """Handle send_command service."""
        device_id = call.data["device_id"]
        command = call.data["command"]
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_send_command(command)

    async def handle_set_routing(call: ServiceCall) -> None:
        """Handle set_routing service."""
        device_id = call.data["device_id"]
        output = int(call.data["output"])
        input_source = int(call.data["input"])
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_set_output_source(output, input_source)

    async def handle_set_all_routing(call: ServiceCall) -> None:
        """Handle set_all_routing service."""
        device_id = call.data["device_id"]
        input_source = int(call.data["input"])
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_set_output_source(0, input_source)

    async def handle_save_preset(call: ServiceCall) -> None:
        """Handle save_preset service."""
        device_id = call.data["device_id"]
        preset = int(call.data["preset"])
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_save_preset(preset)

    async def handle_recall_preset(call: ServiceCall) -> None:
        """Handle recall_preset service."""
        device_id = call.data["device_id"]
        preset = int(call.data["preset"])
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_recall_preset(preset)

    async def handle_clear_preset(call: ServiceCall) -> None:
        """Handle clear_preset service."""
        device_id = call.data["device_id"]
        preset = int(call.data["preset"])
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_clear_preset(preset)

    async def handle_cec_command(call: ServiceCall) -> None:
        """Handle cec_command service."""
        device_id = call.data["device_id"]
        target_type = call.data["target_type"]
        target_num = int(call.data["target_number"])
        command = call.data["command"]
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            if target_type == "input":
                await coordinator.async_send_cec_input(target_num, command)
            else:
                await coordinator.async_send_cec_output(target_num, command)

    async def handle_copy_edid(call: ServiceCall) -> None:
        """Handle copy_edid service."""
        device_id = call.data["device_id"]
        input_num = int(call.data["input"])
        output_num = int(call.data["output"])
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_copy_edid(input_num, output_num)

    async def handle_set_logo(call: ServiceCall) -> None:
        """Handle set_logo service."""
        device_id = call.data["device_id"]
        text = call.data["text"]
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_set_logo(text)

    # Register services
    hass.services.async_register(
        DOMAIN,
        SERVICE_SEND_COMMAND,
        handle_send_command,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("command"): str,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ROUTING,
        handle_set_routing,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("output"): vol.All(vol.Coerce(int), vol.Range(min=1, max=NUM_OUTPUTS)),
                vol.Required("input"): vol.All(vol.Coerce(int), vol.Range(min=1, max=NUM_INPUTS)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_ALL_ROUTING,
        handle_set_all_routing,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("input"): vol.All(vol.Coerce(int), vol.Range(min=1, max=NUM_INPUTS)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SAVE_PRESET,
        handle_save_preset,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("preset"): vol.All(vol.Coerce(int), vol.Range(min=1, max=NUM_PRESETS)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_RECALL_PRESET,
        handle_recall_preset,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("preset"): vol.All(vol.Coerce(int), vol.Range(min=1, max=NUM_PRESETS)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_PRESET,
        handle_clear_preset,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("preset"): vol.All(vol.Coerce(int), vol.Range(min=1, max=NUM_PRESETS)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_CEC_COMMAND,
        handle_cec_command,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("target_type"): vol.In(["input", "output"]),
                vol.Required("target_number"): vol.All(vol.Coerce(int), vol.Range(min=0, max=8)),
                vol.Required("command"): str,
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_COPY_EDID,
        handle_copy_edid,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("input"): vol.All(vol.Coerce(int), vol.Range(min=0, max=NUM_INPUTS)),
                vol.Required("output"): vol.All(vol.Coerce(int), vol.Range(min=1, max=4)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_LOGO,
        handle_set_logo,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("text"): vol.All(str, vol.Length(max=16)),
            }
        ),
    )

    async def handle_set_input_name(call: ServiceCall) -> None:
        """Handle set_input_name service."""
        device_id = call.data["device_id"]
        index = int(call.data["input"])
        name = call.data["name"]
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_set_input_name(index, name)

    async def handle_set_output_name(call: ServiceCall) -> None:
        """Handle set_output_name service."""
        device_id = call.data["device_id"]
        index = int(call.data["output"])
        name = call.data["name"]
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_set_output_name(index, name)

    async def handle_refresh_names(call: ServiceCall) -> None:
        """Handle refresh_names service."""
        device_id = call.data["device_id"]
        
        coordinator = await _get_coordinator_from_device_id(hass, device_id)
        if coordinator:
            await coordinator.async_fetch_names()

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_INPUT_NAME,
        handle_set_input_name,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("input"): vol.All(vol.Coerce(int), vol.Range(min=1, max=NUM_INPUTS)),
                vol.Required("name"): vol.All(str, vol.Length(max=32)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_OUTPUT_NAME,
        handle_set_output_name,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
                vol.Required("output"): vol.All(vol.Coerce(int), vol.Range(min=1, max=NUM_OUTPUTS)),
                vol.Required("name"): vol.All(str, vol.Length(max=32)),
            }
        ),
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_NAMES,
        handle_refresh_names,
        schema=vol.Schema(
            {
                vol.Required("device_id"): str,
            }
        ),
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services."""
    services = [
        SERVICE_SEND_COMMAND,
        SERVICE_SET_ROUTING,
        SERVICE_SET_ALL_ROUTING,
        SERVICE_SAVE_PRESET,
        SERVICE_RECALL_PRESET,
        SERVICE_CLEAR_PRESET,
        SERVICE_CEC_COMMAND,
        SERVICE_COPY_EDID,
        SERVICE_SET_LOGO,
        SERVICE_SET_INPUT_NAME,
        SERVICE_SET_OUTPUT_NAME,
        SERVICE_REFRESH_NAMES,
    ]
    for service in services:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)


async def _get_coordinator_from_device_id(
    hass: HomeAssistant, device_id: str
) -> OreiMatrixCoordinator | None:
    """Get coordinator from device ID."""
    device_registry = dr.async_get(hass)
    device = device_registry.async_get(device_id)
    
    if device is None:
        _LOGGER.error("Device not found: %s", device_id)
        return None

    for identifier in device.identifiers:
        if identifier[0] == DOMAIN:
            entry_id = identifier[1]
            if entry_id in hass.data.get(DOMAIN, {}):
                return hass.data[DOMAIN][entry_id]
    
    _LOGGER.error("Coordinator not found for device: %s", device_id)
    return None
