"""HWP DocInfo CharShape (tag 0x15) helpers.

A CharShape record body has 7 per-script font slots (Hangul / Latin /
Hanja / Japanese / Symbol / User / Other). Hancom's font dropdown often
only changes one slot — usually Hangul — so mixed-script paragraphs with
non-Hangul slots pointing at a different face will not pick up font
changes made through the toolbar.

Operate on records from a DocInfo stream:

    from hwpedit import cfb, records
    from hwpedit.pipeline import docinfo_sid, file_header_compressed
    from hwpedit import charshape

    entries = cfb.load("template.hwp")
    di_sid = docinfo_sid(entries)
    raw = entries[di_sid].data
    if file_header_compressed(entries):
        raw = records.decompress(raw)
    di_records = records.parse(raw)

    # Flatten the 18th CharShape (zero-indexed) to face_id 0
    i = charshape.find_charshape(di_records, 18)
    charshape.flatten_to_face(di_records[i], 0)

See docs/GOTCHAS.md §3 for the full explanation.
"""

from __future__ import annotations

import struct
from typing import List, Tuple

TAG_CHARSHAPE = 0x15

# CharShape body layout (first 46 bytes; record continues with color/attr/border):
#   0..14  : 7 × uint16   face_name_ids
#   14..21 : 7 × uint8    ratios
#   21..28 : 7 × int8     char_spacings
#   28..35 : 7 × uint8    rel_sizes
#   35..42 : 7 × int8     char_offsets
#   42..46 : int32        base_size (1/100 pt)
_FACE_IDS_OFF = 0
_BASE_SIZE_OFF = 42

SLOT_HANGUL = 0
SLOT_LATIN = 1
SLOT_HANJA = 2
SLOT_JAPANESE = 3
SLOT_SYMBOL = 4
SLOT_USER = 5
SLOT_OTHER = 6


def get_face_ids(record: dict) -> Tuple[int, int, int, int, int, int, int]:
    """Return the 7 face_name_ids of a CharShape record body."""
    return struct.unpack_from("<7H", record["body"], _FACE_IDS_OFF)


def set_face_ids(record: dict, face_ids: Tuple[int, int, int, int, int, int, int]):
    """Overwrite the 7 face_name_ids of a CharShape record body."""
    if len(face_ids) != 7:
        raise ValueError("face_ids must have exactly 7 entries")
    body = bytearray(record["body"])
    struct.pack_into("<7H", body, _FACE_IDS_OFF, *face_ids)
    record["body"] = bytes(body)


def get_base_size(record: dict) -> int:
    """Return base font size in 1/100 pt (e.g. 1100 = 11pt)."""
    return struct.unpack_from("<i", record["body"], _BASE_SIZE_OFF)[0]


def set_base_size(record: dict, size_centipoints: int):
    """Set base font size in 1/100 pt. 1100 = 11pt, 1000 = 10pt."""
    body = bytearray(record["body"])
    struct.pack_into("<i", body, _BASE_SIZE_OFF, size_centipoints)
    record["body"] = bytes(body)


def flatten_to_face(record: dict, face_id: int):
    """Set all 7 per-script face_name_ids to the same face id."""
    set_face_ids(record, (face_id,) * 7)


def find_charshape(docinfo_records: List[dict], shape_index: int) -> int:
    """Return the record-list index of the Nth CharShape (0-indexed) in
    a parsed DocInfo record list."""
    n = -1
    for i, r in enumerate(docinfo_records):
        if r["tag"] == TAG_CHARSHAPE:
            n += 1
            if n == shape_index:
                return i
    raise IndexError(f"no CharShape record at index {shape_index}")
