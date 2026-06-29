"""Websocket commands backing the Garden Irrigation Lovelace card.

Exposes setup (config entry) and zone/schedule (subentry) CRUD so the card can
manage everything the config-flow UI manages. All mutations require an admin user
and trigger a reload of the affected config entry.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry, ConfigSubentry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

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
    DEFAULT_START_TIME,
    DOMAIN,
    MAX_CYCLES,
    MAX_DURATION,
    MAX_MASTER_LEAD,
    MAX_SEASONAL_ADJUST,
    MAX_SOAK,
    MIN_DURATION,
    MIN_SEASONAL_ADJUST,
    MODES,
    SUBENTRY_TYPE_ZONE,
    WEEKDAYS,
)

TIME_RE = vol.Match(r"^([01]?\d|2[0-3]):[0-5]\d")


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all websocket commands (called once from async_setup)."""
    for command in (
        ws_get,
        ws_add_setup,
        ws_update_setup,
        ws_delete_setup,
        ws_add_start_time,
        ws_remove_start_time,
        ws_run_setup,
        ws_stop_setup,
        ws_rain_delay,
        ws_start_zone,
        ws_skip_status,
        ws_history,
        ws_clear_history,
        ws_notify_test,
        ws_add_zone,
        ws_update_zone,
        ws_delete_zone,
        ws_add_schedule,
        ws_remove_schedule,
    ):
        websocket_api.async_register_command(hass, command)


@callback
def _entry(hass: HomeAssistant, entry_id: str) -> ConfigEntry | None:
    entry = hass.config_entries.async_get_entry(entry_id)
    if entry and entry.domain == DOMAIN:
        return entry
    return None


@callback
def _zone_payload(
    hass: HomeAssistant,
    entry_id: str,
    subentry_id: str,
    data: dict[str, Any],
    controller: Any = None,
) -> dict[str, Any]:
    ent_reg = er.async_get(hass)
    name = data.get(CONF_NAME)
    payload = {
        "zone_id": subentry_id,
        "entry_id": entry_id,
        "name": name,
        "enabled": data.get(CONF_ENABLED, True),
        "switch_entity": data.get(CONF_SWITCH_ENTITY),
        "duration": int(data.get(CONF_DURATION, DEFAULT_DURATION)),
        "cycles": int(data.get(CONF_CYCLES, DEFAULT_CYCLES) or DEFAULT_CYCLES),
        "soak": int(data.get(CONF_SOAK, DEFAULT_SOAK) or DEFAULT_SOAK),
        "schedules": list(data.get(CONF_SCHEDULES, [])),
        "pre_script": data.get(CONF_PRE_SCRIPT),
        "post_script": data.get(CONF_POST_SCRIPT),
        "entity_id": ent_reg.async_get_entity_id("switch", DOMAIN, subentry_id),
        "sensor_entity_id": ent_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{subentry_id}_remaining"
        ),
        "last_watered": None,
        "next_run": None,
        "total_minutes": 0,
        "effective_duration": int(data.get(CONF_DURATION, DEFAULT_DURATION)),
    }
    if controller is not None:
        zone = controller.get_zone(subentry_id)
        if zone is not None:
            payload["effective_duration"] = controller.effective_minutes(zone)
        payload["last_watered"] = controller.last_watered(name)
        payload["total_minutes"] = controller.total_minutes(subentry_id)
        nxt = controller.next_run(subentry_id)
        payload["next_run"] = nxt.isoformat() if nxt else None
    return payload


@callback
def _start_times(options: Any) -> list[dict[str, Any]]:
    """Return sequential start times, migrating a legacy single start_time."""
    times = options.get(CONF_START_TIMES)
    if times:
        return [dict(s) for s in times]
    legacy = options.get(CONF_START_TIME)
    if legacy:
        return [{CONF_TIME: legacy[:5], CONF_DAYS: options.get(CONF_DAYS, list(WEEKDAYS))}]
    return []


