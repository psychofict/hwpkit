"""Unit tests for record-level operations. No real HWP fixture needed —
these exercise parse / serialize / inject_text / swap / replace on
hand-built byte sequences.

For an end-to-end test against a real HWP, set the HWPKIT_FIXTURE env
var to a .hwp path; test_roundtrip.py will exercise the CFB round-trip
when that's available.
"""

from __future__ import annotations

import struct

from hwpkit import records as R


def _make_record(tag: int, level: int, body: bytes) -> bytes:
    """Hand-build a raw record byte sequence with header."""
    size = len(body)
    if size < 0xFFF:
        hdr = (tag & 0x3FF) | ((level & 0x3FF) << 10) | ((size & 0xFFF) << 20)
        return struct.pack("<I", hdr) + body
    hdr = (tag & 0x3FF) | ((level & 0x3FF) << 10) | (0xFFF << 20)
    return struct.pack("<I", hdr) + struct.pack("<I", size) + body


def test_parse_serialize_empty():
    assert R.parse(b"") == []
    assert R.serialize([]) == b""


def test_parse_serialize_short_record():
    raw = _make_record(R.TAG_PARA_HEADER, 0, b"\x01\x00\x00\x00")
    records = R.parse(raw)
    assert len(records) == 1
    assert records[0]["tag"] == R.TAG_PARA_HEADER
    assert records[0]["body"] == b"\x01\x00\x00\x00"
    assert records[0]["header_len"] == 4
    assert R.serialize(records) == raw


def test_parse_serialize_extended_header():
    big_body = b"\x42" * 5000  # forces extended (8-byte) header
    raw = _make_record(R.TAG_PARA_TEXT, 1, big_body)
    records = R.parse(raw)
    assert len(records) == 1
    assert records[0]["size"] == 5000
    assert records[0]["header_len"] == 8
    assert R.serialize(records) == raw


def test_parse_serialize_multiple():
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, b"\x05\x00\x00\x00" + b"\x00" * 18)
        + _make_record(R.TAG_PARA_TEXT, 1, "안녕\r".encode("utf-16-le"))
        + _make_record(R.TAG_PARA_CHAR_SHAPE, 1, struct.pack("<II", 0, 0))
        + _make_record(R.TAG_PARA_LINE_SEG, 1, b"\xff" * 36)
    )
    records = R.parse(raw)
    assert len(records) == 4
    assert R.serialize(records) == raw


def test_inject_text_into_empty_paragraph():
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 1) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_CHAR_SHAPE, 1, struct.pack("<II", 0, 0))
        + _make_record(R.TAG_PARA_LINE_SEG, 1, b"\xff" * 36)
    )
    records = R.parse(raw)
    R.inject_text(records, 0, "안녕하세요")

    text_records = [r for r in records if r["tag"] == R.TAG_PARA_TEXT]
    assert len(text_records) == 1
    assert text_records[0]["body"].decode("utf-16-le") == "안녕하세요\r"

    seg = next(r for r in records if r["tag"] == R.TAG_PARA_LINE_SEG)
    assert seg["body"] == b"\x00" * 36, "PARA_LINE_SEG must be dummied to all zeros"

    chars = struct.unpack_from("<I", records[0]["body"], 0)[0] & 0x7FFFFFFF
    assert chars == 6, "chars should be len('안녕하세요') + 1 for \\r"


def test_inject_preserves_control_paragraph_high_bit():
    chars_with_high_bit = struct.pack("<I", 0x80000001)
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, chars_with_high_bit + b"\x00" * 18)
        + _make_record(R.TAG_PARA_LINE_SEG, 1, b"\xff" * 36)
    )
    records = R.parse(raw)
    R.inject_text(records, 0, "ab")
    new_chars_raw = struct.unpack_from("<I", records[0]["body"], 0)[0]
    assert new_chars_raw & 0x80000000, "control-paragraph high bit must survive"
    assert (new_chars_raw & 0x7FFFFFFF) == 3


def test_swap_in_para_text_equal_length():
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 3) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_TEXT, 1, "□ a\r".encode("utf-16-le"))
        + _make_record(R.TAG_PARA_LINE_SEG, 1, b"\xff" * 36)
    )
    records = R.parse(raw)
    R.swap_in_para_text(records, 0, "□", "☑")
    text_records = [r for r in records if r["tag"] == R.TAG_PARA_TEXT]
    assert text_records[0]["body"].decode("utf-16-le") == "☑ a\r"

    seg = next(r for r in records if r["tag"] == R.TAG_PARA_LINE_SEG)
    assert seg["body"] == b"\xff" * 36, (
        "swap_in_para_text must NOT dummy the LineSeg — same-length swaps "
        "should keep the cached layout"
    )


def test_swap_unequal_length_raises():
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 3) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_TEXT, 1, "ab\r".encode("utf-16-le"))
    )
    records = R.parse(raw)
    try:
        R.swap_in_para_text(records, 0, "a", "bb")
    except ValueError:
        return
    raise AssertionError("expected ValueError for unequal-length swap")


def test_replace_text_grows():
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 3) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_TEXT, 1, "ab\r".encode("utf-16-le"))
        + _make_record(R.TAG_PARA_LINE_SEG, 1, b"\xff" * 36)
    )
    records = R.parse(raw)
    R.replace_text(records, 0, "new content")
    text_records = [r for r in records if r["tag"] == R.TAG_PARA_TEXT]
    assert text_records[0]["body"].decode("utf-16-le") == "new content\r"
    chars = struct.unpack_from("<I", records[0]["body"], 0)[0] & 0x7FFFFFFF
    assert chars == len("new content\r")
    seg = next(r for r in records if r["tag"] == R.TAG_PARA_LINE_SEG)
    assert seg["body"] == b"\x00" * 36


def test_replace_text_falls_through_to_inject_when_no_para_text():
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 1) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_LINE_SEG, 1, b"\xff" * 36)
    )
    records = R.parse(raw)
    R.replace_text(records, 0, "hello")
    text_records = [r for r in records if r["tag"] == R.TAG_PARA_TEXT]
    assert len(text_records) == 1
    assert text_records[0]["body"].decode("utf-16-le") == "hello\r"


def test_compress_decompress_roundtrip():
    data = b"hello hwp world " * 100
    assert R.decompress(R.compress(data)) == data


def test_index_paragraphs():
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 1) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_TEXT, 1, "a\r".encode("utf-16-le"))
        + _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 1) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 1) + b"\x00" * 18)
    )
    records = R.parse(raw)
    assert R.index_paragraphs(records) == [0, 2, 3]


def test_describe_includes_paragraph_numbers():
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 1) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_TEXT, 1, "hi\r".encode("utf-16-le"))
    )
    records = R.parse(raw)
    out = R.describe(records)
    assert "P  0" in out
    assert "PARA_HEADER" in out
    assert "PARA_TEXT" in out
