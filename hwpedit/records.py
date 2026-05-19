"""HWP 5.0 record-level manipulation.

Operations:
  - parse(raw)                                 → list of record dicts
  - serialize(records)                         → bytes (round-trips parse)
  - decompress(stream) / compress(raw)         → raw deflate codec
  - inject_text(records, paragraph_index, text)
        fill an empty paragraph (chars==1 sentinel) with new text
  - swap_in_para_text(records, paragraph_index, old, new)
        replace an equal-length UTF-16 substring in a paragraph's PARA_TEXT
  - replace_text(records, paragraph_index, text)
        rewrite a paragraph's PARA_TEXT body entirely
  - describe(records)                          → human-readable dump

Records are kept as a list of dicts that round-trip exactly when nothing
is changed.

Header layout (32-bit little-endian):
  bits 0..9   = tag_id
  bits 10..19 = level
  bits 20..31 = size  (0xFFF = extended; next 4 bytes are real size)
"""

from __future__ import annotations

import struct
import zlib
from typing import List

TAG_PARA_HEADER = 0x42
TAG_PARA_TEXT = 0x43
TAG_PARA_CHAR_SHAPE = 0x44
TAG_PARA_LINE_SEG = 0x45

LINESEG_SIZE = 36
LINESEG_FLAGS_DEFAULT = 0x00060000  # bits 17+18: line_head + line_tail


def decompress(stream_bytes: bytes) -> bytes:
    """HWP BodyText / DocInfo streams are raw deflate (no zlib header)."""
    return zlib.decompress(stream_bytes, -15)


def compress(raw: bytes) -> bytes:
    """Raw deflate at max compression."""
    co = zlib.compressobj(9, zlib.DEFLATED, -15)
    return co.compress(raw) + co.flush()


def parse(raw: bytes) -> List[dict]:
    """Return a list of records with raw body bytes preserved.

    Each record dict: {tag, level, size, header_len, body, offset}
    """
    out = []
    i = 0
    while i < len(raw):
        hdr = struct.unpack_from("<I", raw, i)[0]
        tag = hdr & 0x3FF
        level = (hdr >> 10) & 0x3FF
        size = (hdr >> 20) & 0xFFF
        if size == 0xFFF:
            size = struct.unpack_from("<I", raw, i + 4)[0]
            header_len = 8
        else:
            header_len = 4
        body = raw[i + header_len : i + header_len + size]
        out.append({
            "tag": tag,
            "level": level,
            "size": size,
            "header_len": header_len,
            "body": body,
            "offset": i,
        })
        i += header_len + size
    return out


def serialize(records: List[dict]) -> bytes:
    """Inverse of parse(). Reconstructs the byte stream."""
    out = bytearray()
    for r in records:
        body = r["body"]
        size = len(body)
        tag = r["tag"] & 0x3FF
        level = r["level"] & 0x3FF
        if size < 0xFFF and r.get("force_extended_header", False) is False:
            hdr = tag | (level << 10) | (size << 20)
            out.extend(struct.pack("<I", hdr))
        else:
            hdr = tag | (level << 10) | (0xFFF << 20)
            out.extend(struct.pack("<I", hdr))
            out.extend(struct.pack("<I", size))
        out.extend(body)
    return bytes(out)


def index_paragraphs(records: List[dict]) -> List[int]:
    """Return record indices where PARA_HEADER lives, in order."""
    return [i for i, r in enumerate(records) if r["tag"] == TAG_PARA_HEADER]


def _para_text_after(records, para_record_index):
    j = para_record_index + 1
    if j < len(records) and records[j]["tag"] == TAG_PARA_TEXT:
        return j
    return None


def _para_lineseg_after(records, para_record_index):
    """Find PARA_LINE_SEG following a PARA_HEADER, walking past PARA_TEXT
    and PARA_CHAR_SHAPE records. Returns None at next PARA_HEADER."""
    for j in range(para_record_index + 1, min(para_record_index + 6, len(records))):
        if records[j]["tag"] == TAG_PARA_LINE_SEG:
            return j
        if records[j]["tag"] == TAG_PARA_HEADER:
            return None
    return None


