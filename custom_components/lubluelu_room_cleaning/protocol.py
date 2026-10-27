"""Strict, transport-independent Tuya sweeper room protocol.

Only the first length-delimited frame is used. Geometry in trailing frames is
neither needed nor replayed. No captured payload is ever sent verbatim.
"""

import base64
import binascii
from dataclasses import dataclass


class InvalidReport(ValueError):
    """A payload is not a valid room-selection report."""


@dataclass(frozen=True)
class RoomReport:
    """Validated room-selection report."""

    passes: int
    room_ids: tuple[int, ...]


def decode_report(value: str) -> RoomReport:
    """Decode a 0x15 report, never a setter or a geometry frame."""
    if not isinstance(value, str) or len(value) > 65536:
        raise InvalidReport("invalid_report")
    try:
        raw = base64.b64decode(value.strip(), validate=True)
    except (ValueError, binascii.Error) as err:
        raise InvalidReport("invalid_report") from err
    if len(raw) < 8 or raw[0] != 0xAA:
        raise InvalidReport("invalid_report")
    length = int.from_bytes(raw[1:3], "big")
    if length < 4 or len(raw) < length + 4:
        raise InvalidReport("invalid_report")
    body = raw[3 : 3 + length]
    if body[0] != 0x15 or sum(body) & 0xFF != raw[3 + length]:
        raise InvalidReport("invalid_report")
    passes, count = body[1:3]
    ids = tuple(body[3:])
    if not passes or not count or len(ids) != count or len(set(ids)) != count:
        raise InvalidReport("invalid_report")
    return RoomReport(passes, ids)


def single_room(value: str) -> int:
    """Require an unambiguous single-room report."""
    report = decode_report(value)
    if len(report.room_ids) != 1:
        raise InvalidReport("multiple_rooms")
    return report.room_ids[0]


def encode_rooms(room_ids: list[int]) -> str:
    """Build one 0x14 command, always with one cleaning pass."""
    if any(type(room) is not int or not 0 <= room <= 255 for room in room_ids):
        raise ValueError("invalid_room")
    ids = list(dict.fromkeys(room_ids))
    if not 1 <= len(ids) <= 255:
        raise ValueError("invalid_selection")
    body = bytes([0x14, 1, len(ids), *ids])
    return base64.b64encode(
        b"\xaa" + len(body).to_bytes(2, "big") + body + bytes([sum(body) & 0xFF])
    ).decode("ascii")
