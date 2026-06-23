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
    CONF_FORECAST_ENTITY,
    CONF_FORECAST_HOURS,
    CONF_FORECAST_THRESHOLD,
    CONF_MODE,
    CONF_NAME,
    CONF_POST_SCRIPT,
    CONF_PRE_SCRIPT,
    CONF_RAIN_ENTITY,
    CONF_RAIN_HOURS,
    CONF_RAIN_THRESHOLD,
    CONF_SCHEDULES,
    CONF_START_TIME,
    CONF_START_TIMES,
    CONF_SWITCH_ENTITY,
    CONF_TIME,
    DEFAULT_DURATION,
    DEFAULT_FORECAST_HOURS,
    DEFAULT_FORECAST_THRESHOLD,
    DEFAULT_MODE,
    DEFAULT_RAIN_HOURS,
    DEFAULT_RAIN_THRESHOLD,
    DOMAIN,
    EVENT_SKIPPED,
    ISSUE_COLLISION,
    ISSUE_OVERLAP,
    MODE_SEQUENTIAL,
    SIGNAL_UPDATE,
    SKIP_FORECAST,
    SKIP_RECENT,
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
        self._last_skip: dict[str, Any] | None = None

    # ----- configuration helpers -------------------------------------------------

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
        reason = await self.async_skip_reason()
        if reason:
            self._record_skip(reason)
            return
        await self.async_start_zone(zone_id, source="scheduled")

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
        try:
            if self.pre_script:
                await self._run_script(self.pre_script)
            for zone in self.zones.values():
                await self._water(zone, zone.duration * 60, "scheduled")
        except asyncio.CancelledError:
            _LOGGER.debug("Chain for %s stopped early", self.entry.title)
        finally:
            if self.post_script:
                await asyncio.shield(self._run_script(self.post_script))

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

    # ----- rain skip -------------------------------------------------------------

    @property
    def last_skip(self) -> dict[str, Any] | None:
        return self._last_skip

    async def async_skip_reason(self) -> str | None:
        """Return a skip reason (SKIP_*) if a scheduled run should be skipped now."""
        if await self._recent_rain():
            return SKIP_RECENT
        if await self._rain_forecast():
            return SKIP_FORECAST
        return None

    async def _recent_rain(self) -> bool:
        """True if the configured rain entity shows rain within the look-back window."""
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
        _LOGGER.info(
            "Skipping scheduled irrigation for %s (%s)", self.entry.title, reason
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