def _regenerate_lineseg(records, para_record_index, new_chars: int):
    """Replace PARA_LINE_SEG with a 36-byte all-zero "dummy" LineSeg.

    Hancom treats an all-zero LineSeg as a sentinel meaning "no cached
    layout, recompute from PARA_CHAR_SHAPE font metrics." A stale present
    LineSeg is treated as authoritative, so just letting the original sit
    causes new text to overlay on the old single visual line. Deleting the
    record outright makes Hancom reject the file as corrupted.

    Mirrors pyhwp's "더미 LineSeg를 만들어 준다" fallback.
    """
    ls_idx = _para_lineseg_after(records, para_record_index)
    if ls_idx is None:
        return
    records[ls_idx]["body"] = b"\x00" * LINESEG_SIZE
    records[ls_idx]["size"] = LINESEG_SIZE
    records[ls_idx].pop("force_extended_header", None)
    records[ls_idx]["header_len"] = 4


def swap_in_para_text(records, paragraph_index, old: str, new: str):
    """Replace UTF-16LE bytes of `old` with `new` inside paragraph N's
    PARA_TEXT. Requires len(old) == len(new) so byte length is preserved
    and the cached PARA_LINE_SEG remains valid (no dummy needed).
    """
    if len(old) != len(new):
        raise ValueError("swap_in_para_text requires equal-length strings")
    para_indices = index_paragraphs(records)
    pr_idx = para_indices[paragraph_index]
    pt_idx = _para_text_after(records, pr_idx)
    if pt_idx is None:
        raise ValueError(f"P{paragraph_index} has no PARA_TEXT to swap in")
    old_b = old.encode("utf-16-le")
    new_b = new.encode("utf-16-le")
    body = records[pt_idx]["body"]
    if old_b not in body:
        raise ValueError(f"P{paragraph_index} PARA_TEXT does not contain {old!r}")
    records[pt_idx]["body"] = body.replace(old_b, new_b, 1)


def inject_text(records, paragraph_index, text: str):
    """Fill an empty paragraph (chars==1, no PARA_TEXT) with the given text.

    The trailing record-end \\r is added automatically and counted. Use
    \\n for soft line breaks inside the paragraph. The cached PARA_LINE_SEG
    is replaced with a 36-byte dummy so Hancom recomputes layout.
    """
    para_indices = index_paragraphs(records)
    pr_idx = para_indices[paragraph_index]
    para = records[pr_idx]
    body = bytearray(para["body"])
    chars_raw = struct.unpack_from("<I", body, 0)[0]
    high_bit = chars_raw & 0x80000000
    chars_count = chars_raw & 0x7FFFFFFF
    if chars_count != 1:
        raise ValueError(
            f"P{paragraph_index} is not an empty paragraph (chars={chars_count})"
        )
    text_clean = text.replace("\r\n", "\n").replace("\r", "\n")
    payload = text_clean + "\r"
    new_chars = len(payload)
    new_chars_raw = (high_bit) | (new_chars & 0x7FFFFFFF)
    struct.pack_into("<I", body, 0, new_chars_raw)
    para["body"] = bytes(body)
    new_pt = {
        "tag": TAG_PARA_TEXT,
        "level": para["level"] + 1,
        "size": new_chars * 2,
        "header_len": 4,
        "body": payload.encode("utf-16-le"),
        "offset": -1,
    }
    if new_pt["size"] >= 0xFFF:
        new_pt["force_extended_header"] = True
        new_pt["header_len"] = 8
    pt_idx = _para_text_after(records, pr_idx)
    if pt_idx is not None:
        records[pt_idx] = new_pt
    else:
        records.insert(pr_idx + 1, new_pt)
    if new_chars > 1:
        _regenerate_lineseg(records, pr_idx, new_chars)


def replace_text(records, paragraph_index, text: str):
    """Rewrite a paragraph's PARA_TEXT body entirely. Falls through to
    inject_text if the paragraph has no PARA_TEXT yet.

    WARNING: do not call with text="" on a paragraph that originally had
    non-empty PARA_TEXT. The resulting (chars=1, PARA_TEXT=\\r) state opens
    fine in isolation but can corrupt the file when combined with other
    table-cell edits. Use " " or "—" as a placeholder instead.
    """
    para_indices = index_paragraphs(records)
    pr_idx = para_indices[paragraph_index]
    para = records[pr_idx]
    pt_idx = _para_text_after(records, pr_idx)
    if pt_idx is None:
        inject_text(records, paragraph_index, text)
        return
    text_clean = text.replace("\r\n", "\n").replace("\r", "\n")
    payload = text_clean + "\r"
    new_chars = len(payload)
    body = bytearray(para["body"])
    chars_raw = struct.unpack_from("<I", body, 0)[0]
    high_bit = chars_raw & 0x80000000
    struct.pack_into("<I", body, 0, high_bit | (new_chars & 0x7FFFFFFF))
    para["body"] = bytes(body)
    records[pt_idx]["body"] = payload.encode("utf-16-le")
    records[pt_idx]["size"] = new_chars * 2
    if new_chars * 2 >= 0xFFF:
        records[pt_idx]["force_extended_header"] = True
        records[pt_idx]["header_len"] = 8
    else:
        records[pt_idx].pop("force_extended_header", None)
        records[pt_idx]["header_len"] = 4
    if new_chars > 1:
        _regenerate_lineseg(records, pr_idx, new_chars)


