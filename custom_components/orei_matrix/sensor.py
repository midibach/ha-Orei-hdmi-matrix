"""Sensor platform for Orei HDMI Matrix."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NUM_INPUTS, NUM_OUTPUTS
from .coordinator import OreiMatrixCoordinator
from .entity import OreiMatrixEntity, OreiMatrixInputEntity, OreiMatrixOutputEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Orei Matrix sensor entities."""
    coordinator: OreiMatrixCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: list[SensorEntity] = []

    # Device info sensors
    entities.append(OreiMatrixModelSensor(coordinator))
    entities.append(OreiMatrixFirmwareSensor(coordinator))
    entities.append(OreiMatrixMacAddressSensor(coordinator))
    entities.append(OreiMatrixIpAddressSensor(coordinator))

    # Input connection status sensors
    for input_num in range(1, NUM_INPUTS + 1):
        entities.append(OreiMatrixInputStatusSensor(coordinator, input_num))

    # Output connection status sensors
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputStatusSensor(coordinator, output_num))

    # Output current source sensors
    for output_num in range(1, NUM_OUTPUTS + 1):
        entities.append(OreiMatrixOutputSourceSensor(coordinator, output_num))

    async_add_entities(entities)


class OreiMatrixModelSensor(OreiMatrixEntity, SensorEntity):
    """Model sensor for Orei HDMI Matrix."""

    _attr_icon = "mdi:information"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: OreiMatrixCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "model", "Model")

    @property
    def native_value(self) -> str | None:
        """Return the model."""
        return self.coordinator.device_info.get("model")


class OreiMatrixFirmwareSensor(OreiMatrixEntity, SensorEntity):
    """Firmware version sensor for Orei HDMI Matrix."""

    _attr_icon = "mdi:chip"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: OreiMatrixCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "firmware", "Firmware Version")

    @property
    def native_value(self) -> str | None:
        """Return the firmware version."""
        return self.coordinator.device_info.get("firmware_version")


class OreiMatrixMacAddressSensor(OreiMatrixEntity, SensorEntity):
    """MAC address sensor for Orei HDMI Matrix."""

    _attr_icon = "mdi:network"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: OreiMatrixCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "mac_address", "MAC Address")

    @property
    def native_value(self) -> str | None:
        """Return the MAC address."""
        return self.coordinator.device_info.get("mac_address")


class OreiMatrixIpAddressSensor(OreiMatrixEntity, SensorEntity):
    """IP address sensor for Orei HDMI Matrix."""

    _attr_icon = "mdi:ip-network"
    _attr_entity_registry_enabled_default = False

    def __init__(self, coordinator: OreiMatrixCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "ip_address", "IP Address")

    @property
    def native_value(self) -> str | None:
        """Return the IP address."""
        ip_config = self.coordinator.device_info.get("ip_config", {})
        return ip_config.get("ip_address") or self.coordinator.api.host


class OreiMatrixInputStatusSensor(OreiMatrixInputEntity, SensorEntity):
    """Input connection status sensor for Orei HDMI Matrix."""

    _attr_icon = "mdi:hdmi-port"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        input_num: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, input_num, "status", "Status")

    @property
    def native_value(self) -> str | None:
        """Return the connection status."""
        if self.coordinator.data is None:
            return None
        input_status = self.coordinator.data.get("input_status", {})
        return input_status.get(self._input_num, "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon based on status."""
        status = self.native_value
        if status and "connect" in status.lower():
            return "mdi:hdmi-port"
        return "mdi:hdmi-port"

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional attributes."""
        return {
            "input_number": self._input_num,
        }


class OreiMatrixOutputStatusSensor(OreiMatrixOutputEntity, SensorEntity):
    """Output connection status sensor for Orei HDMI Matrix."""

    _attr_icon = "mdi:television"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, output_num, "status", "Status")

    @property
    def native_value(self) -> str | None:
        """Return the connection status."""
        if self.coordinator.data is None:
            return None
        output_status = self.coordinator.data.get("output_status", {})
        return output_status.get(self._output_num, "Unknown")

    @property
    def icon(self) -> str:
        """Return the icon based on status."""
        status = self.native_value
        if status and "connect" in status.lower():
            return "mdi:television"
        return "mdi:television-off"

    @property
    def extra_state_attributes(self) -> dict[str, str] | None:
        """Return additional attributes."""
        return {
            "output_number": self._output_num,
        }


class OreiMatrixOutputSourceSensor(OreiMatrixOutputEntity, SensorEntity):
    """Output current source sensor for Orei HDMI Matrix."""

    _attr_icon = "mdi:video-input-hdmi"

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, output_num, "current_source", "Current Source")

    @property
    def native_value(self) -> str | None:
        """Return the current source."""
        if self.coordinator.data is None:
            return None
        routing = self.coordinator.data.get("routing", {})
        input_num = routing.get(self._output_num)
        if input_num:
            return f"Input {input_num}"
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | None] | None:
        """Return additional attributes."""
        if self.coordinator.data is None:
            return None
        routing = self.coordinator.data.get("routing", {})
        input_num = routing.get(self._output_num)
        return {
            "output_number": self._output_num,
            "input_number": input_num,
        }
