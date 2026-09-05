"""Build the weekly plan an offline-capable relay controller can run on its own.

Pure functions, no Home Assistant objects: they turn a setup's zones, schedules and options
into per-relay time blocks (local minutes since midnight, per weekday) in the JSON shape the
relay6 firmware's ``set_schedule`` action accepts (kept in step with ``core/src/schedule.rs``)::

    {"rev": 123, "channels": {"1": [{"days": "MTWTF--", "from": 360, "to": 420}]}}

Only what the device can do by itself is exported: on/off timing, cycle & soak bursts and the
master valve window. Rain/freeze/soil skips, rain delay, scripts and flow monitoring stay in
Home Assistant, which drives the relays directly while it is reachable; the device applies this
plan only when Home Assistant is gone.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .const import CONF_DAYS, CONF_TIME, MAX_DURATION, MODE_SEQUENTIAL, WEEKDAYS

MINUTES_PER_DAY = 1440
DAY_LETTERS = "MTWTFSS"

# Hardware safeguard bounds (minutes): the device turns a relay off by itself after this long.
SAFEGUARD_MIN = 15
SAFEGUARD_MAX = MAX_DURATION + 5
SAFEGUARD_MARGIN = 5


@dataclass
class ZonePlan:
    """What the plan builder needs to know about one zone."""

    name: str
    minutes: int  # effective run minutes (seasonal adjust already applied)
    cycles: int = 1
    soak: int = 0
    enabled: bool = True
    schedules: list[dict[str, Any]] = field(default_factory=list)
    relay: tuple[str, int] | None = None  # (device node name, relay channel 1..6)

    def bursts(self) -> tuple[int, int, int]:
        """Return (on_minutes_per_cycle, cycles, soak) mirroring the coordinator's split."""
        cycles = max(1, self.cycles)
        on_each = max(1, self.minutes // cycles)
        return on_each, cycles, max(0, self.soak)

    def wall_minutes(self) -> int:
        on_each, cycles, soak = self.bursts()
        return on_each * cycles + soak * (cycles - 1)


@dataclass
class DevicePlan:
    """Blocks per relay channel for one device, plus the longest single on-period per channel."""

    channels: dict[int, list[dict[str, Any]]] = field(default_factory=dict)
    longest_on: dict[int, int] = field(default_factory=dict)

    def add(self, channel: int, days: list[str], start: int, end: int) -> None:
        """Add an on-interval [start, end) in minutes from midnight of the given weekdays.

        ``start``/``end`` may exceed a day (chains that run past midnight); the block is
        shifted to the right weekdays and split at midnight as needed.
        """
        if end <= start:
            return
        self.longest_on[channel] = max(self.longest_on.get(channel, 0), end - start)
        shift, start = divmod(start, MINUTES_PER_DAY)
        end -= shift * MINUTES_PER_DAY
        day_idx = [(WEEKDAYS.index(d) + shift) % 7 for d in days if d in WEEKDAYS]
        while end > 0 and day_idx:
            piece_end = min(end, MINUTES_PER_DAY)
            self.channels.setdefault(channel, []).append(
                {"days": _mask(day_idx), "from": start, "to": piece_end}
            )
            if end <= MINUTES_PER_DAY:
                break
            # Remainder spills into the next day.
            day_idx = [(d + 1) % 7 for d in day_idx]
            start, end = 0, end - MINUTES_PER_DAY

    def merge(self, other: DevicePlan) -> None:
        for ch, blocks in other.channels.items():
            self.channels.setdefault(ch, []).extend(blocks)
        for ch, longest in other.longest_on.items():
            self.longest_on[ch] = max(self.longest_on.get(ch, 0), longest)

    def safeguards(self) -> dict[int, int]:
        """Suggested per-channel max-on-time (minutes) for the device's hardware safeguard."""
        return {
            ch: min(SAFEGUARD_MAX, max(SAFEGUARD_MIN, 2 * longest + SAFEGUARD_MARGIN))
            for ch, longest in self.longest_on.items()
        }

    def payload(self, rev: int) -> dict[str, Any]:
        return {
            "rev": rev & 0xFFFFFFFF,
            "channels": {str(ch): blocks for ch, blocks in sorted(self.channels.items()) if blocks},
        }

    def block_count(self) -> int:
        return sum(len(b) for b in self.channels.values())


def _mask(day_idx: list[int]) -> str:
    return "".join(DAY_LETTERS[i] if i in day_idx else "-" for i in range(7))


def parse_minutes(value: str) -> int:
    hour, minute = value.split(":")[:2]
    return int(hour) * 60 + int(minute)


def build_setup_plans(
    *,
    mode: str,
    enabled: bool,
    start_schedules: list[dict[str, Any]],
    zones: list[ZonePlan],
    master: tuple[str, int] | None = None,
) -> dict[str, DevicePlan]:
    """Return one DevicePlan per device node name for a single setup.

    ``zones`` must be in run order (subentry order). Zones without a ``relay`` mapping are
    still part of a sequential chain's timing but produce no device blocks.
    """
    plans: dict[str, DevicePlan] = {}

    def plan_for(node: str) -> DevicePlan:
        return plans.setdefault(node, DevicePlan())

    def emit_zone(zone: ZonePlan, days: list[str], start: int) -> int:
        """Emit a zone's bursts starting at ``start``; return the wall time consumed.

        The master valve/pump (if it is a relay on the same device) is opened for exactly the
        same bursts: offline, zones on other hardware do not run, so opening the master for
        them would dead-head a pump, and it stays closed during soak gaps for the same reason.
        """
        on_each, cycles, soak = zone.bursts()
        if zone.relay:
            node, ch = zone.relay
            cursor = start
            for i in range(cycles):
                plan_for(node).add(ch, days, cursor, cursor + on_each)
                if master and master[0] == node:
                    plan_for(node).add(master[1], days, cursor, cursor + on_each)
                cursor += on_each + (soak if i < cycles - 1 else 0)
        return zone.wall_minutes()

    if not enabled:
        return plans
    active = [z for z in zones if z.enabled and z.minutes > 0]
    if not active:
        return plans

    if mode == MODE_SEQUENTIAL:
        for sched in start_schedules:
            days = list(sched.get(CONF_DAYS) or WEEKDAYS)
            start = parse_minutes(sched[CONF_TIME])
            cursor = start
            for zone in active:
                cursor += emit_zone(zone, days, cursor)
        return plans

    for zone in active:
        for sched in zone.schedules:
            days = list(sched.get(CONF_DAYS) or WEEKDAYS)
            start = parse_minutes(sched[CONF_TIME])
            emit_zone(zone, days, start)
    return plans
