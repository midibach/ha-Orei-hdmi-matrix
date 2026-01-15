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
        name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{unique_id_suffix}"
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
    """Base entity for input-specific entities."""

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        input_num: int,
        unique_id_suffix: str,
        name: str,
    ) -> None:
        """Initialize the input entity."""
        super().__init__(
            coordinator,
            f"input_{input_num}_{unique_id_suffix}",
            f"Input {input_num} {name}",
        )
        self._input_num = input_num


class OreiMatrixOutputEntity(OreiMatrixEntity):
    """Base entity for output-specific entities."""

    def __init__(
        self,
        coordinator: OreiMatrixCoordinator,
        output_num: int,
        unique_id_suffix: str,
        name: str,
    ) -> None:
        """Initialize the output entity."""
        super().__init__(
            coordinator,
            f"output_{output_num}_{unique_id_suffix}",
            f"Output {output_num} {name}",
        )
        self._output_num = output_num
