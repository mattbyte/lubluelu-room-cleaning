"""Public HA entity transport and short-lived passive learning."""

import asyncio
from collections.abc import Callable
from typing import Any

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.event import async_track_state_change_event

from .const import CONF_COMMAND, CONF_VACUUM, DOMAIN, LEARN_TIMEOUT
from .protocol import InvalidReport, single_room


def service_error(key: str) -> ServiceValidationError:
    """Create a translated error without including device data."""
    return ServiceValidationError(translation_domain=DOMAIN, translation_key=key)


def source_pair(hass, vacuum_id, command_id):
    """Validate enabled Tuya Local entities on the same registered device."""
    registry = er.async_get(hass)
    vacuum = registry.async_get(vacuum_id)
    command = registry.async_get(command_id)
    if (
        vacuum is None
        or command is None
        or vacuum.domain != "vacuum"
        or command.domain != "text"
        or vacuum.platform != "tuya_local"
        or command.platform != "tuya_local"
        or vacuum.disabled
        or command.disabled
        or not vacuum.device_id
        or vacuum.device_id != command.device_id
    ):
        raise ValueError("invalid_sources")
    return vacuum, command


class Runtime:
    """One source pair, no Tuya connections and no credential access."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self.listeners: set[Callable[[], None]] = set()
        self.learning: asyncio.Future | None = None
        self.sending = False
        self._unsub_state: Callable | None = None
        self._unsub_registry: Callable | None = None
        self._learn_unsub: Callable | None = None
        self._source_entity_ids: set[str] = set()

    def sources(self):
        """Resolve stored registry IDs each time, including after renames."""
        registry = er.async_get(self.hass)
        return tuple(
            registry.async_get(self.entry.data[key]) for key in (CONF_VACUUM, CONF_COMMAND)
        )

    def valid_sources(self) -> bool:
        """Check ownership and enablement without reading source config."""
        vacuum, command = self.sources()
        try:
            source_pair(
                self.hass,
                vacuum.entity_id if vacuum else "",
                command.entity_id if command else "",
            )
        except ValueError:
            return False
        return True

    def state(self, index: int):
        """Return a usable state, allowing an unreported command text value."""
        entity = self.sources()[index]
        state = self.hass.states.get(entity.entity_id) if entity else None
        if state is None or state.state == STATE_UNAVAILABLE:
            return None
        # DP15 may not be reported after reconnecting until a room report arrives.
        # An unknown current text value does not prevent writing a new command.
        if index == 0 and state.state == STATE_UNKNOWN:
            return None
        return state

    @callback
    def start(self) -> None:
        """Subscribe to registry changes and source state changes."""
        self._unsub_registry = self.hass.bus.async_listen(
            er.EVENT_ENTITY_REGISTRY_UPDATED, self._registry_changed
        )
        self._bind()

    @callback
    def _registry_changed(self, event) -> None:
        current = {entity.entity_id for entity in self.sources() if entity}
        if event.data.get("entity_id") in current | self._source_entity_ids:
            self.cancel_learning()
            self._bind()

    @callback
    def _bind(self) -> None:
        if self._unsub_state:
            self._unsub_state()
        self._source_entity_ids = {entity.entity_id for entity in self.sources() if entity}
        self._unsub_state = async_track_state_change_event(
            self.hass,
            self._source_entity_ids,
            self._state_changed,
        )
        issue = f"sources_{self.entry.entry_id}"
        if self.valid_sources():
            ir.async_delete_issue(self.hass, DOMAIN, issue)
        else:
            ir.async_create_issue(
                self.hass,
                DOMAIN,
                issue,
                is_fixable=False,
                severity=ir.IssueSeverity.WARNING,
                translation_key="missing_sources",
            )
        self.notify()

    @callback
    def _state_changed(self, event) -> None:
        self.notify()

    @callback
    def notify(self) -> None:
        for listener in tuple(self.listeners):
            listener()

    @callback
    def cancel_learning(self) -> None:
        if self._learn_unsub:
            self._learn_unsub()
            self._learn_unsub = None
        if self.learning and not self.learning.done():
            self.learning.cancel()

    @callback
    def stop(self) -> None:
        self.cancel_learning()
        for unsubscribe in (self._unsub_state, self._unsub_registry):
            if unsubscribe:
                unsubscribe()
        self.listeners.clear()

    async def learn(self) -> tuple[int | None, str | None]:
        """Wait for a changed report; repeated cached state is not evidence."""
        if self.learning is not None or self.sending:
            return None, "learning_busy"
        if not self.valid_sources() or not self.state(1):
            return None, "source_unavailable"
        future = self.hass.loop.create_future()
        self.learning = future
        last_error = "learning_timeout"

        @callback
        def observe(event):
            nonlocal last_error
            old, new = event.data.get("old_state"), event.data.get("new_state")
            if not new or (old and old.state == new.state) or future.done():
                return
            try:
                room = single_room(new.state)
            except InvalidReport as err:
                if str(err) == "multiple_rooms":
                    last_error = "multiple_rooms"
                return
            future.set_result(room)

        self._learn_unsub = async_track_state_change_event(
            self.hass, self.sources()[1].entity_id, observe
        )
        try:
            async with asyncio.timeout(LEARN_TIMEOUT):
                return await future, None
        except TimeoutError:
            return None, last_error
        finally:
            if self._learn_unsub:
                self._learn_unsub()
                self._learn_unsub = None
            self.learning = None

    async def send(self, payload: str, context=None) -> None:
        """Send a single command; never retry a potentially accepted write."""
        if self.learning is not None:
            raise service_error("learning_busy")
        if not self.valid_sources():
            raise service_error("invalid_sources")
        if not self.state(0):
            raise service_error("vacuum_unavailable")
        state = self.state(1)
        if state is None:
            raise service_error("command_unavailable")
        if len(payload) > state.attributes.get("max", 255):
            raise service_error("payload_too_long")
        self.sending = True
        try:
            await self._call(
                "text",
                "set_value",
                {"entity_id": self.sources()[1].entity_id, "value": payload},
                context,
            )
        finally:
            self.sending = False

    async def forward(self, service: str, data: dict[str, Any], context=None):
        """Forward a normal vacuum control through its existing HA service."""
        if not self.valid_sources():
            raise service_error("invalid_sources")
        if not self.state(0):
            raise service_error("vacuum_unavailable")
        await self._call(
            "vacuum",
            service,
            {"entity_id": self.sources()[0].entity_id, **data},
            context,
        )

    async def _call(self, domain, service, data, context):
        try:
            await self.hass.services.async_call(
                domain, service, data, blocking=True, context=context
            )
        except (HomeAssistantError, TimeoutError) as err:
            raise service_error("command_failed") from err
