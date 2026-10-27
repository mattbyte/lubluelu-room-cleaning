"""Lubluelu room cleaning through existing Tuya Local entities."""

from homeassistant.const import Platform
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .runtime import Runtime

PLATFORMS = [Platform.VACUUM]


async def async_setup_entry(hass, entry) -> bool:
    """Load the companion without reading Tuya configuration or credentials."""
    entry.runtime_data = Runtime(hass, entry)
    entry.runtime_data.start()
    entry.async_on_unload(entry.runtime_data.stop)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_updated))
    return True


async def _updated(hass, entry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry) -> bool:
    """Unload entities; HA runs the registered listener cleanup."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass, entry) -> None:
    """Remove integration-owned repairs when deleting its configuration."""
    ir.async_delete_issue(hass, DOMAIN, f"sources_{entry.entry_id}")
