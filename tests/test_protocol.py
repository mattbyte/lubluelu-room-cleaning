"""Known captures and invalid frames must not turn reports into commands."""

import base64

import pytest

from custom_components.lubluelu_room_cleaning.protocol import (
    InvalidReport,
    decode_report,
    encode_rooms,
    single_room,
)


def report(body):
    return base64.b64encode(
        b"\xaa" + len(body).to_bytes(2, "big") + body + bytes([sum(body) & 255])
    ).decode()


def test_confirmed_frames():
    assert single_room("qgAEFQEBAxo=") == 3
    assert encode_rooms([3]) == "qgAEFAEBAxk="
    assert decode_report("qgAFFQECAwId").room_ids == (3, 2)
    assert encode_rooms([3, 2]) == "qgAFFAECAwIc"
    assert encode_rooms([3, 3, 2]) == "qgAFFAECAwIc"


def test_concatenated_frames():
    assert single_room("qgAEFQEBAxqqABQbAQAEAp4BSgNmAUoDZv6EAp7+hMw=") == 3


@pytest.mark.parametrize(
    "value",
    [
        "",
        "!invalid!",
        "qgAEFAEBAxk=",
        "qgAEFQEBAxk=",
        "qgAEFQEBAw==",
        "AAAAFQEBAxo=",
        report(bytes([0x15, 1, 2, 3])),
        report(bytes([0x15, 0, 1, 3])),
        report(bytes([0x15, 1, 0])),
        report(bytes([0x15, 1, 2, 3, 3])),
        report(bytes([0x1B, 1, 1, 3])),
        "A" * 65540,
        report(bytes([0x15, 1, 1, 2, 3])),
    ],
)
def test_invalid_reports(value):
    with pytest.raises(InvalidReport):
        decode_report(value)


def test_multi_room_not_learned_as_single():
    with pytest.raises(InvalidReport, match="multiple_rooms"):
        single_room("qgAFFQECAwId")


@pytest.mark.parametrize("ids", [[], [-1], [256], [True], [1.5], ["3"], list(range(256))])
def test_invalid_commands(ids):
    with pytest.raises(ValueError):
        encode_rooms(ids)


def test_byte_boundaries():
    assert base64.b64decode(encode_rooms([0, 255]))[3:-1] == bytes([0x14, 1, 2, 0, 255])
