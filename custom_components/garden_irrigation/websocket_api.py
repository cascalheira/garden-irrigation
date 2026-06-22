"""Websocket commands backing the Garden Irrigation Lovelace card.

These expose zone/schedule CRUD so the custom card can manage the same config
subentries that the config-flow UI manages. All mutations require an admin user
and trigger a reload of the config entry via the update listener.
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
    CONF_DAYS,
    CONF_DURATION,
    CONF_NAME,
    CONF_POST_SCRIPT,
    CONF_PRE_SCRIPT,
    CONF_SCHEDULES,
    CONF_SWITCH_ENTITY,
    CONF_TIME,
    DEFAULT_DURATION,
    DEFAULT_MODE,
    DOMAIN,
    MAX_DURATION,
    MIN_DURATION,
    CONF_MODE,
    SUBENTRY_TYPE_ZONE,
    WEEKDAYS,
)

TIME_RE = vol.Match(r"^([01]?\d|2[0-3]):[0-5]\d")


@callback
def async_register_websocket_commands(hass: HomeAssistant) -> None:
    """Register all websocket commands (called once from async_setup)."""
    websocket_api.async_register_command(hass, ws_get)
    websocket_api.async_register_command(hass, ws_add_zone)
    websocket_api.async_register_command(hass, ws_update_zone)
    websocket_api.async_register_command(hass, ws_delete_zone)
    websocket_api.async_register_command(hass, ws_add_schedule)
    websocket_api.async_register_command(hass, ws_remove_schedule)


@callback
def _get_entry(hass: HomeAssistant) -> ConfigEntry | None:
    """Return the (single) Garden Irrigation config entry, loaded or not."""
    entries = hass.config_entries.async_entries(DOMAIN)
    return entries[0] if entries else None


@callback
def _zone_payload(
    hass: HomeAssistant, subentry_id: str, data: dict[str, Any]
) -> dict[str, Any]:
    """Build the JSON payload describing one zone for the card."""
    ent_reg = er.async_get(hass)
    return {
        "zone_id": subentry_id,
        "name": data.get(CONF_NAME),
        "switch_entity": data.get(CONF_SWITCH_ENTITY),
        "duration": int(data.get(CONF_DURATION, DEFAULT_DURATION)),
        "schedules": list(data.get(CONF_SCHEDULES, [])),
        "pre_script": data.get(CONF_PRE_SCRIPT),
        "post_script": data.get(CONF_POST_SCRIPT),
        "entity_id": ent_reg.async_get_entity_id("switch", DOMAIN, subentry_id),
        "sensor_entity_id": ent_reg.async_get_entity_id(
            "sensor", DOMAIN, f"{subentry_id}_remaining"
        ),
    }


@websocket_api.websocket_command({vol.Required("type"): "garden_irrigation/get"})
@callback
def ws_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the integration config (mode + zones) for the card."""
    entry = _get_entry(hass)
    if entry is None:
        connection.send_result(msg["id"], {"configured": False, "zones": []})
        return

    zones = [
        _zone_payload(hass, sid, dict(sub.data))
        for sid, sub in entry.subentries.items()
        if sub.subentry_type == SUBENTRY_TYPE_ZONE
    ]
    connection.send_result(
        msg["id"],
        {
            "configured": True,
            "entry_id": entry.entry_id,
            "mode": entry.options.get(CONF_MODE, DEFAULT_MODE),
            "zones": zones,
        },
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/zone/add",
        vol.Required("name"): vol.All(str, vol.Length(min=1)),
        vol.Required("switch_entity"): str,
        vol.Optional("duration", default=DEFAULT_DURATION): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_DURATION, max=MAX_DURATION)
        ),
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
    """Create a new zone subentry."""
    entry = _get_entry(hass)
    if entry is None:
        connection.send_error(msg["id"], "not_configured", "Integration not set up")
        return

    data: dict[str, Any] = {
        CONF_NAME: msg["name"],
        CONF_SWITCH_ENTITY: msg["switch_entity"],
        CONF_DURATION: msg["duration"],
        CONF_SCHEDULES: [],
    }
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
        msg["id"], _zone_payload(hass, subentry.subentry_id, data)
    )


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/zone/update",
        vol.Required("zone_id"): str,
        vol.Optional("name"): vol.All(str, vol.Length(min=1)),
        vol.Optional("switch_entity"): str,
        vol.Optional("duration"): vol.All(
            vol.Coerce(int), vol.Range(min=MIN_DURATION, max=MAX_DURATION)
        ),
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
    """Update fields on an existing zone subentry."""
    entry = _get_entry(hass)
    subentry = entry.subentries.get(msg["zone_id"]) if entry else None
    if entry is None or subentry is None:
        connection.send_error(msg["id"], "not_found", "Unknown zone")
        return

    data = dict(subentry.data)
    for key in (
        CONF_NAME,
        CONF_SWITCH_ENTITY,
        CONF_DURATION,
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
    connection.send_result(msg["id"], _zone_payload(hass, msg["zone_id"], data))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/zone/delete",
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
    entry = _get_entry(hass)
    if entry is None or msg["zone_id"] not in entry.subentries:
        connection.send_error(msg["id"], "not_found", "Unknown zone")
        return

    hass.config_entries.async_remove_subentry(entry, msg["zone_id"])
    connection.send_result(msg["id"], {"zone_id": msg["zone_id"]})


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/schedule/add",
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
    entry = _get_entry(hass)
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
    connection.send_result(msg["id"], _zone_payload(hass, msg["zone_id"], data))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "garden_irrigation/schedule/remove",
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
    entry = _get_entry(hass)
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
    connection.send_result(msg["id"], _zone_payload(hass, msg["zone_id"], data))
