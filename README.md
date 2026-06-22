# Garden Irrigation for Home Assistant

A UI-configured custom integration for controlling garden irrigation zones driven
by relays / smart switches. Built around Home Assistant's native entities, devices
and services — no YAML required.

## Features

- **Multiple zones**, each mapped to a `switch` (or `input_boolean`) and a run
  duration of **1–60 minutes**.
- **Schedules in the UI** — add as many start times per zone as you like, each with
  its own days of the week.
- **Two watering modes:**
  - **Sequential** — one zone at a time; concurrent requests queue automatically.
  - **Parallel** — zones may run simultaneously.
- **Discreet overlap warning** — when schedules overlap you get a non-blocking
  warning while editing *and* a Home Assistant repair issue.
- **Manual activation** — every zone is a switch entity you can toggle from any
  dashboard, plus `garden_irrigation.start` (with optional duration override).
- **Stop in progress** — turn the zone switch off, call `garden_irrigation.stop`,
  or `garden_irrigation.stop_all`. Works for scheduled and manual runs alike.
- **Pre / post scripts** — run and await a `script` entity before the valve opens
  and after it closes (open main supply, send a notification, etc.).
- A **Time remaining** sensor per zone, with `next_run` and run metadata exposed as
  attributes.

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS (type: *Integration*).
2. Install **Garden Irrigation** and restart Home Assistant.

### Manual

Copy `custom_components/garden_irrigation` into your Home Assistant `config/custom_components/`
directory and restart.

## Setup

1. **Settings → Devices & Services → Add Integration → Garden Irrigation.**
2. Choose the watering mode (you can change it later under the integration's *Configure*).
3. On the integration, use **Add zone** to create each zone:
   - Name, switch entity, run duration, optional pre/post scripts.
   - Add one or more schedules (start time + days).
4. Reconfigure a zone any time to edit its settings or schedules.

## Dashboard card

The integration ships a custom Lovelace card that adds/deletes zones, edits run
duration, and manages schedules — all from the dashboard. The card JS is served
and registered automatically (no manual *Resources* entry needed).

Add it to a dashboard:

```yaml
type: custom:garden-irrigation-card
title: Garden watering   # optional
```

From the card you can:

- **Add zone** — name + switch picker + duration.
- **Delete zone** (trash icon).
- **Duration** slider (1–60 min) — released value is saved.
- **Schedules** — add a time (applies every day) or remove with the chip's ✕.
  For per-day schedules, use the zone's *Reconfigure* dialog.
- **Run now / Stop**, with a live countdown and a "Watering · scheduled/manual"
  badge on the active zone.

> The card talks to the integration over admin-only websocket commands and reads
> live run state from each zone's switch entity, so it updates in real time.

## Services

| Service | Description |
| --- | --- |
| `garden_irrigation.start` | Start a zone switch now, optional `duration` (minutes) override. |
| `garden_irrigation.stop` | Stop a zone switch and remove it from the queue. |
| `garden_irrigation.stop_all` | Stop every running zone and clear the queue. |

You can also `switch.turn_on` / `switch.turn_off` each zone entity directly.

## Notes

- Changing options or zones reloads the integration; any in-progress run is stopped
  cleanly (valve closed, post-script run).
- The pre/post scripts are awaited, so a sequential run only opens the valve after
  the pre-script completes.
