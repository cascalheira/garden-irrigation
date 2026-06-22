"""Config, options and zone-subentry flows for Garden Irrigation."""

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
    CONF_MODE,
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
    MODES,
    SUBENTRY_TYPE_ZONE,
    WEEKDAYS,
    WEEKDAY_LABELS,
)
from .util import compute_overlaps, format_days

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


class GardenIrrigationConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of the integration."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Create the single hub entry."""
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        if user_input is not None:
            return self.async_create_entry(
                title="Garden Irrigation",
                data={},
                options={CONF_MODE: user_input[CONF_MODE]},
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_MODE, default=DEFAULT_MODE): MODE_SELECTOR}
            ),
        )

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
    """Allow switching the watering mode after setup."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={CONF_MODE: user_input[CONF_MODE]})

        current = self.config_entry.options.get(CONF_MODE, DEFAULT_MODE)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Required(CONF_MODE, default=current): MODE_SELECTOR}
            ),
        )


class ZoneSubentryFlowHandler(ConfigSubentryFlow):
    """Add or reconfigure a single irrigation zone, including its schedules."""

    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._schedules: list[dict[str, Any]] = []
        self._is_new = True

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
        return await self.async_step_menu()

    # ----- steps -----------------------------------------------------------------

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> SubentryFlowResult:
        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_menu()

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
        data = {**self._data, CONF_SCHEDULES: self._schedules}
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
        """Return a discreet overlap warning, comparing this zone against the others."""
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
