# Validation

## 0.1.1

The new cleaning and learning regressions first reproduced the failures on the
unmodified runtime: native area cleaning rejected an `unknown` command value,
and passive learning returned `source_unavailable` immediately.

The fix passes 64 tests on both Home Assistant 2026.10.0 and 2026.10.4 with 91%
statement coverage. Ruff lint and formatting checks pass. Regression coverage includes:

- Native `vacuum.clean_area` after reloading the companion while the command
  text value is unknown, with exactly one transport write and no start command.
- Passive learning from unknown, accepting only a fresh valid room report.
- Missing, unavailable, disabled, removed, and separated source entities still
  preventing room commands; an unknown vacuum state still prevents commands.
- Payload limits and no automatic retries after service errors or timeouts,
  including when the initial command value is unknown.

All tests use simulated entities. No physical commands were sent and no live
Home Assistant configuration was changed during this validation.

## 0.1.0

Automated tests use synthetic Tuya Local entity-registry entries and a mocked
text transport. They never connect to Tuya or operate hardware.

- 47 tests pass on Home Assistant 2026.10.0 and 2026.10.4.
- Integration statement coverage is 91%.
- Ruff lint and formatting checks pass.
- GitHub Actions runs both HA versions, Hassfest, and HACS validation.

The isolated Home Assistant 2026.10.4 frontend was also exercised with a fake
vacuum and command text entity:

1. Select the source vacuum and command entity in the setup form.
2. Start guided learning and inject a known single-room report into the fake
   command entity.
3. Confirm and save Kitchen without sending a cleaning command.
4. Use **Map vacuum segments to areas** to associate it with the HA Kitchen area.
5. Open the native **Clean areas** picker and verify Kitchen is present.

The frontend check identified two issues addressed before release: the helper
classification could invoke a naming wizard for the shared device, and the
learning progress screen needed its instructions in the progress translation.
The integration is classified as a service and uses the source vacuum's friendly
name for its configuration entry.

Hardware operation remains unverified by this project. The supplied investigation
previously confirmed the SL60D single-room 0x14 command; multi-room operation and
other models have software-level validation only.
