"""Native HA area dispatch and precisely one transport write."""

import pytest
from homeassistant.components.vacuum import VacuumEntityFeature
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.lubluelu_room_cleaning.const import DOMAIN
from custom_components.lubluelu_room_cleaning.diagnostics import async_get_config_entry_diagnostics


def companion(hass, entry):
    entity_id = er.async_get(hass).async_get_entity_id("vacuum", DOMAIN, f"{entry.entry_id}_vacuum")
    return hass.data["vacuum"].get_entity(entity_id)


@pytest.mark.parametrize("command_state", ["qgAEFQEBAxo=", "unknown"])
async def test_native_area_dispatch(hass, loaded, sources, text_calls, command_state):
    hass.states.async_set(sources[1].entity_id, command_state, {"max": 255})
    assert await hass.config_entries.async_reload(loaded.entry_id)
    await hass.async_block_till_done()
    entity = companion(hass, loaded)
    kitchen = ar.async_get(hass).async_create("Kitchen")
    corridor = ar.async_get(hass).async_create("Corridor")
    er.async_get(hass).async_update_entity_options(
        entity.entity_id,
        "vacuum",
        {
            "area_mapping": {kitchen.id: ["0:3"], corridor.id: ["0:2"]},
            "last_seen_segments": [
                {"id": "0:3", "name": "Kitchen"},
                {"id": "0:2", "name": "Corridor"},
            ],
        },
    )
    start_calls = async_mock_service(hass, "vacuum", "start")
    await hass.services.async_call(
        "vacuum",
        "clean_area",
        {
            "entity_id": entity.entity_id,
            "cleaning_area_id": [kitchen.id, corridor.id],
        },
        blocking=True,
    )
    assert len(text_calls) == 1
    assert text_calls[0].data == {"entity_id": sources[1].entity_id, "value": "qgAFFAECAwIc"}
    assert not start_calls
    assert [(segment.id, segment.name) for segment in await entity.async_get_segments()] == [
        ("0:3", "Kitchen"),
        ("0:2", "Corridor"),
    ]


async def test_single_room_and_stale_mapping(hass, loaded, text_calls):
    entity = companion(hass, loaded)
    await entity.async_clean_segments(["0:3", "0:3"])
    assert text_calls[0].data["value"] == "qgAEFAEBAxk="
    for ids in ([], ["0:99"], ["1:3"], ["0:3", "0:99"]):
        with pytest.raises(ServiceValidationError):
            await entity.async_clean_segments(ids)
    assert len(text_calls) == 1


async def test_unavailable_and_oversized(hass, loaded, sources, text_calls):
    entity = companion(hass, loaded)
    hass.states.async_set(sources[1].entity_id, "unavailable")
    with pytest.raises(ServiceValidationError):
        await entity.async_clean_segments(["0:3"])
    # Normal controls stay available when only the command text is offline.
    assert entity.available
    hass.states.async_set(sources[1].entity_id, "qgAEFQEBAxo=", {"max": 4})
    with pytest.raises(ServiceValidationError):
        await entity.async_clean_segments(["0:3"])
    assert not text_calls


@pytest.mark.parametrize(
    ("index", "source_state", "error_key"),
    [
        (0, "unknown", "vacuum_unavailable"),
        (0, "unavailable", "vacuum_unavailable"),
        (0, None, "vacuum_unavailable"),
        (1, "unavailable", "command_unavailable"),
        (1, None, "command_unavailable"),
    ],
)
async def test_unusable_source_blocks_commands(
    hass, loaded, sources, text_calls, index, source_state, error_key
):
    if source_state is None:
        hass.states.async_remove(sources[index].entity_id)
    else:
        hass.states.async_set(sources[index].entity_id, source_state)
    with pytest.raises(ServiceValidationError) as error:
        await companion(hass, loaded).async_clean_segments(["0:3"])
    assert error.value.translation_key == error_key
    assert not text_calls


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize("change", ["disabled", "removed", "moved"])
async def test_invalid_sources_block_unknown_command(
    hass, loaded, sources, text_calls, index, change
):
    hass.states.async_set(sources[1].entity_id, "unknown")
    registry = er.async_get(hass)
    entity_id = sources[index].entity_id
    if change == "disabled":
        registry.async_update_entity(entity_id, disabled_by=er.RegistryEntryDisabler.USER)
    elif change == "removed":
        registry.async_remove(entity_id)
    else:
        registry.async_update_entity(entity_id, device_id=None)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as error:
        await companion(hass, loaded).async_clean_segments(["0:3"])
    assert error.value.translation_key == "invalid_sources"
    assert not text_calls


async def test_unknown_command_still_enforces_payload_limit(hass, loaded, sources, text_calls):
    hass.states.async_set(sources[1].entity_id, "unknown", {"max": 4})
    with pytest.raises(ServiceValidationError) as error:
        await companion(hass, loaded).async_clean_segments(["0:3"])
    assert error.value.translation_key == "payload_too_long"
    assert not text_calls


async def test_forwarding_and_state(hass, loaded, sources):
    entity = companion(hass, loaded)
    calls = async_mock_service(hass, "vacuum", "pause")
    await entity.async_pause()
    assert calls[0].data == {"entity_id": sources[0].entity_id}
    hass.states.async_set(
        sources[0].entity_id, "cleaning", {"supported_features": int(VacuumEntityFeature.PAUSE)}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity.entity_id).state == "cleaning"
    assert not entity.supported_features & VacuumEntityFeature.START
    assert entity.supported_features & VacuumEntityFeature.CLEAN_AREA


async def test_entity_rename_and_removal(hass, loaded, sources, text_calls):
    registry = er.async_get(hass)
    registry.async_update_entity(sources[1].entity_id, new_entity_id="text.renamed_command")
    await hass.async_block_till_done()
    hass.states.async_set("text.renamed_command", "qgAEFQEBAxo=", {"max": 255})
    await companion(hass, loaded).async_clean_segments(["0:3"])
    assert text_calls[0].data["entity_id"] == "text.renamed_command"
    registry.async_remove("text.renamed_command")
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"sources_{loaded.entry_id}")


async def test_diagnostics_allowlist(hass, loaded):
    result = await async_get_config_entry_diagnostics(hass, loaded)
    assert set(result) == {
        "config_version",
        "room_count",
        "protocol_confirmed",
        "sources_valid",
        "vacuum_available",
        "command_available",
        "learning",
    }
    assert result["room_count"] == 2
    assert "Kitchen" not in str(result)
    assert loaded.entry_id not in str(result)


async def test_unload(hass, loaded):
    runtime = loaded.runtime_data
    assert await hass.config_entries.async_unload(loaded.entry_id)
    await hass.async_block_till_done()
    assert not runtime.listeners


async def test_native_segment_websocket(hass, loaded, hass_ws_client):
    entity = companion(hass, loaded)
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "vacuum/get_segments", "entity_id": entity.entity_id})
    message = await client.receive_json()
    assert message["success"]
    assert message["result"]["segments"] == [
        {"id": "0:3", "name": "Kitchen", "group": None},
        {"id": "0:2", "name": "Corridor", "group": None},
    ]
