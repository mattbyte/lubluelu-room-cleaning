# Room-cleaning protocol and evidence

`AA | body_length_hi | body_length_lo | command | data | checksum`

The two-byte big-endian length counts command plus data. The checksum is the sum of those bytes modulo 256. The room payload is `passes | room_count | room_ids...`; each room ID is one byte.

| Purpose | Command |
| --- | --- |
| Start selected-room cleaning | `0x14` |
| Room-selection report / acknowledgement | `0x15` |
| Zone command (not implemented) | `0x28` |
| Zone report (not implemented) | `0x29` |

The integration validates only the first length-delimited frame and ignores subsequent frames. A trailing `0x1B` geometry/status frame is not part of the room command. A captured report is never sent verbatim.

Regression vectors (example map only):

| Selection | Report | Generated setter |
| --- | --- | --- |
| ID 3 | `qgAEFQEBAxo=` | `qgAEFAEBAxk=` |
| IDs 3, 2 | `qgAFFQECAwId` | `qgAFFAECAwIc` |

The supplied SL60D investigation physically confirmed that the single-room setter alone starts cleaning and the robot sets its own power/mode/status DPs. The two-room setter is protocol-derived and covered by software tests, but was not physically verified in that investigation. This project has not run hardware tests.

References:

- [Sweeper implementation and protocol commentary](https://github.com/LM1LC3N7/gladys-lubluelu-vaccum/blob/main/src/tuya/sweeper.js)
- [Tuya Local text transport](https://github.com/make-all/tuya-local/blob/main/custom_components/tuya_local/text.py)
- [Home Assistant 2026.10 vacuum API](https://github.com/home-assistant/core/blob/2026.10.0/homeassistant/components/vacuum/__init__.py)

Room IDs do not contain map identity. A passive room report cannot prove that a remap has not occurred. The user must reset learned rooms after map changes. Segment IDs include a local map revision to reject mappings saved before that explicit reset.