@callback
def _setup_payload(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    options = entry.options
    controller = getattr(entry, "runtime_data", None)
    zones = [
        _zone_payload(hass, entry.entry_id, sid, dict(sub.data), controller)
        for sid, sub in entry.subentries.items()
        if sub.subentry_type == SUBENTRY_TYPE_ZONE
    ]
    rain_delay_until = None
    if controller is not None and controller.rain_delay_active:
        until = controller.rain_delay_until
        rain_delay_until = until.isoformat() if until else None
    return {
        "entry_id": entry.entry_id,
        "name": entry.title,
        "enabled": options.get(CONF_ENABLED, True),
        "mode": options.get(CONF_MODE, DEFAULT_MODE),
        "start_times": _start_times(options),
        "pre_script": options.get(CONF_PRE_SCRIPT),
        "post_script": options.get(CONF_POST_SCRIPT),
        "seasonal_adjust": options.get(CONF_SEASONAL_ADJUST, DEFAULT_SEASONAL_ADJUST),
        "master_entity": options.get(CONF_MASTER_ENTITY),
        "master_lead": options.get(CONF_MASTER_LEAD, DEFAULT_MASTER_LEAD),
        "freeze_enabled": options.get(CONF_FREEZE_ENABLED, False),
        "freeze_entity": options.get(CONF_FREEZE_ENTITY),
        "freeze_threshold": options.get(
            CONF_FREEZE_THRESHOLD, DEFAULT_FREEZE_THRESHOLD
        ),
        "soil_enabled": options.get(CONF_SOIL_ENABLED, False),
        "soil_entity": options.get(CONF_SOIL_ENTITY),
        "soil_threshold": options.get(CONF_SOIL_THRESHOLD, DEFAULT_SOIL_THRESHOLD),
        "flow_enabled": options.get(CONF_FLOW_ENABLED, False),
        "flow_entity": options.get(CONF_FLOW_ENTITY),
        "flow_min": options.get(CONF_FLOW_MIN, DEFAULT_FLOW_MIN),
        "notify_flow": options.get(CONF_NOTIFY_FLOW, False),
        "rain_delay_until": rain_delay_until,
        "rain_enabled": options.get(CONF_RAIN_ENABLED, True),
        "rain_entity": options.get(CONF_RAIN_ENTITY),
        "rain_hours": options.get(CONF_RAIN_HOURS, DEFAULT_RAIN_HOURS),
        "rain_threshold": options.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD),
        "forecast_enabled": options.get(CONF_FORECAST_ENABLED, True),
        "forecast_entity": options.get(CONF_FORECAST_ENTITY),
        "forecast_hours": options.get(CONF_FORECAST_HOURS, DEFAULT_FORECAST_HOURS),
        "forecast_threshold": options.get(
            CONF_FORECAST_THRESHOLD, DEFAULT_FORECAST_THRESHOLD
        ),
        "notify_targets": options.get(CONF_NOTIFY_TARGETS)
        or ([options[CONF_NOTIFY_TARGET]] if options.get(CONF_NOTIFY_TARGET) else []),
        "notify_off_failed": options.get(CONF_NOTIFY_OFF_FAILED, True),
        "notify_start_failed": options.get(CONF_NOTIFY_START_FAILED, True),
        "notify_skip": options.get(CONF_NOTIFY_SKIP, False),
        "total_duration": sum(
            int(sub.data.get(CONF_DURATION, DEFAULT_DURATION))
            for sub in entry.subentries.values()
            if sub.subentry_type == SUBENTRY_TYPE_ZONE
        ),
        "zones": zones,
    }


