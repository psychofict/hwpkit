"""Dump an HWP file's Section0 paragraph structure.

Usage:
    python -m hwpkit.inspect path/to/file.hwp
    hwpkit-inspect path/to/file.hwp

Prints one line per record with a text preview, so you can identify
which paragraph index is which form cell before calling inject_text /
replace_text / swap_in_para_text.
"""

from __future__ import annotations

import sys

from . import cfb, records
from .pipeline import section0_sid, file_header_compressed


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: hwpkit-inspect <file.hwp>", file=sys.stderr)
        sys.exit(0 if argv and argv[0] in ("-h", "--help") else 2)
    path = argv[0]
    entries = cfb.load(path)
    s0 = section0_sid(entries)
    raw = entries[s0].data
    if file_header_compressed(entries):
        raw = records.decompress(raw)
    recs = records.parse(raw)
    print(records.describe(recs))


if __name__ == "__main__":
    main()
