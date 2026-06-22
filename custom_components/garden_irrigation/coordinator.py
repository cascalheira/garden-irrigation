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
    CONF_START_TIME,
    CONF_SWITCH_ENTITY,
    CONF_TIME,
    DEFAULT_DURATION,
    DEFAULT_MODE,
    DEFAULT_START_TIME,
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
    )


class IrrigationController:
    """Owns the scheduling and execution of one setup's zones."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self._running: dict[str, RunState] = {}
        self._chain_task: asyncio.Task | None = None
        self._unsub_time: list[Callable[[], None]] = []

    # ----- configuration helpers -------------------------------------------------

    @property
    def mode(self) -> str:
        """Return the scheduling mode (sequential | specific)."""
        return self.entry.options.get(CONF_MODE, DEFAULT_MODE)

    @property
    def start_time(self) -> str:
        """Return the sequential start time 'HH:MM'."""
        return self.entry.options.get(CONF_START_TIME, DEFAULT_START_TIME)

    @property
    def days(self) -> list[str]:
        """Return the days the sequential chain runs."""
        return self.entry.options.get(CONF_DAYS) or list(WEEKDAYS)

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
        self._register_schedules()
        self._update_overlap_issue()

    async def async_shutdown(self) -> None:
        """Cancel listeners and every running task."""
        for unsub in self._unsub_time:
            unsub()
        self._unsub_time.clear()

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

    @callback
    def _register_schedules(self) -> None:
        """(Re)register the time listeners appropriate to the current mode."""
        for unsub in self._unsub_time:
            unsub()
        self._unsub_time.clear()

        if self.mode == MODE_SEQUENTIAL:
            hour, minute = parse_time(self.start_time)
            self._unsub_time.append(
                async_track_time_change(
                    self.hass, self._sequential_trigger, hour=hour, minute=minute, second=0
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
    def _sequential_trigger(self, now: datetime) -> None:
        """Fire at the setup start time; run the whole chain if today matches."""
        weekday = WEEKDAYS[dt_util.as_local(now).weekday()]
        if weekday not in self.days:
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
        self.hass.async_create_task(
            self.async_start_zone(zone_id, source="scheduled")
        )

    # ----- public control surface ------------------------------------------------

    async def async_start_zone(
        self, zone_id: str, duration: int | None = None, source: str = "manual"
    ) -> None:
        """Start a single zone now (independent of any chain)."""
        zone = self.get_zone(zone_id)
        if zone is None:
            _LOGGER.warning("Cannot start unknown zone %s", zone_id)
            return
        if zone_id in self._running:
            return  # already watering

        minutes = duration if duration is not None else zone.duration
        self.hass.async_create_task(
            self._run_single(zone, int(minutes) * 60, source),
            name=f"{DOMAIN}_{zone_id}",
        )

    @callback
    def async_run_chain(self) -> None:
        """Start the sequential chain (all zones, in order)."""
        if self._chain_task and not self._chain_task.done():
            return
        if not self.zones:
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
            schedules = [{CONF_TIME: self.start_time, CONF_DAYS: self.days}]
        else:
            schedules = zone.schedules
        if not schedules:
            return None
        return compute_next_run(schedules, dt_util.now())

    # ----- execution -------------------------------------------------------------

    async def _run_chain(self) -> None:
        """Run every zone in order; cancellation stops the remaining zones."""
        _LOGGER.debug("Starting sequential chain for %s", self.entry.title)
        try:
            for zone in self.zones.values():
                await self._water(zone, zone.duration * 60, "scheduled")
        except asyncio.CancelledError:
            _LOGGER.debug("Chain for %s stopped early", self.entry.title)

    async def _run_single(self, zone: Zone, seconds: int, source: str) -> None:
        try:
            await self._water(zone, seconds, source)
        except asyncio.CancelledError:
            pass

    async def _water(self, zone: Zone, seconds: int, source: str) -> None:
        """Water one zone: pre-script, switch on, wait, switch off, post-script.

        Runs in the calling task (the chain task or a single-run task) so that
        cancelling that task stops watering. Cleanup is shielded so the valve is
        always closed even on cancellation.
        """
        task = asyncio.current_task()
        self._running[zone.id] = RunState(
            task=task,
            ends_at=dt_util.utcnow() + timedelta(seconds=seconds),
            source=source,
        )
        self._notify()
        try:
            if zone.pre_script:
                await self._run_script(zone.pre_script)
            await self._set_switch(zone.switch_entity, True)
            await asyncio.sleep(seconds)
        finally:
            await asyncio.shield(self._cleanup(zone))

    async def _cleanup(self, zone: Zone) -> None:
        try:
            await self._set_switch(zone.switch_entity, False)
            if zone.post_script:
                await self._run_script(zone.post_script)
        finally:
            self._running.pop(zone.id, None)
            self._notify()

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

    @callback
    def _update_overlap_issue(self) -> None:
        """Raise/clear the overlap repair issue (only meaningful in specific mode)."""
        issue_id = f"{ISSUE_OVERLAP}_{self.entry.entry_id}"
        if self.mode == MODE_SEQUENTIAL:
            ir.async_delete_issue(self.hass, DOMAIN, issue_id)
            return

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
