"""Companion vacuum with native Home Assistant room selection."""

from homeassistant.components.vacuum import (
    Segment,
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_MAP, CONF_PROTOCOL, CONF_ROOMS
from .protocol import encode_rooms
from .runtime import service_error

PARALLEL_UPDATES = 1
FORWARDED = (
    VacuumEntityFeature.START
    | VacuumEntityFeature.STOP
    | VacuumEntityFeature.PAUSE
    | VacuumEntityFeature.RETURN_HOME
    | VacuumEntityFeature.LOCATE
    | VacuumEntityFeature.CLEAN_SPOT
    | VacuumEntityFeature.FAN_SPEED
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Add the companion vacuum."""
    async_add_entities([RoomVacuum(entry)])


class RoomVacuum(StateVacuumEntity):
    """Expose native segments while keeping the source vacuum authoritative."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_translation_key = "room_cleaning"
    _attr_name = "Room cleaning"

    def __init__(self, entry) -> None:
        self.entry = entry
        self.runtime = entry.runtime_data
        self._attr_unique_id = f"{entry.entry_id}_vacuum"
        source = self.runtime.sources()[0]
        device = dr.async_get(self.runtime.hass).async_get(source.device_id) if source else None
        if device:
            self._attr_device_info = DeviceInfo(
                identifiers=device.identifiers, connections=device.connections
            )
        else:
            self._attr_name = f"{entry.title} room cleaning"

    @property
    def available(self):
        return self.runtime.valid_sources() and self.runtime.state(0) is not None

    @property
    def activity(self):
        state = self.runtime.state(0)
        if state:
            try:
                return VacuumActivity(state.state)
            except ValueError:
                return None
        return None

    @property
    def supported_features(self):
        source = self.runtime.state(0)
        features = VacuumEntityFeature.STATE
        if source:
            features |= (
                VacuumEntityFeature(source.attributes.get("supported_features", 0)) & FORWARDED
            )
        if self.entry.options.get(CONF_PROTOCOL) and self.entry.options.get(CONF_ROOMS):
            features |= VacuumEntityFeature.CLEAN_AREA
        return features

    @property
    def fan_speed(self):
        state = self.runtime.state(0)
        return state.attributes.get("fan_speed") if state else None

    @property
    def fan_speed_list(self):
        state = self.runtime.state(0)
        return state.attributes.get("fan_speed_list", []) if state else []

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.runtime.listeners.add(self._updated)
        self.async_on_remove(lambda: self.runtime.listeners.discard(self._updated))
        self._check_mapping()

    @callback
    def _updated(self):
        self.async_write_ha_state()

    def _segments(self):
        revision = self.entry.options.get(CONF_MAP, 0)
        return [
            Segment(id=f"{revision}:{room}", name=name)
            for room, name in self.entry.options.get(CONF_ROOMS, {}).items()
        ]

    @callback
    def _check_mapping(self):
        previous = self.last_seen_segments
        if previous is not None and previous != self._segments():
            self.async_create_segments_issue()

    async def async_get_segments(self):
        return self._segments()

    async def async_clean_segments(self, segment_ids, **kwargs):
        valid = {segment.id for segment in self._segments()}
        if (
            not self.entry.options.get(CONF_PROTOCOL)
            or not segment_ids
            or any(segment not in valid for segment in segment_ids)
        ):
            raise service_error("invalid_selection")
        payload = encode_rooms([int(segment.split(":")[1]) for segment in segment_ids])
        await self.runtime.send(payload, self._context)

    async def async_start(self):
        await self.runtime.forward("start", {}, self._context)

    async def async_stop(self, **kwargs):
        await self.runtime.forward("stop", {}, self._context)

    async def async_pause(self):
        await self.runtime.forward("pause", {}, self._context)

    async def async_return_to_base(self, **kwargs):
        await self.runtime.forward("return_to_base", {}, self._context)

    async def async_locate(self, **kwargs):
        await self.runtime.forward("locate", {}, self._context)

    async def async_clean_spot(self, **kwargs):
        await self.runtime.forward("clean_spot", {}, self._context)

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        await self.runtime.forward("set_fan_speed", {"fan_speed": fan_speed}, self._context)
