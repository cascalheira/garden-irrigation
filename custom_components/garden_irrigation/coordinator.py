"""Runtime controller that drives irrigation zones, schedules and scripts."""

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
from homeassistant.helpers.event import async_track_time_change
from homeassistant.util import dt as dt_util

from .const import (
    CONF_DAYS,
    CONF_DURATION,
    CONF_MODE,
    CONF_NAME,
    CONF_POST_SCRIPT,
    CONF_PRE_SCRIPT,
    CONF_SCHEDULES,
    CONF_SWITCH_ENTITY,
    CONF_TIME,
    DEFAULT_DURATION,
    DEFAULT_MODE,
    DOMAIN,
    ISSUE_OVERLAP,
    MODE_SEQUENTIAL,
    SIGNAL_UPDATE,
    SUBENTRY_TYPE_ZONE,
    WEEKDAYS,
)
from .util import compute_next_run, compute_overlaps, parse_time

_LOGGER = logging.getLogger(__name__)


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


@dataclass
class RunState:
    """Bookkeeping for a zone that is currently watering."""

    task: asyncio.Task
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
    )


class IrrigationController:
    """Owns the scheduling, sequencing and execution of every zone."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._running: dict[str, RunState] = {}
        self._queue: list[tuple[str, int | None, str]] = []
        self._unsub_time: list[Callable[[], None]] = []

    # ----- configuration helpers -------------------------------------------------

    @property
    def mode(self) -> str:
        """Return the configured watering mode."""
        return self.entry.options.get(CONF_MODE, DEFAULT_MODE)

    @property
    def zones(self) -> dict[str, Zone]:
        """Return all configured zones, keyed by subentry id."""
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
        self._register_schedules()
        self._update_overlap_issue()

    async def async_shutdown(self) -> None:
        """Cancel listeners, running runs and queued runs."""
        for unsub in self._unsub_time:
            unsub()
        self._unsub_time.clear()
        self._queue.clear()
        tasks = [state.task for state in self._running.values()]
        for task in tasks:
            task.cancel()
        for task in tasks:
            with _suppress_cancelled():
                await task
        self._running.clear()

    @callback
    def _register_schedules(self) -> None:
        """(Re)register one time-change listener per schedule entry."""
        for unsub in self._unsub_time:
            unsub()
        self._unsub_time.clear()

        for zone in self.zones.values():
            for sched in zone.schedules:
                hour, minute = parse_time(sched[CONF_TIME])
                unsub = async_track_time_change(
                    self.hass,
                    partial(self._scheduled_trigger, zone.id, sched),
                    hour=hour,
                    minute=minute,
                    second=0,
                )
                self._unsub_time.append(unsub)

    @callback
    def _scheduled_trigger(
        self, zone_id: str, sched: dict[str, Any], now: datetime
    ) -> None:
        """Fire when a schedule's time-of-day matches; start if the day matches."""
        days = sched.get(CONF_DAYS) or WEEKDAYS
        weekday = WEEKDAYS[dt_util.as_local(now).weekday()]
        if weekday not in days:
            return
        self.hass.async_create_task(
            self.async_start_zone(zone_id, source="scheduled")
        )

    # ----- public control surface ------------------------------------------------

    async def async_start_zone(
        self, zone_id: str, duration: int | None = None, source: str = "manual"
    ) -> None:
        """Start a zone now, or queue it in sequential mode if one is running."""
        zone = self.get_zone(zone_id)
        if zone is None:
            _LOGGER.warning("Cannot start unknown zone %s", zone_id)
            return

        if zone_id in self._running:
            return  # already watering

        if self.mode == MODE_SEQUENTIAL and self._running:
            if zone_id not in (q[0] for q in self._queue):
                self._queue.append((zone_id, duration, source))
                self._notify()
            return

        self._start_task(zone_id, duration, source)

    async def async_stop_zone(self, zone_id: str) -> None:
        """Stop a running zone and drop it from the queue."""
        self._queue = [q for q in self._queue if q[0] != zone_id]
        state = self._running.get(zone_id)
        if state is not None:
            state.task.cancel()
        self._notify()

    async def async_stop_all(self) -> None:
        """Stop every running zone and clear the queue."""
        self._queue.clear()
        for state in list(self._running.values()):
            state.task.cancel()
        self._notify()

    # ----- introspection for entities --------------------------------------------

    def is_running(self, zone_id: str) -> bool:
        """Return whether the zone is currently watering."""
        return zone_id in self._running

    def is_queued(self, zone_id: str) -> bool:
        """Return whether the zone is waiting in the sequential queue."""
        return any(q[0] == zone_id for q in self._queue)

    def ends_at(self, zone_id: str) -> datetime | None:
        """Return when the current run finishes, or ``None``."""
        state = self._running.get(zone_id)
        return state.ends_at if state else None

    def run_source(self, zone_id: str) -> str | None:
        """Return 'manual'/'scheduled' for a running zone, else ``None``."""
        state = self._running.get(zone_id)
        return state.source if state else None

    def remaining_seconds(self, zone_id: str) -> int:
        """Return seconds left in the current run (0 if not running)."""
        ends_at = self.ends_at(zone_id)
        if ends_at is None:
            return 0
        return max(0, int((ends_at - dt_util.utcnow()).total_seconds()))

    def next_run(self, zone_id: str) -> datetime | None:
        """Return the next scheduled start for the zone."""
        zone = self.get_zone(zone_id)
        if zone is None or not zone.schedules:
            return None
        return compute_next_run(zone.schedules, dt_util.now())

    # ----- internals -------------------------------------------------------------

    @callback
    def _start_task(
        self, zone_id: str, duration: int | None, source: str
    ) -> None:
        zone = self.zones[zone_id]
        minutes = duration if duration is not None else zone.duration
        seconds = int(minutes) * 60
        task = self.hass.async_create_task(
            self._run_zone(zone, seconds), name=f"{DOMAIN}_{zone_id}"
        )
        self._running[zone_id] = RunState(
            task=task,
            ends_at=dt_util.utcnow() + timedelta(seconds=seconds),
            source=source,
        )
        self._notify()

    async def _run_zone(self, zone: Zone, seconds: int) -> None:
        """Execute one watering run: pre-script, switch on, wait, switch off, post."""
        _LOGGER.debug("Starting zone %s for %ss", zone.name, seconds)
        try:
            if zone.pre_script:
                await self._run_script(zone.pre_script)
            await self._set_switch(zone.switch_entity, True)
            await asyncio.sleep(seconds)
        except asyncio.CancelledError:
            _LOGGER.debug("Zone %s stopped early", zone.name)
        finally:
            # Cleanup must complete even though the task was cancelled.
            await asyncio.shield(self._finish_zone(zone))

    async def _finish_zone(self, zone: Zone) -> None:
        try:
            await self._set_switch(zone.switch_entity, False)
            if zone.post_script:
                await self._run_script(zone.post_script)
        finally:
            self._running.pop(zone.id, None)
            self._notify()
            if self.mode == MODE_SEQUENTIAL:
                self._process_queue()

    @callback
    def _process_queue(self) -> None:
        if self._running or not self._queue:
            return
        zone_id, duration, source = self._queue.pop(0)
        if zone_id in self.zones:
            self._start_task(zone_id, duration, source)

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
        await self.hass.services.async_call(
            "script", object_id, blocking=True
        )

    @callback
    def _notify(self) -> None:
        async_dispatcher_send(self.hass, f"{SIGNAL_UPDATE}_{self.entry.entry_id}")

    @callback
    def _update_overlap_issue(self) -> None:
        """Raise or clear the discreet repair issue describing overlapping schedules."""
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
                ISSUE_OVERLAP,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key=ISSUE_OVERLAP,
                translation_placeholders={"overlaps": "\n".join(f"• {o}" for o in overlaps)},
            )
        else:
            ir.async_delete_issue(self.hass, DOMAIN, ISSUE_OVERLAP)


class _suppress_cancelled:
    """Context manager that swallows CancelledError while awaiting task cleanup."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type, exc, tb) -> bool:
        return exc_type is asyncio.CancelledError
