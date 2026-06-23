# Garden Irrigation for Home Assistant

A UI-configured custom integration for controlling garden irrigation zones driven
by relays / smart switches. Built around Home Assistant's native entities, devices
and services — no YAML required.

## Features

- **Multiple setups** — create as many independent setups as you like (e.g.
  "Garden" and "Trees"). Each setup is a config entry with its own zones and
  scheduling mode.
- **Two scheduling modes per setup:**
  - **Sequential** — one or more setup start times + days; zones run back-to-back
    in order (one cancellable chain). Start times must be at least the full
    sequence length apart — collisions are blocked when adding and flagged with a
    discreet warning + repair issue.
  - **Specific times** — each zone has its own schedules (multiple times/days);
    zones may overlap.
- **Multiple zones**, each mapped to a `switch` (or `input_boolean`) and a run
  duration of **1–60 minutes**.
- **Discreet overlap warning** — in *specific* mode, overlapping schedules raise a
  non-blocking warning while editing *and* a Home Assistant repair issue.
- **Rain skip** (per setup, scheduled runs only) — skip watering if it **rained
  recently** (a precipitation/weather/binary sensor over a look-back window) or if
  there's a **high chance of rain soon** (a weather entity's hourly forecast).
  Either condition shows a **warning on the card** before the run and fires a
  `garden_irrigation_skipped` event. Manual runs always water.
- **Manual activation** — every zone is a switch entity you can toggle from any
  dashboard, plus `garden_irrigation.start` (with optional duration override).
- **Stop in progress** — turn the zone switch off, call `garden_irrigation.stop`,
  or `garden_irrigation.stop_all`. Stopping a chained zone stops the whole chain.
- **Pre / post scripts** — run and await a `script` entity before the valve opens
  and after it closes (open main supply, send a notification, etc.). Per-zone in
  any setup, plus **setup-level** pre/post scripts for *sequential* setups that
  run once around the whole sequence.
- A **Time remaining** sensor per zone, with `next_run` and run metadata exposed as
  attributes.
- A **dashboard card** with view/edit modes that manages setups, zones and
  schedules (24-hour time pickers). Localised in **English** and
  **European Portuguese** (follows your Home Assistant language).

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
mode: view               # "view" (default) or "edit"
setup: Garden            # optional — pin to a setup by name or entry_id
title: Garden watering   # optional fallback only; the setup name is shown when loaded
```

The header shows the **setup name** (rename it inline in edit mode). `title` is
only used as a fallback before a setup loads.

The card has two modes (toggle with the **Edit / Done** button):

- **View mode** — a compact, read-only layout: each zone shows its duration and
  schedule times (or position in a sequence), with only **Run / Stop**. A running
  zone shows a live **progress bar** and time remaining. No editing controls. For
  sequential setups, **Run sequence** sits below the last zone.
- **Edit mode** — configuration only (no per-zone Run button); rename the setup
  inline, and edit everything:
  - **Add zone** / **Add setup** (only visible in edit mode)
  - **Delete** zone or setup
  - the zone's **switch** and **pre/post scripts** (shown and editable)
  - the setup's **scheduling-mode toggle** (sequential ⇄ specific) and, for
    sequential, the **start time + days** editor

When more than one setup exists, a dropdown in the header switches between them.
All time fields are **24-hour**. A live countdown and a
"Watering · scheduled/manual" badge appear on the active zone.

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
