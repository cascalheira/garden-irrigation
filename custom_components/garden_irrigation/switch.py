"""Switch platform: one toggle per zone for manual start/stop."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GardenIrrigationConfigEntry
from .const import (
    ATTR_DURATION,
    DOMAIN,
    MAX_DURATION,
    MIN_DURATION,
    SERVICE_START,
    SERVICE_STOP,
    SIGNAL_UPDATE,
    SUBENTRY_TYPE_ZONE,
)
from .coordinator import IrrigationController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenIrrigationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a switch entity for each configured zone subentry."""
    controller = entry.runtime_data

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            continue
        async_add_entities(
            [ZoneSwitch(controller, subentry_id)],
            config_subentry_id=subentry_id,
        )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_START,
        {
            vol.Optional(ATTR_DURATION): vol.All(
                vol.Coerce(int), vol.Range(min=MIN_DURATION, max=MAX_DURATION)
            )
        },
        "async_start_service",
    )
    platform.async_register_entity_service(SERVICE_STOP, {}, "async_stop_service")


class ZoneSwitch(SwitchEntity):
    """A switch that starts/stops watering for one zone."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_icon = "mdi:sprinkler-variant"

    def __init__(self, controller: IrrigationController, subentry_id: str) -> None:
        self._controller = controller
        self._zone_id = subentry_id
        self._attr_unique_id = subentry_id
        zone = controller.get_zone(subentry_id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, subentry_id)},
            name=zone.name if zone else "Zone",
            manufacturer="Garden Irrigation",
            model="Irrigation zone",
        )

    @property
    def available(self) -> bool:
        return self._controller.get_zone(self._zone_id) is not None

    @property
    def is_on(self) -> bool:
        return self._controller.is_running(self._zone_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        zone = self._controller.get_zone(self._zone_id)
        ends_at = self._controller.ends_at(self._zone_id)
        next_run = self._controller.next_run(self._zone_id)
        attrs: dict[str, Any] = {
            "mode": self._controller.mode,
            "chain_running": self._controller.chain_running(),
        }
        if zone is not None:
            attrs["duration_minutes"] = zone.duration
            attrs["switch_entity"] = zone.switch_entity
            attrs["schedules"] = zone.schedules
        if ends_at is not None:
            attrs["ends_at"] = ends_at.isoformat()
            attrs["remaining_seconds"] = self._controller.remaining_seconds(
                self._zone_id
            )
            attrs["run_source"] = self._controller.run_source(self._zone_id)
        if next_run is not None:
            attrs["next_run"] = next_run.isoformat()
        return attrs

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._controller.async_start_zone(self._zone_id)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._controller.async_stop_zone(self._zone_id)

    async def async_start_service(self, duration: int | None = None) -> None:
        """Entity service: start with an optional duration override (minutes)."""
        await self._controller.async_start_zone(self._zone_id, duration)

    async def async_stop_service(self) -> None:
        """Entity service: stop this zone."""
        await self._controller.async_stop_zone(self._zone_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_UPDATE}_{self._controller.entry.entry_id}",
                self._handle_update,
            )
        )

    @callback
    def _handle_update(self) -> None:
        self.async_write_ha_state()
