"""The Garden Irrigation integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall

from .const import DOMAIN, PLATFORMS, SERVICE_STOP_ALL
from .coordinator import IrrigationController

_LOGGER = logging.getLogger(__name__)

type GardenIrrigationConfigEntry = ConfigEntry[IrrigationController]


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
