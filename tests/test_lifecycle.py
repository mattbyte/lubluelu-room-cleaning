"""Recovery and multi-vacuum isolation scenarios."""

import pytest
from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.lubluelu_room_cleaning.const import (
    CONF_COMMAND,
    CONF_MAP,
    CONF_PROTOCOL,
    CONF_ROOMS,
    CONF_VACUUM,
    DOMAIN,
)
from custom_components.lubluelu_room_cleaning.runtime import source_pair


async def test_foreign_device_and_platform_rejected(hass, sources):
    registry = er.async_get(hass)
    other_entry = MockConfigEntry(domain="tuya_local")
    other_entry.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("tuya_local", "second-simulated")}
    )
    other = registry.async_get_or_create(
        "text", "tuya_local", "other-command", config_entry=other_entry, device_id=device.id
    )
    with pytest.raises(ValueError):
        source_pair(hass, sources[0].entity_id, other.entity_id)
    wrong = registry.async_get_or_create(
        "text", "another_integration", "wrong-platform", device_id=sources[0].device_id
    )
    with pytest.raises(ValueError):
        source_pair(hass, sources[0].entity_id, wrong.entity_id)


@pytest.mark.parametrize("command_state", ["qgAEFQEBAxo=", "unknown"])
@pytest.mark.parametrize("exception", [HomeAssistantError, TimeoutError])
async def test_no_retry_on_transport_error(hass, loaded, sources, command_state, exception):
    hass.states.async_set(sources[1].entity_id, command_state)
    calls = []

    async def fail(call):
        calls.append(call)
        raise exception("synthetic failure")

    hass.services.async_register("text", "set_value", fail)
    with pytest.raises(ServiceValidationError) as error:
        await loaded.runtime_data.send("qgAEFAEBAxk=")
    assert error.value.translation_key == "command_failed"
    assert len(calls) == 1
    assert not loaded.runtime_data.sending


async def test_persistence_and_changed_mapping_issue(hass, loaded):
    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("vacuum", DOMAIN, f"{loaded.entry_id}_vacuum")
    registry.async_update_entity_options(
        entity_id,
        "vacuum",
        {
            "area_mapping": {"kitchen": ["0:3"]},
            "last_seen_segments": [{"id": "0:3", "name": "Old kitchen"}],
        },
    )
    assert await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done()
    assert loaded.options[CONF_ROOMS] == {"3": "Kitchen", "2": "Corridor"}
    issue_id = f"segments_changed_{registry.async_get(entity_id).id}"
    assert ir.async_get(hass).async_get_issue("vacuum", issue_id)


async def test_reconfigure_command_clears_map(hass, loaded, sources):
    new_command = er.async_get(hass).async_get_or_create(
        "text", "tuya_local", "replacement-command", device_id=sources[0].device_id
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": loaded.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "vacuum": sources[0].entity_id,
            "command": new_command.entity_id,
        },
    )
    assert result["reason"] == "reconfigure_successful"
    await hass.async_block_till_done()
    assert loaded.options[CONF_ROOMS] == {}
    assert loaded.options[CONF_MAP] == 1
    assert not loaded.options[CONF_PROTOCOL]


async def test_multiple_vacuums_isolated(hass, loaded, text_calls):
    source = MockConfigEntry(domain="tuya_local")
    source.add_to_hass(hass)
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=source.entry_id, identifiers={("tuya_local", "second-simulated")}
    )
    registry = er.async_get(hass)
    vacuum = registry.async_get_or_create(
        "vacuum", "tuya_local", "second-vacuum", device_id=device.id, config_entry=source
    )
    command = registry.async_get_or_create(
        "text", "tuya_local", "second-command", device_id=device.id, config_entry=source
    )
    hass.states.async_set(vacuum.entity_id, "idle")
    hass.states.async_set(command.entity_id, "qgAEFQEBAxo=")
    other = MockConfigEntry(
        domain=DOMAIN,
        unique_id=vacuum.id,
        data={CONF_VACUUM: vacuum.id, CONF_COMMAND: command.id},
        options={CONF_ROOMS: {"3": "Study"}, CONF_PROTOCOL: True, CONF_MAP: 2},
    )
    other.add_to_hass(hass)
    assert await hass.config_entries.async_setup(other.entry_id)
    await hass.async_block_till_done()
    entity_id = registry.async_get_entity_id("vacuum", DOMAIN, f"{other.entry_id}_vacuum")
    entity = hass.data["vacuum"].get_entity(entity_id)
    assert [(item.id, item.name) for item in await entity.async_get_segments()] == [
        ("2:3", "Study")
    ]
    await entity.async_clean_segments(["2:3"])
    assert text_calls[0].data["entity_id"] == command.entity_id
    assert loaded.options[CONF_ROOMS]["3"] == "Kitchen"
