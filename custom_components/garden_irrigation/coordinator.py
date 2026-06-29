"""Runtime controller for one irrigation setup (config entry).

A setup runs in one of two scheduling modes:

* ``sequential`` — the setup has a single start time; all zones run back-to-back
  in subentry order. The whole chain is one cancellable task.
* ``specific`` — each zone has its own schedule(s) and runs independently
  (zones may overlap, which raises a discreet repair issue).

Manual start/stop of an individual zone works in both modes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import partial
from typing import Any, Callable

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import (
    async_call_later,
    async_track_state_change_event,
    async_track_time_change,
)
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    CONF_CYCLES,
    CONF_DAYS,
    CONF_DURATION,
    CONF_ENABLED,
    CONF_FLOW_ENABLED,
    CONF_FLOW_ENTITY,
    CONF_FLOW_MIN,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_ENTITY,
    CONF_FORECAST_HOURS,
    CONF_FORECAST_THRESHOLD,
    CONF_FREEZE_ENABLED,
    CONF_FREEZE_ENTITY,
    CONF_FREEZE_THRESHOLD,
    CONF_MASTER_ENTITY,
    CONF_MASTER_LEAD,
    CONF_MODE,
    CONF_NAME,
    CONF_NOTIFY_FLOW,
    CONF_NOTIFY_OFF_FAILED,
    CONF_NOTIFY_SKIP,
    CONF_NOTIFY_START_FAILED,
    CONF_NOTIFY_TARGET,
    CONF_NOTIFY_TARGETS,
    CONF_POST_SCRIPT,
    CONF_PRE_SCRIPT,
    CONF_RAIN_ENABLED,
    CONF_RAIN_ENTITY,
    CONF_RAIN_HOURS,
    CONF_RAIN_THRESHOLD,
    CONF_SCHEDULES,
    CONF_SEASONAL_ADJUST,
    CONF_SOAK,
    CONF_SOIL_ENABLED,
    CONF_SOIL_ENTITY,
    CONF_SOIL_THRESHOLD,
    CONF_START_TIME,
    CONF_START_TIMES,
    CONF_SWITCH_ENTITY,
    CONF_TIME,
    DEFAULT_CYCLES,
    DEFAULT_DURATION,
    DEFAULT_FLOW_MIN,
    DEFAULT_FORECAST_HOURS,
    DEFAULT_FORECAST_THRESHOLD,
    DEFAULT_FREEZE_THRESHOLD,
    DEFAULT_MASTER_LEAD,
    DEFAULT_MODE,
    DEFAULT_RAIN_HOURS,
    DEFAULT_RAIN_THRESHOLD,
    DEFAULT_SEASONAL_ADJUST,
    DEFAULT_SOAK,
    DEFAULT_SOIL_THRESHOLD,
    DOMAIN,
    EVENT_SKIPPED,
    ISSUE_COLLISION,
    ISSUE_OVERLAP,
    MODE_SEQUENTIAL,
    SIGNAL_UPDATE,
    SKIP_FORECAST,
    SKIP_FREEZE,
    SKIP_RAIN_DELAY,
    SKIP_RECENT,
    SKIP_SOIL,
    STATE_RAIN_DELAY_UNTIL,
    SUBENTRY_TYPE_ZONE,
    WEEKDAYS,
)
from .util import (
    compute_next_run,
    compute_overlaps,
    compute_start_collisions,
    parse_time,
)

_LOGGER = logging.getLogger(__name__)

# Reliable turn-off: verify the switch reported off, retry if not.
OFF_MAX_ATTEMPTS = 5
OFF_SETTLE = 1.0  # seconds to let the state settle before checking
OFF_RETRY_DELAY = 3.0  # seconds between retry attempts

# History log
HISTORY_VERSION = 1
MAX_HISTORY = 1000
MAX_HISTORY_DAYS = 365

# Persisted runtime state (rain delay) and per-zone totals
STATE_VERSION = 1
TOTALS_VERSION = 1

# Flow / leak monitoring
FLOW_SETTLE = 30.0  # seconds after a valve opens before checking for flow
FLOW_LEAK_SECONDS = 120.0  # sustained idle flow before a leak is reported


@dataclass
class Zone:
    """A resolved irrigation zone, built from a config subentry."""

    id: str
    name: str
    switch_entity: str
    duration: int  # minutes
    schedules: list[dict[str, Any]] = field(default_factory=list)
    pre_script: str | None = None
    post_script: str | None = None
    enabled: bool = True
    cycles: int = 1  # number of on-cycles per run (1 = continuous)
    soak: int = 0  # soak minutes between cycles


@dataclass
class RunState:
    """Bookkeeping for a zone that is currently watering."""

    task: asyncio.Task  # the controlling task (chain task or single-run task)
    ends_at: datetime
    source: str  # "manual" or "scheduled"


def zone_from_subentry(subentry_id: str, data: dict[str, Any]) -> Zone:
    """Build a :class:`Zone` from stored subentry data."""
    return Zone(
        id=subentry_id,
        name=data[CONF_NAME],
        switch_entity=data[CONF_SWITCH_ENTITY],
        duration=int(data.get(CONF_DURATION, DEFAULT_DURATION)),
        schedules=list(data.get(CONF_SCHEDULES, [])),
        pre_script=data.get(CONF_PRE_SCRIPT) or None,
        post_script=data.get(CONF_POST_SCRIPT) or None,
        enabled=data.get(CONF_ENABLED, True),
        cycles=max(1, int(data.get(CONF_CYCLES, DEFAULT_CYCLES) or DEFAULT_CYCLES)),
        soak=max(0, int(data.get(CONF_SOAK, DEFAULT_SOAK) or DEFAULT_SOAK)),
    )


class IrrigationController:
    """Owns the scheduling and execution of one setup's zones."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._running: dict[str, RunState] = {}
        self._chain_task: asyncio.Task | None = None
        self._unsub_time: list[Callable[[], None]] = []
        self._last_skip: dict[str, Any] | None = None
        self._history: list[dict[str, Any]] = []
        self._store: Store = Store(
            hass, HISTORY_VERSION, f"{DOMAIN}_history_{entry.entry_id}"
        )
        # Master valve refcount: open while any zone is watering.
        self._master_lock = asyncio.Lock()
        self._master_users: set[str] = set()
        # Manual rain delay + per-zone cumulative totals (persisted).
        self._state_store: Store = Store(
            hass, STATE_VERSION, f"{DOMAIN}_state_{entry.entry_id}"
        )
        self._totals_store: Store = Store(
            hass, TOTALS_VERSION, f"{DOMAIN}_totals_{entry.entry_id}"
        )
        self._rain_delay_until: datetime | None = None
        self._totals: dict[str, float] = {}
        # Idle flow leak watchdog.
        self._unsub_flow: Callable[[], None] | None = None
        self._leak_timer: Callable[[], None] | None = None

    # ----- configuration helpers -------------------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether the setup is enabled (False = paused, no watering)."""
        return self.entry.options.get(CONF_ENABLED, True)

    @property
    def seasonal_adjust(self) -> int:
        """Percent applied to every zone's duration (100 = no change)."""
        return int(self.entry.options.get(CONF_SEASONAL_ADJUST, DEFAULT_SEASONAL_ADJUST))

    def effective_minutes(self, zone: Zone) -> int:
        """Zone duration after the seasonal adjustment (at least 1 minute)."""
        pct = self.seasonal_adjust
        if pct == 100:
            return zone.duration
        return max(1, round(zone.duration * pct / 100))

    @property
    def master_entity(self) -> str | None:
        """Optional master valve/pump opened while any zone in this setup runs."""
        return self.entry.options.get(CONF_MASTER_ENTITY) or None

    @property
    def master_lead(self) -> int:
        """Seconds to wait after opening the master valve before a zone opens."""
        return int(self.entry.options.get(CONF_MASTER_LEAD, DEFAULT_MASTER_LEAD) or 0)

    @property
    def flow_enabled(self) -> bool:
        return bool(
            self.entry.options.get(CONF_FLOW_ENABLED, False)
            and self.entry.options.get(CONF_FLOW_ENTITY)
        )

    @property
    def flow_entity(self) -> str | None:
        return self.entry.options.get(CONF_FLOW_ENTITY) or None

    @property
    def flow_min(self) -> float:
        return float(self.entry.options.get(CONF_FLOW_MIN, DEFAULT_FLOW_MIN))

    @property
    def mode(self) -> str:
        """Return the scheduling mode (sequential | specific)."""
        return self.entry.options.get(CONF_MODE, DEFAULT_MODE)

    @property
    def days(self) -> list[str]:
        """Return the days the sequential chain runs (legacy single-time setups)."""
        return self.entry.options.get(CONF_DAYS) or list(WEEKDAYS)

    @property
    def start_schedules(self) -> list[dict[str, Any]]:
        """Return the sequential start times as a list of {time, days}.

        Migrates a legacy single ``start_time``/``days`` option on read.
        """
        times = self.entry.options.get(CONF_START_TIMES)
        if times:
            return list(times)
        legacy = self.entry.options.get(CONF_START_TIME)
        if legacy:
            return [{CONF_TIME: legacy, CONF_DAYS: self.days}]
        return []

    @property
    def total_duration(self) -> int:
        """Total minutes the full sequence takes (sum of zone durations)."""
        return sum(z.duration for z in self.zones.values())

    @property
    def pre_script(self) -> str | None:
        """Sequential setup: script run once before the sequence starts."""
        return self.entry.options.get(CONF_PRE_SCRIPT) or None

    @property
    def post_script(self) -> str | None:
        """Sequential setup: script run once after the sequence ends."""
        return self.entry.options.get(CONF_POST_SCRIPT) or None

    @property
    def zones(self) -> dict[str, Zone]:
        """Return all configured zones, keyed by subentry id (in order)."""
        return {
            sid: zone_from_subentry(sid, dict(sub.data))
            for sid, sub in self.entry.subentries.items()
            if sub.subentry_type == SUBENTRY_TYPE_ZONE
        }

    def get_zone(self, zone_id: str) -> Zone | None:
        """Return a single zone or ``None``."""
        return self.zones.get(zone_id)

    # ----- lifecycle -------------------------------------------------------------

    async def async_setup(self) -> None:
        """Register schedule listeners and refresh derived state."""
        self._history = self._prune_history(await self._store.async_load() or [])
        state = await self._state_store.async_load() or {}
        raw = state.get(STATE_RAIN_DELAY_UNTIL)
        self._rain_delay_until = dt_util.parse_datetime(raw) if raw else None
        totals = await self._totals_store.async_load() or {}
        self._totals = {k: float(v) for k, v in totals.items()}
        self._register_schedules()
        self._register_flow_listener()
        self._update_overlap_issue()

    async def async_shutdown(self) -> None:
        """Cancel listeners and every running task."""
        for unsub in self._unsub_time:
            unsub()
        self._unsub_time.clear()
        if self._unsub_flow:
            self._unsub_flow()
            self._unsub_flow = None
        self._cancel_leak_timer()

        tasks = [s.task for s in self._running.values()]
        if self._chain_task:
            tasks.append(self._chain_task)
        for task in set(tasks):
            task.cancel()
        for task in set(tasks):
            with _suppress_cancelled():
                await task
        self._running.clear()
        self._chain_task = None
        # Persist any pending history/totals before the controller is replaced.
        await self._store.async_save(self._history)
        await self._totals_store.async_save(self._totals)

    @callback
    def _register_schedules(self) -> None:
        """(Re)register the time listeners appropriate to the current mode."""
        for unsub in self._unsub_time:
            unsub()
        self._unsub_time.clear()

        if self.mode == MODE_SEQUENTIAL:
            for sched in self.start_schedules:
                hour, minute = parse_time(sched[CONF_TIME])
                self._unsub_time.append(
                    async_track_time_change(
                        self.hass,
                        partial(self._sequential_trigger, sched),
                        hour=hour,
                        minute=minute,
                        second=0,
                    )
                )
            return

        for zone in self.zones.values():
            for sched in zone.schedules:
                hour, minute = parse_time(sched[CONF_TIME])
                self._unsub_time.append(
                    async_track_time_change(
                        self.hass,
                        partial(self._scheduled_trigger, zone.id, sched),
                        hour=hour,
                        minute=minute,
                        second=0,
                    )
                )

    @callback
    def _sequential_trigger(self, sched: dict[str, Any], now: datetime) -> None:
        """Fire at a setup start time; run the whole chain if today matches."""
        days = sched.get(CONF_DAYS) or WEEKDAYS
        weekday = WEEKDAYS[dt_util.as_local(now).weekday()]
        if weekday not in days:
            return
        self.hass.async_create_task(self._scheduled_chain())

    async def _scheduled_chain(self) -> None:
        if not self.enabled:
            return
        reason = await self.async_skip_reason()
        if reason:
            self._record_skip(reason)
            return
        self.async_run_chain()

    @callback
    def _scheduled_trigger(
        self, zone_id: str, sched: dict[str, Any], now: datetime
    ) -> None:
        """Fire when a zone schedule matches; start that zone independently."""
        days = sched.get(CONF_DAYS) or WEEKDAYS
        weekday = WEEKDAYS[dt_util.as_local(now).weekday()]
        if weekday not in days:
            return
        self.hass.async_create_task(self._scheduled_zone(zone_id))

    async def _scheduled_zone(self, zone_id: str) -> None:
        if not self.enabled:
            return
        zone = self.get_zone(zone_id)
        if zone is None or not zone.enabled:
            return
        reason = await self.async_skip_reason()
        if reason:
            self._record_skip(reason)
            return
        await self.async_start_zone(zone_id, source="scheduled")

    # ----- public control surface ------------------------------------------------

    async def async_start_zone(
        self, zone_id: str, duration: int | None = None, source: str = "manual"
    ) -> None:
        """Start a single zone now (independent of any chain).

        A manual start always runs, even if the zone is disabled — disabling only
        excludes a zone from *scheduled* runs (the scheduled paths check that
        before calling here).
        """
        zone = self.get_zone(zone_id)
        if zone is None:
            _LOGGER.warning("Cannot start unknown zone %s", zone_id)
            return
        if zone_id in self._running:
            return  # already watering

        # An explicit override runs as-is; the default applies seasonal adjust.
        minutes = duration if duration is not None else self.effective_minutes(zone)
        self.hass.async_create_task(
            self._run_single(zone, int(minutes) * 60, source),
            name=f"{DOMAIN}_{zone_id}",
        )

    @callback
    def async_run_chain(self) -> None:
        """Start the sequential chain (all enabled zones, in order)."""
        if not self.enabled:
            return
        if self._chain_task and not self._chain_task.done():
            return
        if not any(z.enabled for z in self.zones.values()):
            return
        self._chain_task = self.hass.async_create_task(
            self._run_chain(), name=f"{DOMAIN}_chain_{self.entry.entry_id}"
        )

    async def async_stop_zone(self, zone_id: str) -> None:
        """Stop a running zone. In a chain this stops the whole chain."""
        state = self._running.get(zone_id)
        if state is not None:
            state.task.cancel()
        self._notify()

    async def async_stop_all(self) -> None:
        """Stop the chain and every running zone in this setup."""
        if self._chain_task:
            self._chain_task.cancel()
        for state in list(self._running.values()):
            state.task.cancel()
        self._notify()

    # ----- introspection for entities / card -------------------------------------

    def is_running(self, zone_id: str) -> bool:
        return zone_id in self._running

    def chain_running(self) -> bool:
        return self._chain_task is not None and not self._chain_task.done()

    def ends_at(self, zone_id: str) -> datetime | None:
        state = self._running.get(zone_id)
        return state.ends_at if state else None

    def run_source(self, zone_id: str) -> str | None:
        state = self._running.get(zone_id)
        return state.source if state else None

    def remaining_seconds(self, zone_id: str) -> int:
        ends_at = self.ends_at(zone_id)
        if ends_at is None:
            return 0
        return max(0, int((ends_at - dt_util.utcnow()).total_seconds()))

    def next_run(self, zone_id: str) -> datetime | None:
        """Next scheduled start for a zone (uses setup start time in sequential)."""
        zone = self.get_zone(zone_id)
        if zone is None:
            return None
        if self.mode == MODE_SEQUENTIAL:
            schedules = self.start_schedules
        else:
            schedules = zone.schedules
        if not schedules:
            return None
        return compute_next_run(schedules, dt_util.now())

    # ----- execution -------------------------------------------------------------

    async def _run_chain(self) -> None:
        """Run every zone in order; cancellation stops the remaining zones.

        A setup-level pre-script runs once before the sequence and a post-script
        runs once after it (even if the sequence is stopped early).
        """
        _LOGGER.debug("Starting sequential chain for %s", self.entry.title)
        self._log("sequence")
        try:
            if self.pre_script:
                await self._run_script(self.pre_script)
            # Hold one master-valve lease for the whole sequence so it stays
            # open (and only adds its lead once) across all the zones.
            await self._acquire_master("chain")
            for zone in self.zones.values():
                if not zone.enabled:
                    continue
                await self._water(
                    zone, self.effective_minutes(zone) * 60, "scheduled"
                )
        except asyncio.CancelledError:
            _LOGGER.debug("Chain for %s stopped early", self.entry.title)
        finally:
            await asyncio.shield(self._release_master("chain"))
            if self.post_script:
                await asyncio.shield(self._run_script(self.post_script))

    async def _run_single(self, zone: Zone, seconds: int, source: str) -> None:
        try:
            await self._water(zone, seconds, source)
        except asyncio.CancelledError:
            pass

    async def _water(self, zone: Zone, seconds: int, source: str) -> None:
        """Water one zone: pre-script, master valve, on/soak cycles, off, post.

        Runs in the calling task (the chain task or a single-run task) so that
        cancelling that task stops watering. Cleanup is shielded so the valve is
        always closed even on cancellation. ``seconds`` is the total *watering*
        time, split across ``zone.cycles`` bursts with ``zone.soak`` gaps.
        """
        cycles = max(1, zone.cycles)
        soak = max(0, zone.soak) * 60
        on_each = max(1, seconds // cycles)
        wall = on_each * cycles + soak * (cycles - 1)

        task = asyncio.current_task()
        self._running[zone.id] = RunState(
            task=task,
            ends_at=dt_util.utcnow() + timedelta(seconds=wall),
            source=source,
        )
        self._notify()
        self._log(
            "start", zone=zone.name, source=source, minutes=round(seconds / 60)
        )
        stopped = False
        failed = False
        watered = 0
        try:
            if zone.pre_script:
                await self._run_script(zone.pre_script)
            await self._acquire_master(zone.id)
            for index in range(cycles):
                await self._set_switch(zone.switch_entity, True)
                self.hass.async_create_task(self._flow_watchdog(zone))
                await asyncio.sleep(on_each)
                watered += on_each
                if soak and index < cycles - 1:
                    await self._set_switch(zone.switch_entity, False)
                    await asyncio.sleep(soak)
        except asyncio.CancelledError:
            stopped = True
            raise
        except Exception as err:  # noqa: BLE001 — keep the run safe; log + notify
            failed = True
            _LOGGER.error("Zone %s failed to run: %s", zone.name, err)
        finally:
            await asyncio.shield(self._cleanup(zone, stopped, failed, watered))

    async def _cleanup(
        self, zone: Zone, stopped: bool, failed: bool, watered_seconds: int = 0
    ) -> None:
        try:
            closed = await self._async_ensure_off(zone.switch_entity)
            await self._release_master(zone.id)
            if zone.post_script:
                await self._run_script(zone.post_script)
        finally:
            self._running.pop(zone.id, None)
            self._notify()
        if watered_seconds > 0:
            self._add_total(zone.id, watered_seconds / 60.0)
        if not closed:
            self._log("error", zone=zone.name, detail="off_failed", level="error")
            await self._notify_failure(zone.name, "off_failed")
        elif failed:
            self._log("error", zone=zone.name, detail="start_failed", level="error")
            await self._notify_failure(zone.name, "start_failed")
        elif stopped:
            self._log("stop", zone=zone.name)
        else:
            self._log("finish", zone=zone.name)

    # ----- master valve / pump ---------------------------------------------------

    async def _acquire_master(self, key: str) -> None:
        """Open the master valve when the first user acquires it (with lead)."""
        entity = self.master_entity
        async with self._master_lock:
            first = not self._master_users
            self._master_users.add(key)
            if entity and first:
                try:
                    await self._set_switch(entity, True)
                    if self.master_lead:
                        await asyncio.sleep(self.master_lead)
                except Exception as err:  # noqa: BLE001
                    _LOGGER.warning("Could not open master valve %s: %s", entity, err)

    async def _release_master(self, key: str) -> None:
        """Close the master valve when the last user releases it."""
        entity = self.master_entity
        async with self._master_lock:
            self._master_users.discard(key)
            if entity and not self._master_users:
                await self._async_ensure_off(entity)

    # ----- flow / leak monitoring ------------------------------------------------

    async def _flow_watchdog(self, zone: Zone) -> None:
        """A short while after a valve opens, warn if no flow is detected."""
        if not self.flow_enabled:
            return
        await asyncio.sleep(FLOW_SETTLE)
        if zone.id not in self._running:
            return
        state = self.hass.states.get(zone.switch_entity)
        if state is not None and state.state != "on":
            return  # valve is in a soak gap, not actually open
        value = self._num_state(self.flow_entity)
        if value is not None and value < self.flow_min:
            self._log("flow", zone=zone.name, detail="no_flow", level="warning")
            await self._notify_flow(
                f"⚠️ {self.entry.title}: no flow detected at zone “{zone.name}” — "
                "the valve may be stuck closed."
            )

    @callback
    def _register_flow_listener(self) -> None:
        """Watch the flow sensor for sustained flow while everything is idle."""
        if self._unsub_flow:
            self._unsub_flow()
            self._unsub_flow = None
        if not self.flow_enabled:
            return
        self._unsub_flow = async_track_state_change_event(
            self.hass, [self.flow_entity], self._on_flow_change
        )

    @callback
    def _on_flow_change(self, event: Any) -> None:
        if not self.flow_enabled:
            return
        if self._running or self._master_users:
            self._cancel_leak_timer()
            return
        new_state = event.data.get("new_state")
        value = self._num_state(self.flow_entity) if new_state else None
        if value is not None and value > self.flow_min:
            if self._leak_timer is None:
                self._leak_timer = async_call_later(
                    self.hass, FLOW_LEAK_SECONDS, self._leak_fire
                )
        else:
            self._cancel_leak_timer()

    @callback
    def _cancel_leak_timer(self) -> None:
        if self._leak_timer is not None:
            self._leak_timer()
            self._leak_timer = None

    async def _leak_fire(self, _now: Any) -> None:
        self._leak_timer = None
        if self._running or self._master_users:
            return
        value = self._num_state(self.flow_entity)
        if value is not None and value > self.flow_min:
            self._log("flow", detail="leak", level="warning")
            await self._notify_flow(
                f"⚠️ {self.entry.title}: water is flowing while idle "
                f"({value}) — possible leak or stuck valve."
            )

    async def _notify_flow(self, message: str) -> None:
        targets = self.notify_targets
        if not targets or not self.entry.options.get(CONF_NOTIFY_FLOW, False):
            return
        await self._send_notification(targets, message, critical=True)

    def _num_state(self, entity_id: str | None) -> float | None:
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable", "", None):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    @property
    def notify_targets(self) -> list[str]:
        """Configured notify targets (entities/services); migrates a legacy single."""
        targets = self.entry.options.get(CONF_NOTIFY_TARGETS)
        if targets:
            return list(targets)
        legacy = self.entry.options.get(CONF_NOTIFY_TARGET)
        return [legacy] if legacy else []

    async def _notify_failure(self, zone_name: str, detail: str) -> None:
        """Send a push notification about a failure, if enabled for this setup."""
        targets = self.notify_targets
        if not targets:
            return

        if detail == "off_failed":
            if not self.entry.options.get(CONF_NOTIFY_OFF_FAILED, True):
                return
            message = (
                f"⚠️ {self.entry.title}: zone “{zone_name}” may still be OPEN — "
                "the valve did not confirm it turned off."
            )
            critical = True
        elif detail == "start_failed":
            if not self.entry.options.get(CONF_NOTIFY_START_FAILED, True):
                return
            message = f"⚠️ {self.entry.title}: zone “{zone_name}” failed to start."
            critical = False
        else:
            message = f"⚠️ {self.entry.title}: {zone_name} — {detail}"
            critical = False
        await self._send_notification(targets, message, critical=critical)

    async def async_test_notification(self) -> bool:
        """Send a test notification to the configured targets. False if none set."""
        targets = self.notify_targets
        if not targets:
            return False
        await self._send_notification(
            targets,
            f"✅ {self.entry.title}: test notification — Garden Irrigation is set up "
            "correctly.",
        )
        return True

    async def _send_notification(
        self, targets: list[str], message: str, critical: bool = False
    ) -> None:
        title = "Garden irrigation"
        # Critical/high-priority payload (iOS critical alert + Android high prio).
        data = (
            {
                "push": {"sound": {"name": "default", "critical": 1, "volume": 1.0}},
                "ttl": 0,
                "priority": "high",
            }
            if critical
            else None
        )
        for target in targets:
            try:
                if self.hass.states.get(target) is not None:
                    # Modern notify entity (send_message does not take `data`).
                    await self.hass.services.async_call(
                        "notify",
                        "send_message",
                        {"entity_id": target, "message": message, "title": title},
                        blocking=False,
                    )
                else:
                    # Legacy notify service, e.g. "notify.mobile_app_x".
                    service = target.split(".", 1)[1] if "." in target else target
                    payload = {"message": message, "title": title}
                    if data:
                        payload["data"] = data
                    await self.hass.services.async_call(
                        "notify", service, payload, blocking=False
                    )
            except Exception as err:  # noqa: BLE001
                _LOGGER.warning("Could not notify %s: %s", target, err)

    async def _async_ensure_off(self, entity_id: str) -> bool:
        """Turn the switch off and verify it; retry if it's still reported on.

        Network glitches can drop the command, so we confirm the state and try
        again a few times rather than assume a single call worked.
        """
        for attempt in range(1, OFF_MAX_ATTEMPTS + 1):
            try:
                await self._set_switch(entity_id, False)
            except Exception as err:  # noqa: BLE001 — keep retrying on any failure
                _LOGGER.warning("turn_off failed for %s: %s", entity_id, err)
            await asyncio.sleep(OFF_SETTLE)
            state = self.hass.states.get(entity_id)
            if state is None or state.state != "on":
                if attempt > 1:
                    _LOGGER.info(
                        "%s confirmed off after %d attempt(s)", entity_id, attempt
                    )
                return True
            _LOGGER.warning(
                "%s still on after turn-off attempt %d/%d",
                entity_id,
                attempt,
                OFF_MAX_ATTEMPTS,
            )
            if attempt < OFF_MAX_ATTEMPTS:
                await asyncio.sleep(OFF_RETRY_DELAY)
        _LOGGER.error(
            "%s may still be OPEN — could not confirm off after %d attempts",
            entity_id,
            OFF_MAX_ATTEMPTS,
        )
        return False

    async def _set_switch(self, entity_id: str, turn_on: bool) -> None:
        await self.hass.services.async_call(
            "homeassistant",
            "turn_on" if turn_on else "turn_off",
            {"entity_id": entity_id},
            blocking=True,
        )

    async def _run_script(self, entity_id: str) -> None:
        """Run a script entity and wait for it to finish."""
        try:
            _, object_id = entity_id.split(".", 1)
        except ValueError:
            _LOGGER.warning("Invalid script entity_id: %s", entity_id)
            return
        await self.hass.services.async_call("script", object_id, blocking=True)

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry.entry_id}")

    # ----- history ---------------------------------------------------------------

    @property
    def history(self) -> list[dict[str, Any]]:
        """Return the stored history events (oldest first)."""
        return self._history

    def _prune_history(
        self, events: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Drop events older than MAX_HISTORY_DAYS and cap the total count."""
        cutoff = dt_util.utcnow() - timedelta(days=MAX_HISTORY_DAYS)
        pruned = []
        for ev in events:
            ts = ev.get("ts")
            try:
                when = dt_util.parse_datetime(ts) if ts else None
            except (ValueError, TypeError):
                when = None
            if when is not None and when < cutoff:
                continue
            pruned.append(ev)
        if len(pruned) > MAX_HISTORY:
            pruned = pruned[-MAX_HISTORY:]
        return pruned

    async def async_clear_history(self) -> None:
        """Erase the stored activity log."""
        self._history = []
        await self._store.async_save(self._history)
        self._notify()

    @callback
    def _log(
        self,
        event_type: str,
        zone: str | None = None,
        detail: str | None = None,
        source: str | None = None,
        minutes: int | None = None,
        level: str = "info",
    ) -> None:
        """Append an event to the user-facing history and persist it (debounced)."""
        self._history.append(
            {
                "ts": dt_util.utcnow().isoformat(),
                "type": event_type,
                "zone": zone,
                "detail": detail,
                "source": source,
                "minutes": minutes,
                "level": level,
            }
        )
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]
        self._store.async_delay_save(lambda: self._history, 5)
        self._notify()

    @property
    def history_meta(self) -> dict[str, Any]:
        """Retention metadata for the history (shown in the card)."""
        return {"max_days": MAX_HISTORY_DAYS, "max_events": MAX_HISTORY}

    # ----- rain skip -------------------------------------------------------------

    @property
    def last_skip(self) -> dict[str, Any] | None:
        return self._last_skip

    async def async_skip_reason(self) -> str | None:
        """Return a skip reason (SKIP_*) if a scheduled run should be skipped now."""
        if self.rain_delay_active:
            return SKIP_RAIN_DELAY
        if await self._recent_rain():
            return SKIP_RECENT
        if await self._rain_forecast():
            return SKIP_FORECAST
        if self._freezing():
            return SKIP_FREEZE
        if self._soil_wet():
            return SKIP_SOIL
        return None

    def _freezing(self) -> bool:
        """True if the freeze entity is at/below the configured threshold."""
        if not self.entry.options.get(CONF_FREEZE_ENABLED, False):
            return False
        entity_id = self.entry.options.get(CONF_FREEZE_ENTITY)
        if not entity_id:
            return False
        threshold = float(
            self.entry.options.get(CONF_FREEZE_THRESHOLD, DEFAULT_FREEZE_THRESHOLD)
        )
        value = self._temp_value(entity_id)
        return value is not None and value <= threshold

    def _temp_value(self, entity_id: str) -> float | None:
        """Read a temperature from a sensor (state) or weather (attribute)."""
        if entity_id.split(".", 1)[0] == "weather":
            state = self.hass.states.get(entity_id)
            try:
                val = state.attributes.get("temperature") if state else None
                return float(val) if val is not None else None
            except (ValueError, TypeError, AttributeError):
                return None
        return self._num_state(entity_id)

    def _soil_wet(self) -> bool:
        """True if the soil-moisture entity is at/above the configured threshold."""
        if not self.entry.options.get(CONF_SOIL_ENABLED, False):
            return False
        entity_id = self.entry.options.get(CONF_SOIL_ENTITY)
        if not entity_id:
            return False
        threshold = float(
            self.entry.options.get(CONF_SOIL_THRESHOLD, DEFAULT_SOIL_THRESHOLD)
        )
        value = self._num_state(entity_id)
        return value is not None and value >= threshold

    # ----- manual rain delay -----------------------------------------------------

    @property
    def rain_delay_until(self) -> datetime | None:
        return self._rain_delay_until

    @property
    def rain_delay_active(self) -> bool:
        return bool(
            self._rain_delay_until and self._rain_delay_until > dt_util.utcnow()
        )

    async def async_set_rain_delay(self, hours: float) -> None:
        """Pause all watering for ``hours`` from now."""
        self._rain_delay_until = dt_util.utcnow() + timedelta(hours=hours)
        await self._state_store.async_save(
            {STATE_RAIN_DELAY_UNTIL: self._rain_delay_until.isoformat()}
        )
        self._notify()

    async def async_clear_rain_delay(self) -> None:
        """Resume scheduled watering."""
        self._rain_delay_until = None
        await self._state_store.async_save({})
        self._notify()

    # ----- per-zone cumulative totals --------------------------------------------

    def total_minutes(self, zone_id: str) -> float:
        """Total minutes this zone has ever watered (monotonic)."""
        return round(self._totals.get(zone_id, 0.0), 1)

    @callback
    def _add_total(self, zone_id: str, minutes: float) -> None:
        self._totals[zone_id] = self._totals.get(zone_id, 0.0) + minutes
        self._totals_store.async_delay_save(lambda: self._totals, 10)
        self._notify()

    def last_watered(self, zone_name: str) -> str | None:
        """ISO timestamp of the most recent completed/stopped run for a zone."""
        for ev in reversed(self._history):
            if ev.get("zone") == zone_name and ev.get("type") in ("finish", "stop"):
                return ev.get("ts")
        return None

    async def _recent_rain(self) -> bool:
        """True if the configured rain entity shows rain within the look-back window."""
        if not self.entry.options.get(CONF_RAIN_ENABLED, True):
            return False
        entity_id = self.entry.options.get(CONF_RAIN_ENTITY)
        if not entity_id:
            return False
        hours = float(self.entry.options.get(CONF_RAIN_HOURS, DEFAULT_RAIN_HOURS))
        threshold = float(
            self.entry.options.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD)
        )
        domain = entity_id.split(".", 1)[0]
        start = dt_util.utcnow() - timedelta(hours=hours)

        try:
            from homeassistant.components.recorder import get_instance, history

            recorded = await get_instance(self.hass).async_add_executor_job(
                partial(
                    history.state_changes_during_period,
                    self.hass,
                    start,
                    None,
                    entity_id,
                    include_start_time_state=True,
                    no_attributes=False,
                )
            )
        except Exception:  # recorder unavailable
            recorded = {}

        series = list(recorded.get(entity_id, []))
        current = self.hass.states.get(entity_id)
        if current is not None:
            series.append(current)

        if domain == "binary_sensor":
            return any(getattr(s, "state", None) == "on" for s in series)

        values = [
            v for v in (self._precip_value(s, domain) for s in series) if v is not None
        ]
        return bool(values) and max(values) >= threshold

    @staticmethod
    def _precip_value(state: Any, domain: str) -> float | None:
        try:
            if domain == "weather":
                val = state.attributes.get("precipitation")
                return float(val) if val is not None else None
            if state.state in ("unknown", "unavailable", "", None):
                return None
            return float(state.state)
        except (ValueError, TypeError, AttributeError):
            return None

    async def _rain_forecast(self) -> bool:
        """True if the forecast shows a high chance of rain within the look-ahead window."""
        if not self.entry.options.get(CONF_FORECAST_ENABLED, True):
            return False
        entity_id = self.entry.options.get(CONF_FORECAST_ENTITY)
        if not entity_id:
            return False
        hours = int(self.entry.options.get(CONF_FORECAST_HOURS, DEFAULT_FORECAST_HOURS))
        threshold = float(
            self.entry.options.get(CONF_FORECAST_THRESHOLD, DEFAULT_FORECAST_THRESHOLD)
        )

        try:
            response = await self.hass.services.async_call(
                "weather",
                "get_forecasts",
                {"entity_id": entity_id, "type": "hourly"},
                blocking=True,
                return_response=True,
            )
        except Exception:
            return False

        forecasts = (response or {}).get(entity_id, {}).get("forecast", [])
        now = dt_util.utcnow()
        horizon = now + timedelta(hours=hours)
        for item in forecasts:
            when = item.get("datetime")
            if isinstance(when, str):
                when = dt_util.parse_datetime(when)
            if when is None:
                continue
            when = dt_util.as_utc(when)
            if when < now - timedelta(hours=1) or when > horizon:
                continue
            prob = item.get("precipitation_probability")
            if prob is not None and float(prob) >= threshold:
                return True
        return False

    @callback
    def _record_skip(self, reason: str) -> None:
        self._last_skip = {"reason": reason, "at": dt_util.utcnow().isoformat()}
        self._log("skip", detail=reason, level="warning")
        _LOGGER.info(
            "Skipping scheduled irrigation for %s (%s)", self.entry.title, reason
        )
        if self.notify_targets and self.entry.options.get(CONF_NOTIFY_SKIP, False):
            label = {
                SKIP_FORECAST: "rain forecast",
                SKIP_RECENT: "recent rain",
                SKIP_FREEZE: "freezing temperature",
                SKIP_SOIL: "soil already moist",
                SKIP_RAIN_DELAY: "rain delay active",
            }.get(reason, reason)
            self.hass.async_create_task(
                self._send_notification(
                    self.notify_targets,
                    f"🌧️ {self.entry.title}: scheduled watering skipped ({label}).",
                )
            )
        self.hass.bus.async_fire(
            EVENT_SKIPPED,
            {
                "entry_id": self.entry.entry_id,
                "setup": self.entry.title,
                "reason": reason,
            },
        )
        self._notify()

    @callback
    def _update_overlap_issue(self) -> None:
        """Raise/clear the repair issue for overlaps (specific) or start collisions (sequential)."""
        overlap_id = f"{ISSUE_OVERLAP}_{self.entry.entry_id}"
        collision_id = f"{ISSUE_COLLISION}_{self.entry.entry_id}"

        if self.mode == MODE_SEQUENTIAL:
            ir.async_delete_issue(self.hass, DOMAIN, overlap_id)
            collisions = compute_start_collisions(
                self.start_schedules, self.total_duration
            )
            if collisions:
                ir.async_create_issue(
                    self.hass,
                    DOMAIN,
                    collision_id,
                    is_fixable=False,
                    severity=ir.IssueSeverity.WARNING,
                    translation_key=ISSUE_COLLISION,
                    translation_placeholders={
                        "setup": self.entry.title,
                        "collisions": "\n".join(f"• {c}" for c in collisions),
                    },
                )
            else:
                ir.async_delete_issue(self.hass, DOMAIN, collision_id)
            return

        ir.async_delete_issue(self.hass, DOMAIN, collision_id)
        issue_id = overlap_id
        zone_dicts = [
            {
                CONF_NAME: z.name,
                CONF_DURATION: z.duration,
                CONF_SCHEDULES: z.schedules,
            }
            for z in self.zones.values()
        ]
        overlaps = compute_overlaps(zone_dicts)
        if overlaps:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue_id,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_OVERLAP,
                translation_placeholders={
                    "setup": self.entry.title,
                    "overlaps": "\n".join(f"• {o}" for o in overlaps),
                },
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)


class _suppress_cancelled:
    """Context manager that swallows CancelledError while awaiting task cleanup."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is asyncio.CancelledError
