"""Isolated HA fixtures; no Tuya library, device connection, or credentials."""

import pytest
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.lubluelu_room_cleaning.const import (
    CONF_COMMAND,
    CONF_MAP,
    CONF_PROTOCOL,
    CONF_ROOMS,
    CONF_VACUUM,
    DOMAIN,
)


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow this custom integration in the test HA instance."""


@pytest.fixture
def sources(hass):
    source_entry = MockConfigEntry(domain="tuya_local", title="Simulated vacuum")
    source_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source_entry.entry_id,
        identifiers={("tuya_local", "simulated-only")},
        name="Simulated vacuum",
    )
    registry = er.async_get(hass)
    vacuum = registry.async_get_or_create(
        "vacuum",
        "tuya_local",
        "simulated-vacuum",
        config_entry=source_entry,
        device_id=device.id,
        suggested_object_id="simulated_vacuum",
    )
    command = registry.async_get_or_create(
        "text",
        "tuya_local",
        "simulated-command",
        config_entry=source_entry,
        device_id=device.id,
        suggested_object_id="simulated_command",
    )
    hass.states.async_set(vacuum.entity_id, "docked", {"supported_features": 8191})
    hass.states.async_set(command.entity_id, "qgAEFQEBAxo=", {"max": 255})
    return vacuum, command


@pytest.fixture
def entry(hass, sources):
    vacuum, command = sources
    result = MockConfigEntry(
        domain=DOMAIN,
        unique_id=vacuum.id,
        title="Simulated vacuum",
        data={CONF_VACUUM: vacuum.id, CONF_COMMAND: command.id},
        options={CONF_ROOMS: {"3": "Kitchen", "2": "Corridor"}, CONF_PROTOCOL: True, CONF_MAP: 0},
    )
    result.add_to_hass(hass)
    return result


@pytest.fixture
async def loaded(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
def text_calls(hass):
    return async_mock_service(hass, "text", "set_value")
