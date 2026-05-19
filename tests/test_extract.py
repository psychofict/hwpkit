"""Unit tests for plain-text extraction."""

from __future__ import annotations

import struct

from hwpedit import records as R


def _make_record(tag: int, level: int, body: bytes) -> bytes:
    size = len(body)
    if size < 0xFFF:
        hdr = (tag & 0x3FF) | ((level & 0x3FF) << 10) | ((size & 0xFFF) << 20)
        return struct.pack("<I", hdr) + body
    hdr = (tag & 0x3FF) | ((level & 0x3FF) << 10) | (0xFFF << 20)
    return struct.pack("<I", hdr) + struct.pack("<I", size) + body


def _para(chars: int, text_body: bytes | None = None) -> bytes:
    head = _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", chars) + b"\x00" * 18)
    if text_body is None:
        return head
    return head + _make_record(R.TAG_PARA_TEXT, 1, text_body)


def test_extract_text_simple():
    raw = _para(3, "hi\r".encode("utf-16-le"))
    assert R.extract_text(R.parse(raw)) == "hi"


def test_extract_text_korean():
    raw = _para(6, "안녕하세요\r".encode("utf-16-le"))
    assert R.extract_text(R.parse(raw)) == "안녕하세요"


def test_extract_text_strips_extended_inline_control():
    # 16-byte extended ctrl span: ctrl_id 0x01, six payload code units,
    # closing ctrl_id 0x01. Followed by literal "abc\r".
    ctrl_span = b"\x01\x00" + b"x\x00" * 6 + b"\x01\x00"
    body = ctrl_span + "abc\r".encode("utf-16-le")
    raw = _para(12, body)
    assert R.extract_text(R.parse(raw)) == "abc"


def test_extract_text_strips_high_extended_ctrl():
    # Real-world: 0x15 (bookmark) was previously missed because the
    # cap was 0x14 — make sure the whole 0x01..0x17 range is covered.
    for opener in (0x01, 0x02, 0x10, 0x15, 0x17):
        ctrl_span = (
            bytes([opener, 0x00]) + b"x\x00" * 6 + bytes([opener, 0x00])
        )
        body = ctrl_span + "ok\r".encode("utf-16-le")
        raw = _para(11, body)
        assert R.extract_text(R.parse(raw)) == "ok", (
            f"opener 0x{opener:02x} not stripped"
        )


def test_extract_text_soft_linebreak():
    raw = _para(6, "ab\ncd\r".encode("utf-16-le"))
    assert R.extract_text(R.parse(raw)) == "ab\ncd"


def test_extract_text_tab():
    raw = _para(6, "ab\tcd\r".encode("utf-16-le"))
    assert R.extract_text(R.parse(raw)) == "ab\tcd"


def test_extract_text_fixed_width_space():
    # 0x1E is HWP's fixed-width space → renders as " "
    body = "a".encode("utf-16-le") + b"\x1e\x00" + "b\r".encode("utf-16-le")
    raw = _para(4, body)
    assert R.extract_text(R.parse(raw)) == "a b"


def test_extract_text_empty_paragraph_becomes_blank_line():
    raw = _para(1) + _para(3, "hi\r".encode("utf-16-le"))
    assert R.extract_text(R.parse(raw)) == "\nhi"


def test_extract_text_multiple_paragraphs():
    raw = (
        _para(2, "a\r".encode("utf-16-le"))
        + _para(2, "b\r".encode("utf-16-le"))
        + _para(2, "c\r".encode("utf-16-le"))
    )
    assert R.extract_text(R.parse(raw)) == "a\nb\nc"


def test_extract_text_ignores_non_text_records():
    # PARA_HEADER + PARA_TEXT + PARA_CHAR_SHAPE + PARA_LINE_SEG mix
    raw = (
        _make_record(R.TAG_PARA_HEADER, 0, struct.pack("<I", 4) + b"\x00" * 18)
        + _make_record(R.TAG_PARA_TEXT, 1, "abc\r".encode("utf-16-le"))
        + _make_record(R.TAG_PARA_CHAR_SHAPE, 1, struct.pack("<II", 0, 0))
        + _make_record(R.TAG_PARA_LINE_SEG, 1, b"\x00" * 36)
    )
    assert R.extract_text(R.parse(raw)) == "abc"
