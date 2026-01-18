"""Config flow for Orei HDMI Matrix integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .api import OreiMatrixAPI, OreiMatrixConnectionError, OreiMatrixError
from .const import (
    CONF_PASSWORD,
    CONF_SYNC_NAMES,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def validate_connection(
    hass: HomeAssistant, host: str, port: int, password: str | None = None
) -> dict[str, Any]:
    """Validate the connection to the matrix."""
    api = OreiMatrixAPI(host, port, password=password)
    
    try:
        await api.connect()
        model = await api.get_model()
        
        # Try to get names to verify HTTP API access
        names_available = False
        try:
            input_names = await api.get_input_names()
            if input_names and input_names[0] != "Input1":
                names_available = True
            else:
                names_available = True  # API works even if default names
        except Exception:
            names_available = False
        
        await api.disconnect()
        return {"model": model, "names_available": names_available}
    except OreiMatrixConnectionError as err:
        raise ConnectionError(str(err)) from err
    except OreiMatrixError as err:
        raise ConnectionError(str(err)) from err
    finally:
        await api.disconnect()


class OreiMatrixConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Orei HDMI Matrix."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None
        self._port: int = DEFAULT_PORT
        self._name: str | None = None
        self._password: str | None = None
        self._model: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._port = int(user_input.get(CONF_PORT, DEFAULT_PORT))
            self._name = user_input.get(CONF_NAME)
            self._password = user_input.get(CONF_PASSWORD) or ""

            try:
                info = await validate_connection(
                    self.hass, self._host, self._port, self._password
                )
                self._model = info.get("model", "Orei Matrix")
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:  # noqa: BLE001
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Check if already configured
                await self.async_set_unique_id(f"{self._host}:{self._port}")
                self._abort_if_unique_id_configured()

                name = self._name or f"Orei Matrix ({self._host})"
                
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: self._host,
                        CONF_PORT: self._port,
                        CONF_PASSWORD: self._password,
                    },
                    options={
                        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
                        CONF_SYNC_NAMES: True,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    vol.Optional(CONF_PORT, default=DEFAULT_PORT): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=1,
                            max=65535,
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                    vol.Optional(CONF_NAME): selector.TextSelector(
                        selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
                    ),
                    vol.Optional(CONF_PASSWORD, default=""): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD
                        )
                    ),
                }
            ),
            errors=errors,
            description_placeholders={
                "default_port": str(DEFAULT_PORT),
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> OreiMatrixOptionsFlowHandler:
        """Get the options flow for this handler."""
        return OreiMatrixOptionsFlowHandler(config_entry)


class OreiMatrixOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Orei HDMI Matrix."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        current_sync_names = self.config_entry.options.get(CONF_SYNC_NAMES, True)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current_interval,
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=MIN_SCAN_INTERVAL,
                            max=MAX_SCAN_INTERVAL,
                            step=1,
                            mode=selector.NumberSelectorMode.SLIDER,
                            unit_of_measurement="seconds",
                        )
                    ),
                    vol.Optional(
                        CONF_SYNC_NAMES,
                        default=current_sync_names,
                    ): selector.BooleanSelector(),
                }
            ),
            description_placeholders={
                "min_interval": str(MIN_SCAN_INTERVAL),
                "max_interval": str(MAX_SCAN_INTERVAL),
                "default_interval": str(DEFAULT_SCAN_INTERVAL),
            },
        )
