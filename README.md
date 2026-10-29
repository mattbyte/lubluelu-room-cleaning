# Lubluelu Room Cleaning

[![Validate](https://github.com/mattbyte/lubluelu-room-cleaning/actions/workflows/validate.yml/badge.svg)](https://github.com/mattbyte/lubluelu-room-cleaning/actions/workflows/validate.yml)

Add Home Assistant's native room selection to a compatible vacuum already connected through [Tuya Local](https://github.com/make-all/tuya-local).

The integration creates a **Room cleaning** companion vacuum on the existing device. Normal controls use your original Tuya Local vacuum. Room cleaning sends one locally delivered command through its command text entity. It needs no cloud account, local key, custom card, or second Tuya connection.

## Requirements and compatibility

- Home Assistant **2026.10.0 or later**.
- Tuya Local installed and configured, with an enabled vacuum and writable `command_trans` text entity on the **same device**. On the SL60D this is DP15, commonly named **Command**. Check the Tuya Local device definition; do not select a different text entity merely because it accepts base64.
- A vacuum using the Tuya sweeper `0x14` room command / `0x15` room report protocol.

Setup lists every Tuya Local vacuum, but **not every Tuya Local vacuum uses this protocol**. A valid room report or explicit manual confirmation is required before room cleaning is exposed. Selection of an entity alone is not a compatibility test.

The SL60D's single-room command was physically confirmed by the project user before this integration was created. This integration's own hardware behavior, multi-room cleaning, and other models remain unverified. Automated tests use simulated entities only. There is no brand-independent promise of device compatibility.

## Install through HACS

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/mattbyte/lubluelu-room-cleaning` with category **Integration**.
3. Download **Lubluelu Room Cleaning** and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → Lubluelu Room Cleaning**.
5. Choose your Tuya Local vacuum and its command text entity. Setup sends no commands.
6. Open the integration's **Configure** menu to add rooms.

This is a HACS custom repository, not a listing in the default HACS catalog. For manual installation, copy `custom_components/lubluelu_room_cleaning` into your HA `custom_components` directory and restart.

## Learn rooms safely

1. In **Configure**, choose **Learn a room from Smart Life** and give it a name.
2. Wait until the wizard says it is listening.
3. In Smart Life, select **only that room** and start cleaning. This action physically starts the robot. The integration itself only listens; you control stopping and docking it.
4. Confirm the captured room ID and its name. Nothing is saved until confirmation.
5. Reopen Configure and repeat for the remaining rooms.

The wizard listens for two minutes. It validates base64, the first frame's length, opcode, checksum, and room count. It ignores outgoing commands and unrelated data. A multi-room selection cannot be assigned a single room name. Additional geometry frames are not needed.

A report already present before listening is not accepted. Repeating the same room may produce an unchanged text state; periodic rewrites of cached state cannot prove a new selection. In that case use **Enter an ID or paste a report**, or select a different room through Smart Life before starting a fresh learning session. Do not send extra test commands just to change the value.

### Manual entry

Enter a known decimal ID from 0–255, or paste a single-room `0x15` report. Numeric IDs require explicitly confirming that the device uses this protocol. Pasted reports are validated but never replayed or retained. You still confirm the room name before saving.

Room IDs belong to your robot's current map. Never copy another user's Kitchen or Bedroom ID. Saving an existing ID renames it; names must be nonempty and unique within that vacuum.

## Use native Home Assistant areas

1. Open the **Room cleaning** companion vacuum's entity settings.
2. Open **Map vacuum segments to areas** and associate the learned robot rooms with your HA areas.
3. Use the native vacuum room controls or the `vacuum.clean_area` action. No custom dashboard resource is required.

Example automation action (replace the entity and HA area IDs):

```yaml
action: vacuum.clean_area
target:
  entity_id: vacuum.simulated_vacuum_room_cleaning
data:
  cleaning_area_id:
    - kitchen
    - corridor
```

`cleaning_area_id` contains **HA area IDs**, not robot room numbers. HA translates them using the mapping you saved. Multiple selected rooms become one DP15 command with one cleaning pass. The integration does not additionally write power or mode DPs.

The companion forwards supported start, stop, pause, dock, locate, spot-clean, and fan-speed controls to the original vacuum. Its activity comes from Tuya Local; it does not infer that the robot is cleaning merely because a command was sent. The original vacuum remains available for existing automations.

## Maps, changes, and recovery

- Each vacuum has one learned map. Multiple vacuums have separate entries and room lists.
- After remapping, splitting/merging rooms, or changing room numbering in Smart Life, choose **Reset after remapping**. Relearn the rooms and update HA's area mapping.
- Reset changes internal segment IDs so stale HA area mappings cannot target the new rooms. Renaming or deleting rooms raises a native mapping repair when a previously saved mapping differs.
- Automatic map-change detection is unavailable: room reports cannot reveal whether an unchanged number has acquired a new meaning.
- Source entity renames are tracked by registry ID. If a source is deleted, disabled, or moved, restore it or use **Reconfigure**. Replacing either source clears the learned rooms.
- Configuration persists in HA config entries. Unloading removes listeners and cancels pending learning. Removing the integration removes its companion and configuration; the original Tuya Local vacuum stays installed.

## Troubleshooting and privacy

**No command entity:** enable the appropriate Tuya Local text entity if disabled. If the device definition does not expose writable `command_trans`, this companion cannot add it; resolve that in Tuya Local first.

**Learning times out:** check the command entity's availability and select one room while the wizard is listening. An identical cached report requires manual entry. A report containing several rooms must be recaptured as one room.

**No native room selection:** add at least one room and confirm protocol compatibility. Use HA 2026.10+ and configure area mapping on the companion, not the original vacuum.

**Command failed:** check the robot before retrying. A timeout or service error does not establish that the device rejected the write. This integration does not automatically retry physical commands.

**Command text is unknown after a restart:** this means no current DP15 value has been reported. Room cleaning and passive learning can still use the enabled command entity when it is available. An explicitly `unavailable` or missing command entity still blocks room commands. The source vacuum must also have a known, available state. No prior room report or reconfiguration is required just to clear an `unknown` command value.

**Too many rooms:** the text entity imposes a payload length limit. Select fewer rooms; the integration will not split one action into multiple commands.

**Misleading activity:** activity is taken from Tuya Local, never the official Tuya cloud entity. If your Tuya Local definition does not handle `select_room`, correct its device definition upstream rather than relying on an optimistic status.

Diagnostics contain counts and operational flags only. They omit Tuya configuration, credentials, device identifiers, room names, and raw reports. The integration does not log command payloads. Tuya Local has its own logging behavior; review its logs before sharing them.

## Development and protocol references

See [CONTRIBUTING.md](CONTRIBUTING.md) for isolated tests, [docs/VALIDATION.md](docs/VALIDATION.md) for validation results, and [docs/PROTOCOL.md](docs/PROTOCOL.md) for the frame contract and evidence boundary. No automated test contacts a physical device.

Project structure, development-container approach, issue templates, and validation workflow are based on [ludeeus/integration_blueprint](https://github.com/ludeeus/integration_blueprint), with its MIT attribution preserved. The protocol was independently implemented in Python from the supplied verified captures and the documented setter/report distinction in [LM1LC3N7/gladys-lubluelu-vaccum](https://github.com/LM1LC3N7/gladys-lubluelu-vaccum/blob/main/src/tuya/sweeper.js). Native area support follows [Home Assistant's vacuum API](https://developers.home-assistant.io/docs/core/entity/vacuum/).
