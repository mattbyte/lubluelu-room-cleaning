# 0.1.0

Initial release of Lubluelu Room Cleaning for Home Assistant 2026.10+ and Tuya Local.

- Companion vacuum with native HA area mapping and selected-room cleaning.
- Guided passive single-room learning, manual IDs, and validated pasted reports.
- Room renaming/deletion and map reset with stale-mapping protection.
- Public-entity transport: one DP15 `0x14` command, no cloud credentials or extra start/mode writes.
- Diagnostics with an explicit allowlist, source repairs, and entity-rename handling.

Install as a HACS custom repository. The SL60D single-room protocol was previously user-confirmed; this integration's hardware behavior, multi-room cleaning, and other models remain unverified. One map and one cleaning pass per request are supported.
