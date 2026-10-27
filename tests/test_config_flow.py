"""Configuration and options flows never operate hardware."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er

from custom_components.lubluelu_room_cleaning.const import (
    CONF_MAP,
    CONF_PROTOCOL,
    CONF_ROOMS,
    DOMAIN,
)


async def test_setup_and_duplicate(hass, sources):
    hass.states.async_set(sources[0].entity_id, "docked", {"friendly_name": "Simulated SL60D"})
    data = {"vacuum": sources[0].entity_id, "command": sources[1].entity_id}
    with patch("custom_components.lubluelu_room_cleaning.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        result = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "Simulated SL60D"
        assert not result["options"][CONF_PROTOCOL]
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=data
        )
        assert result["reason"] == "already_configured"


async def test_invalid_source(hass, sources):
    er.async_get(hass).async_update_entity(
        sources[1].entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            "vacuum": sources[0].entity_id,
            "command": sources[1].entity_id,
        },
    )
    assert result["errors"] == {"base": "invalid_sources"}


async def test_manual_requires_confirmation_and_saves(hass, loaded, text_calls):
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Study",
            "room_or_report": "4",
            "confirm_protocol": False,
        },
    )
    assert result["errors"]["base"] == "confirm_protocol"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Study",
            "room_or_report": "4",
            "confirm_protocol": True,
        },
    )
    assert result["step_id"] == "confirm"
    assert "4" not in loaded.options[CONF_ROOMS]
    result = await hass.config_entries.options.async_configure(flow_id, {"name": "Study"})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert loaded.options[CONF_ROOMS]["4"] == "Study"
    assert not text_calls


async def test_pasted_report_and_duplicate_name(hass, loaded):
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "manual"}
    )
    flow_id = result["flow_id"]
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Corridor",
            "room_or_report": "qgAEFQEBAxo=",
            "confirm_protocol": False,
        },
    )
    assert result["errors"]["base"] == "duplicate_name"
    result = await hass.config_entries.options.async_configure(
        flow_id,
        {
            "name": "Kitchen renamed",
            "room_or_report": "qgAEFQEBAxo=",
            "confirm_protocol": False,
        },
    )
    assert result["step_id"] == "confirm"
    await hass.config_entries.options.async_configure(flow_id, {"name": "Kitchen renamed"})
    await hass.async_block_till_done()
    assert loaded.options[CONF_ROOMS]["3"] == "Kitchen renamed"
    assert len(loaded.options[CONF_ROOMS]) == 2


async def test_reset_invalidates_old_map(hass, loaded):
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "reset"}
    )
    assert loaded.options[CONF_ROOMS]
    await hass.config_entries.options.async_configure(result["flow_id"], {})
    await hass.async_block_till_done()
    assert loaded.options[CONF_ROOMS] == {}
    assert loaded.options[CONF_MAP] == 1
    assert not loaded.options[CONF_PROTOCOL]


async def test_guided_cancel_cleans_listener(hass, loaded):
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "learn"}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"name": "Study"})
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    assert loaded.runtime_data.learning is not None
    hass.config_entries.options.async_abort(result["flow_id"])
    await hass.async_block_till_done()
    assert loaded.runtime_data.learning is None
    assert loaded.runtime_data._learn_unsub is None


async def test_guided_capture_requires_confirmation(hass, loaded, sources, text_calls):
    result = await hass.config_entries.options.async_init(loaded.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "learn"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Kitchen updated"}
    )
    flow_id = result["flow_id"]
    await hass.async_block_till_done()
    hass.states.async_set(sources[1].entity_id, "qgAEFQEBAxqqABQbAQAEAp4BSgNmAUoDZv6EAp7+hMw=")
    await hass.async_block_till_done()
    result = await hass.config_entries.options.async_configure(flow_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert loaded.options[CONF_ROOMS]["3"] == "Kitchen"
    await hass.config_entries.options.async_configure(flow_id, {"name": "Kitchen updated"})
    await hass.async_block_till_done()
    assert loaded.options[CONF_ROOMS]["3"] == "Kitchen updated"
    assert not text_calls
