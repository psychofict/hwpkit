"""Unit tests for the CharShape helpers."""

from __future__ import annotations

import struct

from hwpkit import charshape as cs
from hwpkit import records as R


def _make_charshape_body(face_ids=(0, 1, 2, 3, 4, 5, 6), base_size=1000) -> bytes:
    """Build a minimum-valid CharShape body."""
    body = bytearray()
    body.extend(struct.pack("<7H", *face_ids))   # face_name_ids
    body.extend(struct.pack("<7B", 100, 100, 100, 100, 100, 100, 100))  # ratios
    body.extend(struct.pack("<7b", 0, 0, 0, 0, 0, 0, 0))  # char_spacings
    body.extend(struct.pack("<7B", 100, 100, 100, 100, 100, 100, 100))  # rel_sizes
    body.extend(struct.pack("<7b", 0, 0, 0, 0, 0, 0, 0))  # char_offsets
    body.extend(struct.pack("<i", base_size))    # base_size
    # Pad some trailing bytes (color/attr placeholders) — content doesn't matter here.
    body.extend(b"\x00" * 26)
    return bytes(body)


def _wrap_record(body: bytes, tag: int = cs.TAG_CHARSHAPE) -> dict:
    return {
        "tag": tag,
        "level": 0,
        "size": len(body),
        "header_len": 4,
        "body": body,
        "offset": 0,
    }


def test_get_face_ids():
    record = _wrap_record(_make_charshape_body(face_ids=(0, 6, 5, 5, 6, 6, 4)))
    assert cs.get_face_ids(record) == (0, 6, 5, 5, 6, 6, 4)


def test_set_face_ids():
    record = _wrap_record(_make_charshape_body())
    cs.set_face_ids(record, (7, 7, 7, 7, 7, 7, 7))
    assert cs.get_face_ids(record) == (7, 7, 7, 7, 7, 7, 7)


def test_set_face_ids_wrong_length():
    record = _wrap_record(_make_charshape_body())
    try:
        cs.set_face_ids(record, (0, 0, 0))  # type: ignore[arg-type]
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def test_flatten_to_face():
    record = _wrap_record(_make_charshape_body(face_ids=(0, 1, 2, 3, 4, 5, 6)))
    cs.flatten_to_face(record, 3)
    assert cs.get_face_ids(record) == (3, 3, 3, 3, 3, 3, 3)


def test_get_set_base_size():
    record = _wrap_record(_make_charshape_body(base_size=1100))
    assert cs.get_base_size(record) == 1100
    cs.set_base_size(record, 1500)
    assert cs.get_base_size(record) == 1500


def test_find_charshape():
    other = _wrap_record(b"\x00" * 16, tag=0x10)
    a = _wrap_record(_make_charshape_body(face_ids=(0,) * 7))
    b = _wrap_record(_make_charshape_body(face_ids=(1,) * 7))
    c = _wrap_record(_make_charshape_body(face_ids=(2,) * 7))
    records = [other, a, other, b, c]
    assert cs.find_charshape(records, 0) == 1
    assert cs.find_charshape(records, 1) == 3
    assert cs.find_charshape(records, 2) == 4


def test_find_charshape_out_of_range():
    records = [_wrap_record(_make_charshape_body())]
    try:
        cs.find_charshape(records, 5)
    except IndexError:
        return
    raise AssertionError("expected IndexError")
