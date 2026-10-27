"""Allowlisted diagnostics; never serialize source entries or raw reports."""

from .const import CONF_PROTOCOL, CONF_ROOMS


async def async_get_config_entry_diagnostics(hass, entry):
    """Return operational flags only, excluding identifiers and room names."""
    runtime = entry.runtime_data
    return {
        "config_version": entry.version,
        "room_count": len(entry.options.get(CONF_ROOMS, {})),
        "protocol_confirmed": bool(entry.options.get(CONF_PROTOCOL)),
        "sources_valid": runtime.valid_sources(),
        "vacuum_available": runtime.state(0) is not None,
        "command_available": runtime.state(1) is not None,
        "learning": runtime.learning is not None,
    }
