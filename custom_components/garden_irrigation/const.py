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

# Rain skip (per setup; applies to scheduled runs only)
CONF_RAIN_ENTITY = "rain_entity"  # sensor / weather / binary_sensor
CONF_RAIN_HOURS = "rain_hours"
CONF_RAIN_THRESHOLD = "rain_threshold"  # mm
CONF_FORECAST_ENTITY = "forecast_entity"  # weather entity
CONF_FORECAST_HOURS = "forecast_hours"
CONF_FORECAST_THRESHOLD = "forecast_threshold"  # %

DEFAULT_RAIN_HOURS = 12
DEFAULT_RAIN_THRESHOLD = 1.0
DEFAULT_FORECAST_HOURS = 6
DEFAULT_FORECAST_THRESHOLD = 60

SKIP_RECENT = "rain_recent"
SKIP_FORECAST = "rain_forecast"
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