@websocket_api.websocket_command({vol.Required("type"): "garden_irrigation/get"})
@callback
def ws_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return all setups (with their zones) for the card."""
    setups = [
        _setup_payload(hass, entry)
        for entry in hass.config_entries.async_entries(DOMAIN)
    ]
    connection.send_result(msg["id"], {"setups": setups})


# ----- setup (config entry) commands --------------------------------------------


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/setup/add",
        vol.Required("name"): vol.All(str, vol.Length(min=1)),
        vol.Optional("mode", default=DEFAULT_MODE): vol.In(MODES),
        vol.Optional("start_time", default=DEFAULT_START_TIME): TIME_RE,
        vol.Optional("days", default=list(WEEKDAYS)): [vol.In(WEEKDAYS)],
        vol.Optional("pre_script"): vol.Any(str, None),
        vol.Optional("post_script"): vol.Any(str, None),
    }
)
@websocket_api.async_response
async def ws_add_setup(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create a new setup (config entry) via the import flow."""
    data = {
        CONF_NAME: msg["name"],
        CONF_MODE: msg["mode"],
        CONF_START_TIME: msg["start_time"][:5],
        CONF_DAYS: msg["days"],
    }
    if msg.get("pre_script"):
        data[CONF_PRE_SCRIPT] = msg["pre_script"]
    if msg.get("post_script"):
        data[CONF_POST_SCRIPT] = msg["post_script"]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "import"}, data=data
    )
    entry = result.get("result")
    connection.send_result(
        msg["id"], {"entry_id": entry.entry_id if entry else None}
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/setup/update",
        vol.Required("entry_id"): str,
        vol.Optional("name"): vol.All(str, vol.Length(min=1)),
        vol.Optional("enabled"): bool,
        vol.Optional("mode"): vol.In(MODES),
        vol.Optional("start_time"): TIME_RE,
        vol.Optional("days"): [vol.In(WEEKDAYS)],
        vol.Optional("pre_script"): vol.Any(str, None),
        vol.Optional("post_script"): vol.Any(str, None),
        vol.Optional("rain_enabled"): bool,
        vol.Optional("rain_entity"): vol.Any(str, None),
        vol.Optional("rain_hours"): vol.Coerce(float),
        vol.Optional("rain_threshold"): vol.Coerce(float),
        vol.Optional("forecast_enabled"): bool,
        vol.Optional("forecast_entity"): vol.Any(str, None),
        vol.Optional("forecast_hours"): vol.Coerce(float),
        vol.Optional("forecast_threshold"): vol.Coerce(float),
        vol.Optional("notify_targets"): [str],
        vol.Optional("notify_off_failed"): bool,
        vol.Optional("notify_start_failed"): bool,
        vol.Optional("notify_skip"): bool,
        vol.Optional("notify_flow"): bool,
        vol.Optional("seasonal_adjust"): vol.Coerce(int),
        vol.Optional("master_entity"): vol.Any(str, None),
        vol.Optional("master_lead"): vol.Coerce(int),
        vol.Optional("freeze_enabled"): bool,
        vol.Optional("freeze_entity"): vol.Any(str, None),
        vol.Optional("freeze_threshold"): vol.Coerce(float),
        vol.Optional("soil_enabled"): bool,
        vol.Optional("soil_entity"): vol.Any(str, None),
        vol.Optional("soil_threshold"): vol.Coerce(float),
        vol.Optional("flow_enabled"): bool,
        vol.Optional("flow_entity"): vol.Any(str, None),
        vol.Optional("flow_min"): vol.Coerce(float),
    }
)
@callback
def ws_update_setup(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update a setup's name and/or scheduling options."""
    entry = _entry(hass, msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Unknown setup")
        return

    options = dict(entry.options)
    for flag in (
        "enabled",
        "rain_enabled",
        "forecast_enabled",
        "freeze_enabled",
        "soil_enabled",
        "flow_enabled",
        "notify_off_failed",
        "notify_start_failed",
        "notify_skip",
        "notify_flow",
    ):
        if flag in msg:
            options[flag] = bool(msg[flag])
    if "notify_targets" in msg:
        options[CONF_NOTIFY_TARGETS] = msg["notify_targets"]
        options.pop(CONF_NOTIFY_TARGET, None)  # drop legacy single
    if "mode" in msg:
        options[CONF_MODE] = msg["mode"]
    if "start_time" in msg:
        options[CONF_START_TIME] = msg["start_time"][:5]
    if "days" in msg:
        options[CONF_DAYS] = msg["days"]
    for key in (
        CONF_PRE_SCRIPT,
        CONF_POST_SCRIPT,
        CONF_RAIN_ENTITY,
        CONF_FORECAST_ENTITY,
        CONF_MASTER_ENTITY,
        CONF_FREEZE_ENTITY,
        CONF_SOIL_ENTITY,
        CONF_FLOW_ENTITY,
    ):
        if key in msg:
            if msg[key]:
                options[key] = msg[key]
            else:
                options.pop(key, None)
    for key in (
        CONF_RAIN_HOURS,
        CONF_RAIN_THRESHOLD,
        CONF_FORECAST_HOURS,
        CONF_FORECAST_THRESHOLD,
        CONF_SEASONAL_ADJUST,
        CONF_MASTER_LEAD,
        CONF_FREEZE_THRESHOLD,
        CONF_SOIL_THRESHOLD,
        CONF_FLOW_MIN,
    ):
        if key in msg and msg[key] is not None:
            options[key] = msg[key]

    title = msg.get("name", entry.title)
    hass.config_entries.async_update_entry(entry, title=title, options=options)
    connection.send_result(msg["id"], _setup_payload(hass, entry))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/setup/delete",
        vol.Required("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_delete_setup(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a whole setup (config entry)."""
    if _entry(hass, msg["entry_id"]) is None:
        connection.send_error(msg["id"], "not_found", "Unknown setup")
        return
    await hass.config_entries.async_remove(msg["entry_id"])
    connection.send_result(msg["id"], {"entry_id": msg["entry_id"]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/setup/start_time/add",
        vol.Required("entry_id"): str,
        vol.Required("time"): TIME_RE,
        vol.Optional("days", default=list(WEEKDAYS)): [vol.In(WEEKDAYS)],
    }
)
@callback
def ws_add_start_time(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Append a start time to a sequential setup."""
    entry = _entry(hass, msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Unknown setup")
        return
    options = dict(entry.options)
    starts = _start_times(options)
    starts.append({CONF_TIME: msg["time"][:5], CONF_DAYS: msg["days"] or list(WEEKDAYS)})
    options[CONF_START_TIMES] = starts
    options.pop(CONF_START_TIME, None)
    hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"], _setup_payload(hass, entry))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/setup/start_time/remove",
        vol.Required("entry_id"): str,
        vol.Required("index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)
@callback
def ws_remove_start_time(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove a start time from a sequential setup by index."""
    entry = _entry(hass, msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Unknown setup")
        return
    options = dict(entry.options)
    starts = _start_times(options)
    index = msg["index"]
    if 0 <= index < len(starts):
        del starts[index]
    options[CONF_START_TIMES] = starts
    options.pop(CONF_START_TIME, None)
    hass.config_entries.async_update_entry(entry, options=options)
    connection.send_result(msg["id"], _setup_payload(hass, entry))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/skip_status",
        vol.Required("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_skip_status(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Report whether a scheduled run would currently be skipped (rain)."""
    entry = _entry(hass, msg["entry_id"])
    controller = getattr(entry, "runtime_data", None) if entry else None
    if controller is None:
        connection.send_result(msg["id"], {"would_skip": False, "reason": None})
        return
    reason = await controller.async_skip_reason()
    connection.send_result(
        msg["id"],
        {
            "would_skip": reason is not None,
            "reason": reason,
            "last_skip": controller.last_skip,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/history",
        vol.Required("entry_id"): str,
    }
)
@callback
def ws_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the setup's history events (newest first)."""
    entry = _entry(hass, msg["entry_id"])
    controller = getattr(entry, "runtime_data", None) if entry else None
    events = list(controller.history) if controller is not None else []
    meta = controller.history_meta if controller is not None else {}
    connection.send_result(
        msg["id"], {"events": list(reversed(events)), "meta": meta}
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/history_clear",
        vol.Required("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_clear_history(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Erase the setup's activity log."""
    entry = _entry(hass, msg["entry_id"])
    controller = getattr(entry, "runtime_data", None) if entry else None
    if controller is None:
        connection.send_error(msg["id"], "not_found", "Setup not ready")
        return
    await controller.async_clear_history()
    connection.send_result(msg["id"], {})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/notify_test",
        vol.Required("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_notify_test(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Send a test notification to the setup's configured target."""
    entry = _entry(hass, msg["entry_id"])
    controller = getattr(entry, "runtime_data", None) if entry else None
    if controller is None:
        connection.send_error(msg["id"], "not_found", "Setup not ready")
        return
    if await controller.async_test_notification():
        connection.send_result(msg["id"], {})
    else:
        connection.send_error(msg["id"], "no_target", "No notification target set")


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/setup/run",
        vol.Required("entry_id"): str,
    }
)
@callback
def ws_run_setup(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Start a sequential setup's chain now."""
    entry = _entry(hass, msg["entry_id"])
    if entry is None or not hasattr(entry, "runtime_data") or entry.runtime_data is None:
        connection.send_error(msg["id"], "not_found", "Setup not ready")
        return
    entry.runtime_data.async_run_chain()
    connection.send_result(msg["id"], {})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/setup/stop",
        vol.Required("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_stop_setup(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Stop everything in a setup."""
    entry = _entry(hass, msg["entry_id"])
    if entry is None or getattr(entry, "runtime_data", None) is None:
        connection.send_error(msg["id"], "not_found", "Setup not ready")
        return
    await entry.runtime_data.async_stop_all()
    connection.send_result(msg["id"], {})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/setup/rain_delay",
        vol.Required("entry_id"): str,
        # hours > 0 sets a delay; 0 (or omitted) clears it.
        vol.Optional("hours", default=0): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=240)
        ),
    }
)
@websocket_api.async_response
async def ws_rain_delay(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Set or clear a manual rain delay (pause all watering)."""
    entry = _entry(hass, msg["entry_id"])
    controller = getattr(entry, "runtime_data", None) if entry else None
    if controller is None:
        connection.send_error(msg["id"], "not_found", "Setup not ready")
        return
    if msg["hours"] > 0:
        await controller.async_set_rain_delay(msg["hours"])
    else:
        await controller.async_clear_rain_delay()
    connection.send_result(msg["id"], _setup_payload(hass, entry))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/zone/start",
        vol.Required("entry_id"): str,
        vol.Required("zone_id"): str,
        vol.Optional("duration"): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_DURATION, max=MAX_DURATION)
        ),
    }
)
@websocket_api.async_response
async def ws_start_zone(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Start a zone now, optionally for a custom duration (minutes)."""
    entry = _entry(hass, msg["entry_id"])
    controller = getattr(entry, "runtime_data", None) if entry else None
    if controller is None or controller.get_zone(msg["zone_id"]) is None:
        connection.send_error(msg["id"], "not_found", "Unknown zone")
        return
    await controller.async_start_zone(
        msg["zone_id"], duration=msg.get("duration"), source="manual"
    )
    connection.send_result(msg["id"], {})


# ----- zone (subentry) commands -------------------------------------------------


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/zone/add",
        vol.Required("entry_id"): str,
        vol.Required("name"): vol.All(str, vol.Length(min=1)),
        vol.Required("switch_entity"): str,
        vol.Optional("duration", default=DEFAULT_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_DURATION, max=MAX_DURATION)
        ),
        vol.Optional("cycles"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_CYCLES)
        ),
        vol.Optional("soak"): vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_SOAK)),
        vol.Optional("pre_script"): vol.Any(str, None),
        vol.Optional("post_script"): vol.Any(str, None),
    }
)
@callback
def ws_add_zone(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Create a new zone subentry in a setup."""
    entry = _entry(hass, msg["entry_id"])
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Unknown setup")
        return

    data: dict[str, Any] = {
        CONF_NAME: msg["name"],
        CONF_SWITCH_ENTITY: msg["switch_entity"],
        CONF_DURATION: msg["duration"],
        CONF_SCHEDULES: [],
    }
    if msg.get("cycles") is not None:
        data[CONF_CYCLES] = msg["cycles"]
    if msg.get("soak") is not None:
        data[CONF_SOAK] = msg["soak"]
    if msg.get("pre_script"):
        data[CONF_PRE_SCRIPT] = msg["pre_script"]
    if msg.get("post_script"):
        data[CONF_POST_SCRIPT] = msg["post_script"]

    subentry = ConfigSubentry(
        data=MappingProxyType(data),
        subentry_type=SUBENTRY_TYPE_ZONE,
        title=msg["name"],
        unique_id=None,
    )
    hass.config_entries.async_add_subentry(entry, subentry)
    connection.send_result(
        msg["id"], _zone_payload(hass, entry.entry_id, subentry.subentry_id, data)
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/zone/update",
        vol.Required("entry_id"): str,
        vol.Required("zone_id"): str,
        vol.Optional("name"): vol.All(str, vol.Length(min=1)),
        vol.Optional("enabled"): bool,
        vol.Optional("switch_entity"): str,
        vol.Optional("duration"): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_DURATION, max=MAX_DURATION)
        ),
        vol.Optional("cycles"): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=MAX_CYCLES)
        ),
        vol.Optional("soak"): vol.All(vol.Coerce(int), vol.Range(min=0, max=MAX_SOAK)),
        vol.Optional("pre_script"): vol.Any(str, None),
        vol.Optional("post_script"): vol.Any(str, None),
    }
)
@callback
def ws_update_zone(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Update fields on a zone subentry."""
    entry = _entry(hass, msg["entry_id"])
    subentry = entry.subentries.get(msg["zone_id"]) if entry else None
    if entry is None or subentry is None:
        connection.send_error(msg["id"], "not_found", "Unknown zone")
        return

    data = dict(subentry.data)
    if "enabled" in msg:
        data[CONF_ENABLED] = bool(msg["enabled"])
    for key in (
        CONF_NAME,
        CONF_SWITCH_ENTITY,
        CONF_DURATION,
        CONF_CYCLES,
        CONF_SOAK,
        CONF_PRE_SCRIPT,
        CONF_POST_SCRIPT,
    ):
        if key in msg:
            if msg[key] in (None, ""):
                data.pop(key, None)
            else:
                data[key] = msg[key]

    hass.config_entries.async_update_subentry(
        entry, subentry, data=data, title=data.get(CONF_NAME, subentry.title)
    )
    connection.send_result(
        msg["id"], _zone_payload(hass, entry.entry_id, msg["zone_id"], data)
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/zone/delete",
        vol.Required("entry_id"): str,
        vol.Required("zone_id"): str,
    }
)
@callback
def ws_delete_zone(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Delete a zone subentry."""
    entry = _entry(hass, msg["entry_id"])
    if entry is None or msg["zone_id"] not in entry.subentries:
        connection.send_error(msg["id"], "not_found", "Unknown zone")
        return
    hass.config_entries.async_remove_subentry(entry, msg["zone_id"])
    connection.send_result(msg["id"], {"zone_id": msg["zone_id"]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/schedule/add",
        vol.Required("entry_id"): str,
        vol.Required("zone_id"): str,
        vol.Required("time"): TIME_RE,
        vol.Optional("days", default=list(WEEKDAYS)): [vol.In(WEEKDAYS)],
    }
)
@callback
def ws_add_schedule(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Append a schedule to a zone."""
    entry = _entry(hass, msg["entry_id"])
    subentry = entry.subentries.get(msg["zone_id"]) if entry else None
    if entry is None or subentry is None:
        connection.send_error(msg["id"], "not_found", "Unknown zone")
        return

    data = dict(subentry.data)
    schedules = list(data.get(CONF_SCHEDULES, []))
    schedules.append(
        {CONF_TIME: msg["time"][:5], CONF_DAYS: msg["days"] or list(WEEKDAYS)}
    )
    data[CONF_SCHEDULES] = schedules
    hass.config_entries.async_update_subentry(entry, subentry, data=data)
    connection.send_result(
        msg["id"], _zone_payload(hass, entry.entry_id, msg["zone_id"], data)
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/schedule/remove",
        vol.Required("entry_id"): str,
        vol.Required("zone_id"): str,
        vol.Required("index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)
@callback
def ws_remove_schedule(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Remove a schedule from a zone by index."""
    entry = _entry(hass, msg["entry_id"])
    subentry = entry.subentries.get(msg["zone_id"]) if entry else None
    if entry is None or subentry is None:
        connection.send_error(msg["id"], "not_found", "Unknown zone")
        return

    data = dict(subentry.data)
    schedules = list(data.get(CONF_SCHEDULES, []))
    index = msg["index"]
    if 0 <= index < len(schedules):
        del schedules[index]
    data[CONF_SCHEDULES] = schedules
    hass.config_entries.async_update_subentry(entry, subentry, data=data)
    connection.send_result(
        msg["id"], _zone_payload(hass, entry.entry_id, msg["zone_id"], data)
    )
