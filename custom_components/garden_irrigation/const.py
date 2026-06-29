"""Constants for the Garden Irrigation integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "garden_irrigation"

PLATFORMS = [Platform.SWITCH, Platform.SENSOR]

# Subentry types
SUBENTRY_TYPE_ZONE = "zone"

# Config / option keys
CONF_MODE = "mode"  # scheduling mode of a setup: sequential | specific
CONF_START_TIME = "start_time"  # legacy single start time (migrated to start_times)
CONF_START_TIMES = "start_times"  # sequential setups: list of {time, days}
CONF_NAME = "name"
CONF_SWITCH_ENTITY = "switch_entity"
CONF_DURATION = "duration"  # minutes
CONF_SCHEDULES = "schedules"  # specific setups: per-zone schedules
CONF_TIME = "time"
CONF_DAYS = "days"
CONF_PRE_SCRIPT = "pre_script"
CONF_POST_SCRIPT = "post_script"
CONF_ENABLED = "enabled"  # soft enable/disable for a setup or a zone

# Cycle & soak (per zone) — split a run into N bursts with soak gaps
CONF_CYCLES = "cycles"  # number of on-cycles per run (1 = continuous)
CONF_SOAK = "soak"  # soak minutes between cycles
DEFAULT_CYCLES = 1
DEFAULT_SOAK = 0
MAX_CYCLES = 6
MAX_SOAK = 60

# Seasonal adjustment (per setup) — scales every zone's duration
CONF_SEASONAL_ADJUST = "seasonal_adjust"  # percent (100 = no change)
DEFAULT_SEASONAL_ADJUST = 100
MIN_SEASONAL_ADJUST = 0
MAX_SEASONAL_ADJUST = 200

# Master valve / pump (per setup) — opens while any zone in the setup runs
CONF_MASTER_ENTITY = "master_entity"  # switch / valve / input_boolean
CONF_MASTER_LEAD = "master_lead"  # seconds to wait after opening before a zone
DEFAULT_MASTER_LEAD = 0
MAX_MASTER_LEAD = 120

# Freeze skip (per setup; scheduled runs only)
CONF_FREEZE_ENABLED = "freeze_enabled"
CONF_FREEZE_ENTITY = "freeze_entity"  # temperature sensor / weather
CONF_FREEZE_THRESHOLD = "freeze_threshold"  # skip if at/below this temperature
DEFAULT_FREEZE_THRESHOLD = 2.0

# Soil-moisture skip (per setup; scheduled runs only)
CONF_SOIL_ENABLED = "soil_enabled"
CONF_SOIL_ENTITY = "soil_entity"  # moisture sensor (%)
CONF_SOIL_THRESHOLD = "soil_threshold"  # skip if at/above this moisture
DEFAULT_SOIL_THRESHOLD = 40.0

# Flow / leak monitoring (per setup)
CONF_FLOW_ENABLED = "flow_enabled"
CONF_FLOW_ENTITY = "flow_entity"  # flow-rate sensor
CONF_FLOW_MIN = "flow_min"  # expected minimum flow while a zone runs
DEFAULT_FLOW_MIN = 0.5
CONF_NOTIFY_FLOW = "notify_flow"  # notify on a flow anomaly (no-flow / leak)

# Manual rain delay (pause all watering until a timestamp); stored in state Store
STATE_RAIN_DELAY_UNTIL = "rain_delay_until"

# Notifications (per setup)
CONF_NOTIFY_ENABLED = "notify_enabled"  # legacy (migrated)
CONF_NOTIFY_TARGET = "notify_target"  # legacy single target (migrated)
CONF_NOTIFY_TARGETS = "notify_targets"  # list of notify entities/services
CONF_NOTIFY_OFF_FAILED = "notify_off_failed"  # valve didn't close (critical)
CONF_NOTIFY_START_FAILED = "notify_start_failed"  # zone failed to start
CONF_NOTIFY_SKIP = "notify_skip"  # scheduled run skipped (rain)

# Rain skip (per setup; applies to scheduled runs only)
CONF_RAIN_ENABLED = "rain_enabled"  # toggle the "has rained" check
CONF_RAIN_ENTITY = "rain_entity"  # sensor / weather / binary_sensor
CONF_RAIN_HOURS = "rain_hours"
CONF_RAIN_THRESHOLD = "rain_threshold"  # mm
CONF_FORECAST_ENABLED = "forecast_enabled"  # toggle the "will rain" check
CONF_FORECAST_ENTITY = "forecast_entity"  # weather entity
CONF_FORECAST_HOURS = "forecast_hours"
CONF_FORECAST_THRESHOLD = "forecast_threshold"  # %

DEFAULT_RAIN_HOURS = 12
DEFAULT_RAIN_THRESHOLD = 1.0
DEFAULT_FORECAST_HOURS = 6
DEFAULT_FORECAST_THRESHOLD = 60

SKIP_RECENT = "rain_recent"
SKIP_FORECAST = "rain_forecast"
SKIP_FREEZE = "freeze"
SKIP_SOIL = "soil_wet"
SKIP_RAIN_DELAY = "rain_delay"
EVENT_SKIPPED = f"{DOMAIN}_skipped"

# Scheduling modes
MODE_SEQUENTIAL = "sequential"  # one setup start time; zones run back-to-back
MODE_SPECIFIC = "specific"  # each zone has its own schedule(s)
DEFAULT_MODE = MODE_SPECIFIC
MODES = [MODE_SEQUENTIAL, MODE_SPECIFIC]

DEFAULT_START_TIME = "06:00"

# Duration bounds (minutes)
MIN_DURATION = 1
MAX_DURATION = 60
DEFAULT_DURATION = 10

# Weekdays (index matches datetime.weekday(): Mon=0 .. Sun=6)
WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
WEEKDAY_LABELS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}

# Repairs
ISSUE_OVERLAP = "schedule_overlap"
ISSUE_COLLISION = "start_collision"

# Services
SERVICE_STOP_ALL = "stop_all"
SERVICE_START = "start"
SERVICE_STOP = "stop"
ATTR_DURATION = "duration"

# Dispatcher signal template
SIGNAL_UPDATE = f"{DOMAIN}_update"
