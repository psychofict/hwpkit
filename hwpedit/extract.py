"""Plain-text extraction from an HWP file.

Usage:
    python -m hwpedit.extract path/to/file.hwp
    hwpedit-text path/to/file.hwp

Walks every Section* stream under BodyText (in numeric order), decodes
PARA_TEXT records, strips inline controls, and prints the result. For
semantic HWP → XML conversion, use pyhwp instead.
"""

from __future__ import annotations

import sys

from . import cfb, records
from .pipeline import file_header_compressed


def extract_text_from_hwp(path: str) -> str:
    """Read an HWP and return its plain text content across all sections."""
    entries = cfb.load(path)
    compressed = file_header_compressed(entries)
    sections = []
    for sid, de in entries.items():
        if de.etype != 2 or not de.data:
            continue
        if not de.name.startswith("Section"):
            continue
        suffix = de.name[len("Section"):]
        try:
            idx = int(suffix)
        except ValueError:
            continue
        sections.append((idx, sid))
    sections.sort()
    parts = []
    for _, sid in sections:
        raw = entries[sid].data
        if compressed:
            raw = records.decompress(raw)
        parts.append(records.extract_text(records.parse(raw)))
    return "\n".join(parts)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: hwpedit-text <file.hwp>", file=sys.stderr)
        sys.exit(0 if argv and argv[0] in ("-h", "--help") else 2)
    print(extract_text_from_hwp(argv[0]))


if __name__ == "__main__":
    main()
