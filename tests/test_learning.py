"""Learning must be passive, fresh, single-room and cancellable."""

import asyncio
from unittest.mock import patch

import pytest
from homeassistant.exceptions import ServiceValidationError


async def test_learning_ignores_cached_setter_and_geometry(hass, loaded, sources, text_calls):
    runtime = loaded.runtime_data
    task = hass.async_create_background_task(runtime.learn(), "test learning")
    await asyncio.sleep(0)
    assert not task.done()  # The existing valid Kitchen report is not accepted.
    hass.states.async_set(sources[1].entity_id, "qgAEFQEBAxo=", {"max": 256})
    await hass.async_block_till_done()
    assert not task.done()  # Attribute-only changes are not fresh selections.
    hass.states.async_set(sources[1].entity_id, "qgAEFAEBAxk=")
    await hass.async_block_till_done()
    assert not task.done()
    with pytest.raises(ServiceValidationError):
        await runtime.send("qgAEFAEBAxk=")
    assert await runtime.learn() == (None, "learning_busy")
    hass.states.async_set(sources[1].entity_id, "qgAFFQECAwId")
    await hass.async_block_till_done()
    assert not task.done()
    hass.states.async_set(sources[1].entity_id, "qgAEFQEBAxqqABQbAQAEAp4BSgNmAUoDZv6EAp7+hMw=")
    assert await task == (3, None)
    assert runtime.learning is None
    assert runtime._learn_unsub is None
    assert not text_calls


async def test_timeout_cleanup(hass, loaded):
    with patch("custom_components.lubluelu_room_cleaning.runtime.LEARN_TIMEOUT", 0.01):
        assert await loaded.runtime_data.learn() == (None, "learning_timeout")
    assert loaded.runtime_data.learning is None
    assert loaded.runtime_data._learn_unsub is None


async def test_unload_cancels_learning(hass, loaded):
    runtime = loaded.runtime_data
    task = hass.async_create_background_task(runtime.learn(), "test learning")
    await asyncio.sleep(0)
    await hass.config_entries.async_unload(loaded.entry_id)
    with pytest.raises(asyncio.CancelledError):
        await task
    assert runtime._learn_unsub is None
    assert runtime.learning is None
