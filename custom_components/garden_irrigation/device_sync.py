"""Keep offline-capable relay controllers (relay6 ESPHome-API firmware) in sync.

Zones whose switch belongs to an ESPHome device exposing a ``set_schedule`` action get their
weekly plan pushed to that device, so watering continues if Home Assistant is down. One
publisher serves all setups: plans from every loaded config entry are merged per device.

Republished (debounced) on: any setup reload (which every options/zone change causes), entry
unload, Home Assistant start, the device's ``set_schedule`` action appearing (device connected),
and a mapped relay switch coming back from ``unavailable`` (device rebooted).
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, timezone
from typing import Any

from homeassistant.const import (
    EVENT_HOMEASSISTANT_STARTED,
    EVENT_SERVICE_REGISTERED,
    STATE_UNAVAILABLE,
)
from homeassistant.core import CALLBACK_TYPE, Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_call_later, async_track_state_change_event

from .const import DOMAIN, MODE_SEQUENTIAL
from .plan import DevicePlan, ZonePlan, build_setup_plans

_LOGGER = logging.getLogger(__name__)

ESPHOME_DOMAIN = "esphome"
SERVICE_SET_SCHEDULE = "set_schedule"
SERVICE_CLEAR_SCHEDULE = "clear_schedule"
DEBOUNCE_SECONDS = 5.0
DATA_KEY = f"{DOMAIN}_device_sync"

# Relay channel from an ESPHome entity unique_id, which ends in the object id ("relay_3") or the
# entity name ("Relay 3"), optionally followed by "@<device_id>" for sub-devices.
_RELAY_RE = re.compile(r"relay[ _-]?(\d+)(?:@.*)?$", re.IGNORECASE)
_MAX_ON_RE_TMPL = r"relay[ _-]?{ch}[ _-]?max[ _-]?on"


def get_device_sync(hass: HomeAssistant) -> DeviceSync:
    """Return the per-hass singleton, creating it on first use."""
    sync = hass.data.get(DATA_KEY)
    if sync is None:
        sync = DeviceSync(hass)
        hass.data[DATA_KEY] = sync
    return sync


class DeviceSync:
    """Merges plans from all setups and pushes them to the relay devices."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._debounce: CALLBACK_TYPE | None = None
        self._unsub_states: CALLBACK_TYPE | None = None
        self._known_devices: set[str] = set()
        self._lock = asyncio.Lock()
        # node -> {"status": human readable, "at": ISO timestamp of the attempt}
        self.last_result: dict[str, dict[str, str]] = {}
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, self._on_started)
        hass.bus.async_listen(EVENT_SERVICE_REGISTERED, self._on_service_registered)

    # ----- triggers -------------------------------------------------------------------------

    @callback
    def schedule(self, delay: float = DEBOUNCE_SECONDS) -> None:
        """Publish soon; repeated calls within the window collapse into one."""
        if self._debounce:
            self._debounce()
        self._debounce = async_call_later(self.hass, delay, self._debounced)

    @callback
    def _debounced(self, _now: Any) -> None:
        self._debounce = None
        self.hass.async_create_task(self.async_publish())

    @callback
    def _on_started(self, _event: Event) -> None:
        self.schedule(10)

    @callback
    def _on_service_registered(self, event: Event) -> None:
        if event.data.get("domain") == ESPHOME_DOMAIN and str(event.data.get("service", "")).endswith(
            f"_{SERVICE_SET_SCHEDULE}"
        ):
            self.schedule()

    @callback
    def _on_relay_state(self, event: Event) -> None:
        old = event.data.get("old_state")
        new = event.data.get("new_state")
        if old is not None and new is not None and old.state == STATE_UNAVAILABLE and new.state != STATE_UNAVAILABLE:
            self.schedule()

    # ----- resolution -----------------------------------------------------------------------

    def resolve_relay(self, entity_id: str) -> tuple[str, int] | None:
        """Map a switch entity to (esphome node name, relay channel) if it is one of ours."""
        ent = er.async_get(self.hass).async_get(entity_id)
        if ent is None or ent.platform != ESPHOME_DOMAIN or not ent.device_id:
            return None
        match = _RELAY_RE.search(ent.unique_id or "")
        if not match:
            return None
        node = self._node_name(ent.device_id)
        return (node, int(match.group(1))) if node else None

    def _node_name(self, device_id: str) -> str | None:
        device = dr.async_get(self.hass).async_get(device_id)
        if device is None:
            return None
        for ce_id in device.config_entries:
            entry = self.hass.config_entries.async_get_entry(ce_id)
            if entry and entry.domain == ESPHOME_DOMAIN:
                return entry.data.get("device_name")
        return None

    def _max_on_entity(self, node: str, channel: int) -> str | None:
        """Find the device's per-relay max-on-time number entity."""
        pattern = re.compile(_MAX_ON_RE_TMPL.format(ch=channel), re.IGNORECASE)
        ent_reg = er.async_get(self.hass)
        for entry in self.hass.config_entries.async_entries(ESPHOME_DOMAIN):
            if entry.data.get("device_name") != node:
                continue
            for ent in er.async_entries_for_config_entry(ent_reg, entry.entry_id):
                if ent.domain == "number" and pattern.search(ent.unique_id or ""):
                    return ent.entity_id
        return None

    @staticmethod
    def service_name(node: str, service: str) -> str:
        return f"{node.replace('-', '_')}_{service}"

    # ----- publishing -----------------------------------------------------------------------

    def build_plans(self) -> tuple[dict[str, DevicePlan], set[str]]:
        """Merge every loaded setup into one plan per device. Also returns the relay entity ids."""
        merged: dict[str, DevicePlan] = {}
        relay_entities: set[str] = set()
        for entry in self.hass.config_entries.async_loaded_entries(DOMAIN):
            ctl = getattr(entry, "runtime_data", None)
            if ctl is None:
                continue
            zones: list[ZonePlan] = []
            for zone in ctl.zones.values():
                relay = self.resolve_relay(zone.switch_entity)
                if relay:
                    relay_entities.add(zone.switch_entity)
                zones.append(
                    ZonePlan(
                        name=zone.name,
                        minutes=ctl.effective_minutes(zone),
                        cycles=zone.cycles,
                        soak=zone.soak,
                        enabled=zone.enabled,
                        schedules=list(zone.schedules),
                        relay=relay,
                    )
                )
            master = self.resolve_relay(ctl.master_entity) if ctl.master_entity else None
            if master:
                relay_entities.add(ctl.master_entity)
            plans = build_setup_plans(
                mode=ctl.mode,
                enabled=ctl.enabled,
                start_schedules=ctl.start_schedules if ctl.mode == MODE_SEQUENTIAL else [],
                zones=zones,
                master=master,
            )
            for node, plan in plans.items():
                merged.setdefault(node, DevicePlan()).merge(plan)
            # Devices referenced only by disabled/empty setups still need clearing.
            for z in zones:
                if z.relay:
                    merged.setdefault(z.relay[0], DevicePlan())
            if master:
                merged.setdefault(master[0], DevicePlan())
        return merged, relay_entities

    async def async_publish(self) -> None:
        """Push the merged plans to every device that is currently reachable."""
        async with self._lock:
            plans, relay_entities = self.build_plans()
            self._track(relay_entities)
            targets = set(plans) | self._known_devices
            rev = int(time.time())
            for node in sorted(targets):
                plan = plans.get(node, DevicePlan())
                await self._push(node, plan, rev)
            self._known_devices = set(plans)

    def _record(self, node: str, status: str) -> None:
        self.last_result[node] = {"status": status, "at": datetime.now(timezone.utc).isoformat()}

    def status_for(self, nodes: set[str]) -> list[dict[str, str]]:
        """Sync status entries for the card, for the given device nodes."""
        return [
            {"node": node, **self.last_result.get(node, {"status": "pending", "at": ""})}
            for node in sorted(nodes)
        ]

    async def _push(self, node: str, plan: DevicePlan, rev: int) -> None:
        set_svc = self.service_name(node, SERVICE_SET_SCHEDULE)
        clear_svc = self.service_name(node, SERVICE_CLEAR_SCHEDULE)
        if not self.hass.services.has_service(ESPHOME_DOMAIN, set_svc):
            self._record(node, "device offline")
            _LOGGER.debug("Relay device %s not connected; plan will be sent when it appears", node)
            return
        try:
            if plan.block_count() == 0:
                if self.hass.services.has_service(ESPHOME_DOMAIN, clear_svc):
                    await self.hass.services.async_call(ESPHOME_DOMAIN, clear_svc, {}, blocking=True)
                self._record(node, "cleared")
                _LOGGER.info("Cleared offline schedule on %s", node)
            else:
                import json

                payload = json.dumps(plan.payload(rev), separators=(",", ":"))
                await self.hass.services.async_call(
                    ESPHOME_DOMAIN, set_svc, {"json": payload}, blocking=True
                )
                self._record(node, f"rev {rev & 0xFFFFFFFF}, {plan.block_count()} blocks")
                _LOGGER.info(
                    "Sent offline schedule rev %s to %s: %s blocks on relays %s",
                    rev & 0xFFFFFFFF,
                    node,
                    plan.block_count(),
                    sorted(plan.channels),
                )
            for channel, minutes in plan.safeguards().items():
                entity_id = self._max_on_entity(node, channel)
                if entity_id:
                    await self.hass.services.async_call(
                        "number", "set_value", {"entity_id": entity_id, "value": minutes}, blocking=True
                    )
        except Exception as err:  # noqa: BLE001 - never let a device hiccup break a reload
            self._record(node, f"error: {err}")
            _LOGGER.warning("Could not sync offline schedule to %s: %s", node, err)

    @callback
    def _track(self, relay_entities: set[str]) -> None:
        if self._unsub_states:
            self._unsub_states()
            self._unsub_states = None
        if relay_entities:
            self._unsub_states = async_track_state_change_event(
                self.hass, sorted(relay_entities), self._on_relay_state
            )
