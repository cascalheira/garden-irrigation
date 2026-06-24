"""Config, options and zone-subentry flows for Garden Irrigation.

Each config entry is one *setup* (e.g. "Garden", "Trees"). Multiple setups are
allowed. A setup is either ``sequential`` (single start time, zones run in order)
or ``specific`` (each zone has its own schedules).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    ConfigSubentryFlow,
    OptionsFlow,
    SubentryFlowResult,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    CONF_DAYS,
    CONF_DURATION,
    CONF_FORECAST_ENABLED,
    CONF_FORECAST_ENTITY,
    CONF_FORECAST_HOURS,
    CONF_FORECAST_THRESHOLD,
    CONF_MODE,
    CONF_NAME,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_TARGET,
    CONF_POST_SCRIPT,
    CONF_PRE_SCRIPT,
    CONF_RAIN_ENABLED,
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
    DEFAULT_START_TIME,
    DOMAIN,
    MAX_DURATION,
    MIN_DURATION,
    MODE_SEQUENTIAL,
    MODE_SPECIFIC,
    MODES,
    SUBENTRY_TYPE_ZONE,
    WEEKDAYS,
    WEEKDAY_LABELS,
)
from .util import compute_overlaps, compute_start_collisions, format_days

MODE_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=MODES,
        translation_key="mode",
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

DAYS_SELECTOR = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=[
            selector.SelectOptionDict(value=day, label=WEEKDAY_LABELS[day])
            for day in WEEKDAYS
        ],
        multiple=True,
        mode=selector.SelectSelectorMode.LIST,
    )
)

DURATION_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=MIN_DURATION,
        max=MAX_DURATION,
        step=1,
        unit_of_measurement="min",
        mode=selector.NumberSelectorMode.BOX,
    )
)

SCRIPT_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="script")
)

RAIN_ENTITY_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain=["sensor", "weather", "binary_sensor"])
)

WEATHER_SELECTOR = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="weather")
)

HOURS_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=1, max=72, step=1, unit_of_measurement="h", mode=selector.NumberSelectorMode.BOX
    )
)

MM_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, max=50, step=0.1, unit_of_measurement="mm", mode=selector.NumberSelectorMode.BOX
    )
)

PERCENT_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0, max=100, step=5, unit_of_measurement="%", mode=selector.NumberSelectorMode.SLIDER
    )
)


def _settings_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_SWITCH_ENTITY): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch", "input_boolean"])
            ),
            vol.Required(CONF_DURATION, default=DEFAULT_DURATION): DURATION_SELECTOR,
            vol.Optional(CONF_PRE_SCRIPT): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
            vol.Optional(CONF_POST_SCRIPT): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="script")
            ),
        }
    )


def _sequential_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_START_TIME, default=defaults.get(CONF_START_TIME, DEFAULT_START_TIME)
            ): selector.TimeSelector(),
            vol.Required(
                CONF_DAYS, default=defaults.get(CONF_DAYS, list(WEEKDAYS))
            ): DAYS_SELECTOR,
            vol.Optional(CONF_PRE_SCRIPT): SCRIPT_SELECTOR,
            vol.Optional(CONF_POST_SCRIPT): SCRIPT_SELECTOR,
        }
    )


class GardenIrrigationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create irrigation setups (multiple allowed)."""

    VERSION = 1

    def __init__(self) -> None:
        self._setup: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 1: name + scheduling mode."""
        if user_input is not None:
            self._setup = dict(user_input)
            if user_input[CONF_MODE] == MODE_SEQUENTIAL:
                return await self.async_step_sequential()
            return self._create()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default="Garden"): selector.TextSelector(),
                    vol.Required(CONF_MODE, default=DEFAULT_MODE): MODE_SELECTOR,
                }
            ),
        )

    async def async_step_sequential(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Step 2 (sequential only): start time + days."""
        if user_input is not None:
            self._setup.update(user_input)
            return self._create()

        return self.async_show_form(
            step_id="sequential", data_schema=_sequential_schema({})
        )

    async def async_step_import(
        self, import_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create a setup programmatically (used by the card)."""
        self._setup = dict(import_data)
        return self._create()

    @callback
    def _create(self) -> ConfigFlowResult:
        name = self._setup.get(CONF_NAME, "Garden")
        options: dict[str, Any] = {CONF_MODE: self._setup.get(CONF_MODE, DEFAULT_MODE)}
        if options[CONF_MODE] == MODE_SEQUENTIAL:
            options[CONF_START_TIMES] = [
                {
                    CONF_TIME: self._setup.get(CONF_START_TIME, DEFAULT_START_TIME)[:5],
                    CONF_DAYS: self._setup.get(CONF_DAYS, list(WEEKDAYS)),
                }
            ]
            if self._setup.get(CONF_PRE_SCRIPT):
                options[CONF_PRE_SCRIPT] = self._setup[CONF_PRE_SCRIPT]
            if self._setup.get(CONF_POST_SCRIPT):
                options[CONF_POST_SCRIPT] = self._setup[CONF_POST_SCRIPT]
        return self.async_create_entry(title=name, data={}, options=options)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return OptionsFlowHandler()

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls, config_entry: ConfigEntry
    ) -> dict[str, type[ConfigSubentryFlow]]:
        return {SUBENTRY_TYPE_ZONE: ZoneSubentryFlowHandler}


class OptionsFlowHandler(OptionsFlow):
    """Edit a setup: scheduling mode, sequential start times (multiple) and scripts."""

    def __init__(self) -> None:
        self._opts: dict[str, Any] = {}
        self._starts: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        self._opts = dict(self.config_entry.options)
        self._starts = _starts_from_options(self._opts)
        return await self.async_step_menu()

    async def async_step_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if self._opts.get(CONF_MODE, DEFAULT_MODE) != MODE_SEQUENTIAL:
            # Specific setups have no setup-level start times/scripts to manage.
            return await self.async_step_settings()

        menu_options = ["settings", "add_start"]
        if self._starts:
            menu_options.append("remove_start")
        menu_options.append("finish")
        return self.async_show_menu(
            step_id="menu",
            menu_options=menu_options,
            description_placeholders={
                "summary": self._summary(),
                "warning": self._warning(),
            },
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._opts[CONF_MODE] = user_input[CONF_MODE]
            for key in (
                CONF_PRE_SCRIPT,
                CONF_POST_SCRIPT,
                CONF_RAIN_ENTITY,
                CONF_FORECAST_ENTITY,
            ):
                if user_input.get(key):
                    self._opts[key] = user_input[key]
                else:
                    self._opts.pop(key, None)
            for key in (
                CONF_RAIN_HOURS,
                CONF_RAIN_THRESHOLD,
                CONF_FORECAST_HOURS,
                CONF_FORECAST_THRESHOLD,
            ):
                if user_input.get(key) is not None:
                    self._opts[key] = user_input[key]
            for key in (CONF_RAIN_ENABLED, CONF_FORECAST_ENABLED):
                self._opts[key] = bool(user_input.get(key, True))
            self._opts[CONF_NOTIFY_ENABLED] = bool(
                user_input.get(CONF_NOTIFY_ENABLED, False)
            )
            if user_input.get(CONF_NOTIFY_TARGET):
                self._opts[CONF_NOTIFY_TARGET] = user_input[CONF_NOTIFY_TARGET]
            else:
                self._opts.pop(CONF_NOTIFY_TARGET, None)
            if user_input[CONF_MODE] != MODE_SEQUENTIAL:
                return await self.async_step_finish()
            return await self.async_step_menu()

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_MODE, default=self._opts.get(CONF_MODE, DEFAULT_MODE)
                ): MODE_SELECTOR,
                vol.Optional(CONF_PRE_SCRIPT): SCRIPT_SELECTOR,
                vol.Optional(CONF_POST_SCRIPT): SCRIPT_SELECTOR,
                vol.Optional(
                    CONF_RAIN_ENABLED,
                    default=self._opts.get(CONF_RAIN_ENABLED, True),
                ): selector.BooleanSelector(),
                vol.Optional(CONF_RAIN_ENTITY): RAIN_ENTITY_SELECTOR,
                vol.Optional(
                    CONF_RAIN_HOURS,
                    default=self._opts.get(CONF_RAIN_HOURS, DEFAULT_RAIN_HOURS),
                ): HOURS_SELECTOR,
                vol.Optional(
                    CONF_RAIN_THRESHOLD,
                    default=self._opts.get(CONF_RAIN_THRESHOLD, DEFAULT_RAIN_THRESHOLD),
                ): MM_SELECTOR,
                vol.Optional(
                    CONF_FORECAST_ENABLED,
                    default=self._opts.get(CONF_FORECAST_ENABLED, True),
                ): selector.BooleanSelector(),
                vol.Optional(CONF_FORECAST_ENTITY): WEATHER_SELECTOR,
                vol.Optional(
                    CONF_FORECAST_HOURS,
                    default=self._opts.get(CONF_FORECAST_HOURS, DEFAULT_FORECAST_HOURS),
                ): HOURS_SELECTOR,
                vol.Optional(
                    CONF_FORECAST_THRESHOLD,
                    default=self._opts.get(
                        CONF_FORECAST_THRESHOLD, DEFAULT_FORECAST_THRESHOLD
                    ),
                ): PERCENT_SELECTOR,
                vol.Optional(
                    CONF_NOTIFY_ENABLED,
                    default=self._opts.get(CONF_NOTIFY_ENABLED, False),
                ): selector.BooleanSelector(),
                vol.Optional(CONF_NOTIFY_TARGET): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="notify")
                ),
            }
        )
        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(schema, self._opts),
        )

    async def async_step_add_start(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self._starts.append(
                {CONF_TIME: user_input[CONF_TIME][:5], CONF_DAYS: user_input[CONF_DAYS]}
            )
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="add_start",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_TIME, default=DEFAULT_START_TIME
                    ): selector.TimeSelector(),
                    vol.Required(CONF_DAYS, default=list(WEEKDAYS)): DAYS_SELECTOR,
                }
            ),
        )

    async def async_step_remove_start(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            for index in sorted(
                (int(i) for i in user_input[CONF_START_TIMES]), reverse=True
            ):
                if 0 <= index < len(self._starts):
                    del self._starts[index]
            return await self.async_step_menu()

        options = [
            selector.SelectOptionDict(
                value=str(index),
                label=f"{s[CONF_TIME]} — {format_days(s.get(CONF_DAYS, []))}",
            )
            for index, s in enumerate(self._starts)
        ]
        return self.async_show_form(
            step_id="remove_start",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_START_TIMES): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        new_options: dict[str, Any] = {CONF_MODE: self._opts.get(CONF_MODE, DEFAULT_MODE)}
        if new_options[CONF_MODE] == MODE_SEQUENTIAL:
            new_options[CONF_START_TIMES] = self._starts or [
                {CONF_TIME: DEFAULT_START_TIME, CONF_DAYS: list(WEEKDAYS)}
            ]
            for key in (CONF_PRE_SCRIPT, CONF_POST_SCRIPT):
                if self._opts.get(key):
                    new_options[key] = self._opts[key]
        # Rain skip applies to both modes.
        for key in (
            CONF_RAIN_ENABLED,
            CONF_RAIN_ENTITY,
            CONF_RAIN_HOURS,
            CONF_RAIN_THRESHOLD,
            CONF_FORECAST_ENABLED,
            CONF_FORECAST_ENTITY,
            CONF_FORECAST_HOURS,
            CONF_FORECAST_THRESHOLD,
            CONF_NOTIFY_ENABLED,
            CONF_NOTIFY_TARGET,
        ):
            if self._opts.get(key) not in (None, ""):
                new_options[key] = self._opts[key]
        return self.async_create_entry(data=new_options)

    def _summary(self) -> str:
        if not self._starts:
            return "No start times yet."
        lines = ["Start times:"]
        lines.extend(
            f"• {s[CONF_TIME]} — {format_days(s.get(CONF_DAYS, []))}"
            for s in self._starts
        )
        return "\n".join(lines)

    def _warning(self) -> str:
        total = sum(
            int(sub.data.get(CONF_DURATION, 0))
            for sub in self.config_entry.subentries.values()
            if sub.subentry_type == SUBENTRY_TYPE_ZONE
        )
        collisions = compute_start_collisions(self._starts, total)
        if not collisions:
            return ""
        return "⚠️ Colliding start times (sequence is " + str(total) + " min):\n" + "\n".join(
            f"• {c}" for c in collisions
        )


def _starts_from_options(options: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the sequential start times, migrating a legacy single time."""
    times = options.get(CONF_START_TIMES)
    if times:
        return [dict(s) for s in times]
    legacy = options.get(CONF_START_TIME)
    if legacy:
        return [
            {CONF_TIME: legacy[:5], CONF_DAYS: options.get(CONF_DAYS, list(WEEKDAYS))}
        ]
    return []


class ZoneSubentryFlowHandler(ConfigSubentryFlow):
    """Add or reconfigure a zone. Schedules apply only in 'specific' mode."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._schedules: list[dict[str, Any]] = []
        self._is_new = True

    @property
    def _is_specific(self) -> bool:
        return self._get_entry().options.get(CONF_MODE, DEFAULT_MODE) == MODE_SPECIFIC

    # ----- entry points ----------------------------------------------------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        self._is_new = True
        self._data = {}
        self._schedules = []
        return await self.async_step_settings()

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        self._is_new = False
        subentry = self._get_reconfigure_subentry()
        self._data = {k: v for k, v in subentry.data.items() if k != CONF_SCHEDULES}
        self._schedules = [dict(s) for s in subentry.data.get(CONF_SCHEDULES, [])]
        if self._is_specific:
            return await self.async_step_menu()
        return await self.async_step_settings()

    # ----- steps -----------------------------------------------------------------

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            if self._is_specific:
                return await self.async_step_menu()
            return await self.async_step_finish()

        return self.async_show_form(
            step_id="settings",
            data_schema=self.add_suggested_values_to_schema(
                _settings_schema(), self._data
            ),
        )

    async def async_step_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        menu_options = ["settings", "add_schedule"]
        if self._schedules:
            menu_options.append("remove_schedule")
        menu_options.append("finish")

        return self.async_show_menu(
            step_id="menu",
            menu_options=menu_options,
            description_placeholders={
                "summary": self._summary(),
                "warning": self._warning(),
            },
        )

    async def async_step_add_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            self._schedules.append(
                {
                    CONF_TIME: user_input[CONF_TIME][:5],
                    CONF_DAYS: user_input[CONF_DAYS],
                }
            )
            return await self.async_step_menu()

        return self.async_show_form(
            step_id="add_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_TIME): selector.TimeSelector(),
                    vol.Required(CONF_DAYS, default=list(WEEKDAYS)): DAYS_SELECTOR,
                }
            ),
        )

    async def async_step_remove_schedule(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            for index in sorted(
                (int(i) for i in user_input[CONF_SCHEDULES]), reverse=True
            ):
                if 0 <= index < len(self._schedules):
                    del self._schedules[index]
            return await self.async_step_menu()

        options = [
            selector.SelectOptionDict(
                value=str(index),
                label=f"{sched[CONF_TIME]} — {format_days(sched.get(CONF_DAYS, []))}",
            )
            for index, sched in enumerate(self._schedules)
        ]
        return self.async_show_form(
            step_id="remove_schedule",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCHEDULES): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=options,
                            multiple=True,
                            mode=selector.SelectSelectorMode.LIST,
                        )
                    )
                }
            ),
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        data = {**self._data}
        if self._is_specific:
            data[CONF_SCHEDULES] = self._schedules
        title = data[CONF_NAME]

        if self._is_new:
            return self.async_create_entry(title=title, data=data)

        return self.async_update_and_abort(
            self._get_entry(),
            self._get_reconfigure_subentry(),
            title=title,
            data=data,
        )

    # ----- helpers ---------------------------------------------------------------

    def _summary(self) -> str:
        name = self._data.get(CONF_NAME, "Zone")
        duration = self._data.get(CONF_DURATION, DEFAULT_DURATION)
        lines = [f"**{name}** — {int(duration)} min per run"]
        if self._schedules:
            lines.append("Schedules:")
            lines.extend(
                f"• {s[CONF_TIME]} — {format_days(s.get(CONF_DAYS, []))}"
                for s in self._schedules
            )
        else:
            lines.append("No schedules yet.")
        return "\n".join(lines)

    def _warning(self) -> str:
        """Discreet overlap warning comparing this zone against the others."""
        if not self._schedules:
            return ""

        zones = [
            {
                CONF_NAME: self._data.get(CONF_NAME, "This zone"),
                CONF_DURATION: int(self._data.get(CONF_DURATION, DEFAULT_DURATION)),
                CONF_SCHEDULES: self._schedules,
            }
        ]

        current_id = None
        if not self._is_new:
            current_id = self._get_reconfigure_subentry().subentry_id

        for sid, sub in self._get_entry().subentries.items():
            if sub.subentry_type != SUBENTRY_TYPE_ZONE or sid == current_id:
                continue
            zones.append(
                {
                    CONF_NAME: sub.data.get(CONF_NAME, "Zone"),
                    CONF_DURATION: int(sub.data.get(CONF_DURATION, DEFAULT_DURATION)),
                    CONF_SCHEDULES: sub.data.get(CONF_SCHEDULES, []),
                }
            )

        overlaps = compute_overlaps(zones)
        if not overlaps:
            return ""
        return "⚠️ Overlapping schedules:\n" + "\n".join(f"• {o}" for o in overlaps)
