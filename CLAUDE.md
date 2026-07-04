# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Home Assistant custom integration ("Garden Irrigation", domain `garden_irrigation`) distributed via HACS. All code lives in `custom_components/garden_irrigation/`. Pure Python + one vanilla-JS Lovelace card — **no build step, no tests, no linter config, no dependencies** (`requirements: []` in manifest.json). Minimum HA version is in `hacs.json` (currently 2025.6.0).

## Conventions

- **Bump `version` in `manifest.json` in every commit that changes the card JS** (patch bump, e.g. 0.20.5 → 0.20.6). The card is served at `/garden_irrigation/garden-irrigation-card.js?v=<version>` (`__init__.py`), so a stale version means users keep a cached card.
- To try changes: copy `custom_components/garden_irrigation` into an HA `config/custom_components/` and restart HA (or reload the integration for Python-only changes; a restart is needed for `__init__.py`/websocket registration changes).
- Commit messages follow the existing style: short imperative summary, body explaining the user-visible behaviour.

## Architecture

### Data model — config entries and subentries

- One **config entry per "setup"** (e.g. "Garden", "Trees"). All setup-level settings (scheduling mode, start times, rain/freeze/soil skip, master valve, flow monitoring, notifications, seasonal adjust, enabled) live in `entry.options`.
- Each **zone is a config subentry** (`subentry_type == "zone"`) whose `data` holds name, switch entity, duration, per-zone schedules, pre/post scripts, cycles/soak, enabled.
- All keys and bounds are defined in `const.py`. Some keys are legacy and migrated on read (`start_time` → `start_times`, `notify_target` → `notify_targets`) — preserve that handling when touching options.
- **Any options or subentry change reloads the config entry** (`_async_update_listener` in `__init__.py`), which cleanly stops in-progress runs. Mutations never poke the running controller directly; they write config and rely on the reload.

### Runtime — `coordinator.py`

`IrrigationController` (one per config entry, stored in `entry.runtime_data`) owns everything at runtime: schedule registration (`async_track_time_change`), the sequential run chain (one cancellable asyncio task) vs. per-zone independent runs, cycle/soak splitting, master-valve refcounting, skip evaluation (rain/forecast/freeze/soil/rain-delay — scheduled runs only, manual always waters), verified-off retry logic (`_async_ensure_off`), flow/leak watchdogs, and notifications. It persists three `Store`s per entry: history log, runtime state (rain delay), and per-zone watering totals.

Entities (`switch.py` `ZoneSwitch`, `sensor.py` remaining/total sensors) are **thin views over the controller** — they hold no state and re-render on the dispatcher signal `SIGNAL_UPDATE` + entry_id, which the controller fires via `_notify()` on every state change.

### Two parallel configuration UIs — keep them in sync

The same setup/zone/schedule CRUD is exposed twice, and both write the same `entry.options` / subentry shapes:

1. **`config_flow.py`** — HA-native config flow, options flow, and `ZoneSubentryFlowHandler` (Settings → Devices & Services).
2. **`websocket_api.py`** — admin-only websocket commands (`garden_irrigation/get`, `add_zone`, `update_setup`, …) backing the Lovelace card. Validation bounds here must match `const.py` and the config flow.

When adding a setting, it typically touches: `const.py`, both UIs above, `coordinator.py` (behaviour), the card JS (editor UI + `STR` translations), and `strings.json` + `translations/en.json`/`pt.json`.

### The card — `www/garden-irrigation-card.js`

A single ~3500-line plain custom element (`GardenIrrigationCard`), no framework, no build. Registered automatically at startup via `add_extra_js_url` (`__init__.py`) — users never add a Lovelace resource. It reads live run state from the zone switch entities' attributes (so it updates in real time) and performs all mutations over the websocket commands. **Card UI strings are localised inline** in the `STR`/`DAY_SHORT`/`DAY_LABEL` tables (en + pt) at the top of the file — every new user-facing string needs both languages there (integration/config-flow strings instead go in `strings.json` + `translations/`). All time UI is forced 24-hour.

### Shared pure helpers — `util.py`

`compute_next_run`, `compute_overlaps` (specific-mode schedule overlaps), and `compute_start_collisions` (sequential start times closer than the total sequence length). Used by the coordinator (which raises HA repair issues `schedule_overlap` / `start_collision`), the config flow (blocking/warning), and the websocket API — overlap/collision behaviour must stay consistent across all three.
