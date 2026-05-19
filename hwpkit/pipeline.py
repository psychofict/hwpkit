"""End-to-end pipeline: load HWP → decompress Section0 → edit records →
recompress → write a new HWP.

Use this when you want a one-call entry point. For finer control (e.g.
editing DocInfo as well), use cfb.load / cfb.dump and records.* directly.
"""

from __future__ import annotations

import struct
from typing import Callable, List

from . import cfb
from . import records as rec


def section0_sid(entries) -> int:
    """Locate the Section0 dir entry SID by name."""
    for sid, de in entries.items():
        if de.name == "BodyText":
            break
    else:
        raise RuntimeError("BodyText storage not found")
    for sid, de in entries.items():
        if de.name == "Section0":
            return sid
    raise RuntimeError("Section0 not found")


def docinfo_sid(entries) -> int:
    """Locate the DocInfo stream SID by name."""
    for sid, de in entries.items():
        if de.name == "DocInfo":
            return sid
    raise RuntimeError("DocInfo not found")


def file_header_compressed(entries) -> bool:
    """Read FileHeader stream's compression bit."""
    for sid, de in entries.items():
        if de.name == "FileHeader" and de.data:
            return bool(struct.unpack("<I", de.data[36:40])[0] & 0x01)
    return False


def fill_hwp(input_path: str, output_path: str,
             edit_fn: Callable[[List[dict]], None]):
    """Open `input_path`, parse Section0, call `edit_fn(records)` to mutate
    in place, then write the new HWP to `output_path`.

    Returns (raw_in, raw_out, comp_in, comp_out) sizes for logging.
    """
    entries = cfb.load(input_path)
    s0 = section0_sid(entries)
    section0 = entries[s0].data
    compressed = file_header_compressed(entries)
    raw = rec.decompress(section0) if compressed else section0
    records = rec.parse(raw)
    edit_fn(records)
    raw2 = rec.serialize(records)
    section0_new = rec.compress(raw2) if compressed else raw2
    cfb.dump(entries, output_path,
             target_sid_to_replace=s0, new_data=section0_new)
    return len(raw), len(raw2), len(section0), len(section0_new)
