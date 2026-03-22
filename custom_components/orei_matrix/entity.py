"""Base entity for Orei HDMI Matrix."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OreiMatrixCoordinator


class OreiMatrixEntity(CoordinatorEntity[OreiMatrixCoordinator]):
    """Base entity for Orei HDMI Matrix."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        unique_id_suffix: str,
        name: str | None = None,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id_suffix}"
        # Only set _attr_name if provided - subclasses can use name property instead
        if name is not None:
            self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=coordinator.config_entry.title,
            manufacturer="Orei",
            model=coordinator.device_info.get("model", "BK-808 HDMI Matrix"),
            sw_version=coordinator.device_info.get("firmware_version"),
            configuration_url=f"http://{coordinator.api.host}",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.available and super().available


class OreiMatrixInputEntity(OreiMatrixEntity):
    """Base entity for input-specific entities.
    
    Entity IDs are based on numbers (e.g., input_1_status) for stability.
    Friendly names in the UI use custom port names dynamically.
    """

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        input_num: int,
        unique_id_suffix: str,
        name_suffix: str,
    ) -> None:
        """Initialize the input entity."""
        # Don't pass name to parent - we use the name property for dynamic names
        super().__init__(
            coordinator,
            f"input_{input_num}_{unique_id_suffix}",
            name=None,  # Use name property instead
        )
        self._input_num = input_num
        self._name_suffix = name_suffix

    @property
    def name(self) -> str:
        """Return the display name using custom port name.
        
        This is called dynamically, so names update when HTTP sync runs.
        """
        port_name = self.coordinator.get_input_name(self._input_num)
        return f"{port_name} {self._name_suffix}"


class OreiMatrixOutputEntity(OreiMatrixEntity):
    """Base entity for output-specific entities.
    
    Entity IDs are based on numbers (e.g., output_1_routing) for stability.
    Friendly names in the UI use custom port names dynamically.
    """

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
        unique_id_suffix: str,
        name_suffix: str,
    ) -> None:
        """Initialize the output entity."""
        # Don't pass name to parent - we use the name property for dynamic names
        super().__init__(
            coordinator,
            f"output_{output_num}_{unique_id_suffix}",
            name=None,  # Use name property instead
        )
        self._output_num = output_num
        self._name_suffix = name_suffix

    @property
    def name(self) -> str:
        """Return the display name using custom port name.
        
        This is called dynamically, so names update when HTTP sync runs.
        """
        port_name = self.coordinator.get_output_name(self._output_num)
        return f"{port_name} {self._name_suffix}"
