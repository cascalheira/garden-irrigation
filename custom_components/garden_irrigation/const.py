"""Constants for the Garden Irrigation integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "garden_irrigation"

PLATFORMS = [Platform.SWITCH, Platform.SENSOR]

# Subentry types
SUBENTRY_TYPE_ZONE = "zone"

# Config / option keys
CONF_MODE = "mode"
CONF_NAME = "name"
CONF_SWITCH_ENTITY = "switch_entity"
CONF_DURATION = "duration"  # minutes
CONF_SCHEDULES = "schedules"
CONF_TIME = "time"
CONF_DAYS = "days"
CONF_PRE_SCRIPT = "pre_script"
CONF_POST_SCRIPT = "post_script"

# Watering modes
MODE_SEQUENTIAL = "sequential"
MODE_PARALLEL = "parallel"
DEFAULT_MODE = MODE_SEQUENTIAL
MODES = [MODE_SEQUENTIAL, MODE_PARALLEL]

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

# Services
SERVICE_STOP_ALL = "stop_all"
SERVICE_START = "start"
SERVICE_STOP = "stop"
ATTR_DURATION = "duration"

# Dispatcher signal template
SIGNAL_UPDATE = f"{DOMAIN}_update"
