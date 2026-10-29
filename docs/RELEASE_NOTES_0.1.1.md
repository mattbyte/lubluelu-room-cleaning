# 0.1.1

Fix scheduled room cleaning being rejected after a Home Assistant restart or Tuya
Local reconnect when the vacuum is available but its command text value is
`unknown`. The command entity no longer needs to receive a room report before
the integration can write a room-cleaning command. Passive room learning can
also begin from an unknown value and still requires a fresh, valid report.

- Keep blocking missing or explicitly unavailable source states, invalid source
  pairs, and an unknown vacuum state.
- Distinguish source configuration errors, vacuum unavailability, and command
  entity unavailability in action errors.
- Preserve existing learned rooms, native area mappings, payload limits, and the
  single-command behavior without automatic retries.

Validation: 64 tests pass on Home Assistant 2026.10.0 and 2026.10.4, with 91%
statement coverage. Ruff lint and formatting checks pass. The GitHub validation
workflow checks both HA versions, Hassfest, and HACS before publication.

Automated tests use simulated entities and never connect to a physical vacuum.
This fix has not been deployed to or physically verified on the user's vacuum.

After updating through HACS, restart Home Assistant. Existing rooms and area
mappings are retained; no reconfiguration or relearning is required for this fix.
