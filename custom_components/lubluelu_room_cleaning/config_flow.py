"""Setup and explicitly confirmed passive room learning."""

from copy import deepcopy

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import CONF_COMMAND, CONF_MAP, CONF_PROTOCOL, CONF_ROOMS, CONF_VACUUM, DOMAIN
from .protocol import InvalidReport, single_room
from .runtime import source_pair


def source_schema():
    """Select only entities exposed by Tuya Local; ownership is checked too."""
    return vol.Schema(
        {
            vol.Required("vacuum"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="vacuum", integration="tuya_local")
            ),
            vol.Required("command"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain="text", integration="tuya_local")
            ),
        }
    )


class RoomCleaningFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Configure a source pair without probing or starting the vacuum."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                vacuum, command = source_pair(
                    self.hass, user_input["vacuum"], user_input["command"]
                )
            except ValueError:
                errors["base"] = "invalid_sources"
            else:
                await self.async_set_unique_id(vacuum.id)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=vacuum.name or vacuum.original_name or "Vacuum rooms",
                    data={CONF_VACUUM: vacuum.id, CONF_COMMAND: command.id},
                    options={CONF_ROOMS: {}, CONF_PROTOCOL: False, CONF_MAP: 0},
                )
        return self.async_show_form(step_id="user", data_schema=source_schema(), errors=errors)

    async def async_step_reconfigure(self, user_input=None):
        entry = self._get_reconfigure_entry()
        errors = {}
        if user_input is not None:
            try:
                vacuum, command = source_pair(
                    self.hass, user_input["vacuum"], user_input["command"]
                )
            except ValueError:
                errors["base"] = "invalid_sources"
            else:
                if any(
                    other.entry_id != entry.entry_id and other.unique_id == vacuum.id
                    for other in self._async_current_entries()
                ):
                    errors["base"] = "already_configured"
                else:
                    options = dict(entry.options)
                    if (vacuum.id, command.id) != (
                        entry.data[CONF_VACUUM],
                        entry.data[CONF_COMMAND],
                    ):
                        options = {
                            CONF_ROOMS: {},
                            CONF_PROTOCOL: False,
                            CONF_MAP: entry.options.get(CONF_MAP, 0) + 1,
                        }
                    return self.async_update_reload_and_abort(
                        entry,
                        unique_id=vacuum.id,
                        data={CONF_VACUUM: vacuum.id, CONF_COMMAND: command.id},
                        options=options,
                    )
        return self.async_show_form(
            step_id="reconfigure", data_schema=source_schema(), errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return RoomOptionsFlow()


class RoomOptionsFlow(config_entries.OptionsFlow):
    """Manage room IDs without leaving background learning listeners alive."""

    def __init__(self):
        self._task = None
        self._room = None
        self._name = ""
        self._options = None

    @property
    def options(self):
        if self._options is None:
            self._options = deepcopy(dict(self.config_entry.options))
        return self._options

    def _name_error(self, name, room=None):
        if not name.strip() or len(name.strip()) > 128:
            return "invalid_name"
        if any(
            existing.casefold() == name.strip().casefold() and key != str(room)
            for key, existing in self.options.get(CONF_ROOMS, {}).items()
        ):
            return "duplicate_name"
        return None

    async def async_step_init(self, user_input=None):
        # Options are configuration only: never sends commands.
        return self.async_show_menu(
            step_id="init", menu_options=["learn", "manual", "edit", "delete", "reset"]
        )

    async def async_step_learn(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._name = user_input["name"].strip()
            if not self._name:
                errors["base"] = "invalid_name"
            elif not hasattr(self.config_entry, "runtime_data"):
                errors["base"] = "source_unavailable"
            else:
                return await self.async_step_listen()
        return self.async_show_form(
            step_id="learn", data_schema=vol.Schema({vol.Required("name"): str}), errors=errors
        )

    async def async_step_listen(self, user_input=None):
        if self._task is None:
            self._task = self.hass.async_create_background_task(
                self.config_entry.runtime_data.learn(), "Learn vacuum room"
            )
        if not self._task.done():
            return self.async_show_progress(
                step_id="listen",
                progress_action="listen",
                progress_task=self._task,
                description_placeholders={"name": self._name},
            )
        if self._task.cancelled():
            return self.async_abort(reason="learning_cancelled")
        self._room, error = self._task.result()
        self._task = None
        self._learn_error = error
        return self.async_show_progress_done(next_step_id="learn_failed" if error else "confirm")

    async def async_step_learn_failed(self, user_input=None):
        return self.async_show_menu(
            step_id="learn_failed",
            menu_options=["learn", "manual"],
            description_placeholders={
                "reason": {
                    "multiple_rooms": "More than one room was selected. Select only one room.",
                    "learning_busy": "Another learning session is already listening.",
                    "source_unavailable": "The Tuya Local command entity is unavailable.",
                    "learning_timeout": "No fresh single-room report arrived within two minutes.",
                }.get(self._learn_error, "Learning could not finish.")
            },
        )

    async def async_step_manual(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._name = user_input["name"].strip()
            raw = user_input["room_or_report"].strip()
            try:
                if raw.isascii() and raw.isdecimal():
                    if len(raw) > 3:
                        raise InvalidReport("invalid_room")
                    self._room = int(raw)
                    if not 0 <= self._room <= 255:
                        raise InvalidReport("invalid_room")
                    if not user_input.get("confirm_protocol"):
                        raise InvalidReport("confirm_protocol")
                else:
                    self._room = single_room(raw)
                error = self._name_error(self._name, self._room)
                if error:
                    errors["base"] = error
                else:
                    return await self.async_step_confirm()
            except InvalidReport as err:
                errors["base"] = str(err)
        return self.async_show_form(
            step_id="manual",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("room_or_report"): str,
                    vol.Required("confirm_protocol", default=False): bool,
                }
            ),
            errors=errors,
        )

    async def async_step_confirm(self, user_input=None):
        errors = {}
        error = self._name_error(self._name, self._room)
        if error:
            # Allow the name to be corrected after a capture, without re-learning.
            errors["base"] = error
        if user_input is not None:
            self._name = user_input["name"].strip()
            if error := self._name_error(self._name, self._room):
                errors["base"] = error
            else:
                self.options.setdefault(CONF_ROOMS, {})[str(self._room)] = self._name
                self.options[CONF_PROTOCOL] = True
                return self.async_create_entry(title="", data=self.options)
        previous = self.options.get(CONF_ROOMS, {}).get(str(self._room), "—")
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema({vol.Required("name", default=self._name): str}),
            description_placeholders={"room": str(self._room), "previous": previous},
            errors=errors,
        )

    def _room_selector(self):
        return selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": room, "label": f"{name} (ID {room})"}
                    for room, name in self.options.get(CONF_ROOMS, {}).items()
                ]
            )
        )

    async def async_step_edit(self, user_input=None):
        if not self.options.get(CONF_ROOMS):
            return self.async_abort(reason="no_rooms")
        if user_input is not None:
            room = user_input["room"]
            if room not in self.options[CONF_ROOMS]:
                return self.async_abort(reason="no_rooms")
            self._room, self._name = int(room), self.options[CONF_ROOMS][room]
            return await self.async_step_confirm()
        return self.async_show_form(
            step_id="edit", data_schema=vol.Schema({vol.Required("room"): self._room_selector()})
        )

    async def async_step_delete(self, user_input=None):
        if not self.options.get(CONF_ROOMS):
            return self.async_abort(reason="no_rooms")
        if user_input is not None:
            self.options[CONF_ROOMS].pop(user_input["room"], None)
            return self.async_create_entry(title="", data=self.options)
        return self.async_show_form(
            step_id="delete", data_schema=vol.Schema({vol.Required("room"): self._room_selector()})
        )

    async def async_step_reset(self, user_input=None):
        if user_input is not None:
            self.options.update(
                {
                    CONF_ROOMS: {},
                    CONF_PROTOCOL: False,
                    CONF_MAP: self.options.get(CONF_MAP, 0) + 1,
                }
            )
            return self.async_create_entry(title="", data=self.options)
        return self.async_show_form(step_id="reset", data_schema=vol.Schema({}))

    @callback
    def async_remove(self):
        if self._task and not self._task.done():
            self._task.cancel()
        super().async_remove()