def extract_text(records) -> str:
    """Extract plain text from a parsed BodyText/Section* record list.

    Returns one line per paragraph. Inline controls (tables, images,
    footnote refs, etc.) are stripped — only literal character content
    is returned. For semantic / structural conversion (HWP → XML / OWPML)
    use pyhwp instead; that's a much bigger job and out of scope here.

    Soft line breaks (0x0A) become \\n. Tabs (0x09) become \\t. The
    paragraph-terminating 0x0D is stripped from each line.
    """
    para_indices = index_paragraphs(records)
    lines = []
    for pr_idx in para_indices:
        pt_idx = _para_text_after(records, pr_idx)
        if pt_idx is None:
            lines.append("")
        else:
            lines.append(_extract_para_text(records[pt_idx]["body"]))
    return "\n".join(lines)


def _extract_para_text(body: bytes) -> str:
    """Decode a PARA_TEXT body to plain text, stripping inline controls.

    PARA_TEXT mixes literal UTF-16 characters with inline controls:
      - 0x01..0x17 (except tab/LF/CR) are 'extended' controls that span
        8 UTF-16 code units (16 bytes) — open ctrl_id + 6 payload units
        + matching close ctrl_id. Skip the whole span. Covers section
        defs, fields, table/drawing refs, header/footer refs, footnotes,
        autonumber, page-number ctrl, bookmarks, overlapping ruby, etc.
      - 0x09 = tab, 0x0A = soft line break, 0x0D = paragraph terminator
      - 0x18 = soft hyphen (drop), 0x1E / 0x1F = fixed-width space → " "
      - 0x00 = padding (drop)

    We walk in code-unit space (not Python codepoint space) so the
    16-byte extended-control width is honored even if surrogate pairs
    appear in the paragraph.
    """
    out = []
    i = 0
    n = len(body) - (len(body) % 2)
    while i < n:
        cu = body[i] | (body[i + 1] << 8)
        if cu == 0x09:
            out.append("\t"); i += 2; continue
        if cu in (0x0A, 0x0D):
            out.append("\n"); i += 2; continue
        if cu in (0x1E, 0x1F):
            out.append(" "); i += 2; continue
        if cu in (0x00, 0x18):
            i += 2; continue
        if 0x01 <= cu <= 0x17:
            # Extended inline control: 8 code units total (16 bytes).
            i += 16; continue
        if 0xD800 <= cu <= 0xDBFF and i + 4 <= n:
            # High surrogate — pair with the following low surrogate.
            out.append(body[i:i + 4].decode("utf-16-le", errors="replace"))
            i += 4
        else:
            out.append(body[i:i + 2].decode("utf-16-le", errors="replace"))
            i += 2
    return "".join(out).rstrip("\n")


def describe(records, limit=None):
    """Return a human-readable dump (one line per record).

    Each PARA_HEADER line is prefixed with `Pn` where n is the paragraph
    index — pass that n to inject_text / replace_text / swap_in_para_text.
    """
    pi = -1
    out = []
    for i, r in enumerate(records):
        if r["tag"] == TAG_PARA_HEADER:
            pi += 1
            chars = struct.unpack_from("<I", r["body"], 0)[0] & 0x7FFFFFFF
            out.append(f"[{i:3d}] P{pi:3d} PARA_HEADER L={r['level']} chars={chars}")
        elif r["tag"] == TAG_PARA_TEXT:
            txt = r["body"].decode("utf-16-le", errors="replace")
            preview = txt[:60].replace("\r", "\\r").replace("\n", "\\n")
            out.append(f"[{i:3d}]    PARA_TEXT L={r['level']} {len(r['body'])//2}ch: {preview!r}")
        else:
            out.append(f"[{i:3d}] tag=0x{r['tag']:02x} L={r['level']} sz={r['size']}")
        if limit and i >= limit:
            break
    return "\n".join(out)
