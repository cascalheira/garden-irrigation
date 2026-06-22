"""Sensor platform: remaining watering time per zone."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GardenIrrigationConfigEntry
from .const import DOMAIN, SIGNAL_UPDATE, SUBENTRY_TYPE_ZONE
from .coordinator import IrrigationController


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GardenIrrigationConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a remaining-time sensor for each configured zone subentry."""
    controller = entry.runtime_data

    for subentry_id, subentry in entry.subentries.items():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            continue
        async_add_entities(
            [ZoneRemainingSensor(controller, subentry_id)],
            config_subentry_id=subentry_id,
        )


class ZoneRemainingSensor(SensorEntity):
    """Reports how many seconds remain in the current run (0 when idle)."""

    _attr_has_entity_name = True
    _attr_translation_key = "remaining"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, controller: IrrigationController, subentry_id: str) -> None:
        self._controller = controller
        self._zone_id = subentry_id
        self._attr_unique_id = f"{subentry_id}_remaining"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, subentry_id)})

    @property
    def available(self) -> bool:
        return self._controller.get_zone(self._zone_id) is not None

    @property
    def native_value(self) -> int:
        return self._controller.remaining_seconds(self._zone_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        next_run = self._controller.next_run(self._zone_id)
        return {"next_run": next_run.isoformat() if next_run else None}

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
