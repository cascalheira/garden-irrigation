"""The Garden Irrigation integration."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.typing import ConfigType
from homeassistant.loader import async_get_integration

from .const import DOMAIN, PLATFORMS, SERVICE_STOP_ALL
from .coordinator import IrrigationController
from .websocket_api import async_register_websocket_commands

_LOGGER = logging.getLogger(__name__)

type GardenIrrigationConfigEntry = ConfigEntry[IrrigationController]

CARD_URL = "/garden_irrigation/garden-irrigation-card.js"
CARD_FILENAME = "garden-irrigation-card.js"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register websocket commands and serve the Lovelace card."""
    async_register_websocket_commands(hass)
    await _async_register_card(hass)
    return True


async def _async_register_card(hass: HomeAssistant) -> None:
    """Serve the card JS and register it as a frontend module."""
    card_path = Path(__file__).parent / "www" / CARD_FILENAME
    try:
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(card_path), cache_headers=False)]
        )
    except RuntimeError:
        # Already registered (e.g. integration reloaded without a restart).
        _LOGGER.debug("Static path %s already registered", CARD_URL)

    # Cache-bust the module URL by integration version so updates aren't stale.
    integration = await async_get_integration(hass, DOMAIN)
    versioned_url = f"{CARD_URL}?v={integration.version}"

    # Auto-load the card so users don't have to add a Lovelace resource manually.
    try:
        from homeassistant.components.frontend import add_extra_js_url

        add_extra_js_url(hass, versioned_url)
        _LOGGER.debug("Registered Lovelace card module at %s", versioned_url)
    except ImportError:  # frontend not available (e.g. minimal install)
        _LOGGER.debug("Frontend not available; add %s as a resource manually", CARD_URL)


async def async_setup_entry(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> bool:
    """Set up Garden Irrigation from a config entry."""
    controller = IrrigationController(hass, entry)
    await controller.async_setup()
    entry.runtime_data = controller

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _async_register_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_shutdown()
        if not _has_other_entries(hass, entry):
            hass.services.async_remove(DOMAIN, SERVICE_STOP_ALL)
    return unloaded


async def _async_update_listener(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> None:
    """Reload the entry when options or zones (subentries) change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _has_other_entries(
    hass: HomeAssistant, entry: GardenIrrigationConfigEntry
) -> bool:
    """Return True if another loaded entry of this integration exists."""
    return any(
        other.entry_id != entry.entry_id
        for other in hass.config_entries.async_loaded_entries(DOMAIN)
    )


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration-level services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_STOP_ALL):
        return

    async def _handle_stop_all(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_loaded_entries(DOMAIN):
            await entry.runtime_data.async_stop_all()

    hass.services.async_register(DOMAIN, SERVICE_STOP_ALL, _handle_stop_all)
