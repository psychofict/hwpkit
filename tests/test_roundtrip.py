"""End-to-end CFB round-trip test against a real .hwp file.

Skipped unless the HWPKIT_FIXTURE env var points at an existing .hwp.
Set this to one of your own templates locally to validate that:

    HWPKIT_FIXTURE=/path/to/template.hwp pytest tests/test_roundtrip.py
"""

from __future__ import annotations

import os

import pytest

from hwpkit import cfb

FIXTURE = os.environ.get("HWPKIT_FIXTURE")

pytestmark = pytest.mark.skipif(
    not FIXTURE or not os.path.exists(FIXTURE),
    reason="set HWPKIT_FIXTURE=path/to/file.hwp to enable",
)


def _stream_set(ole):
    return {tuple(p) for p in ole.listdir()}


def test_byte_identical_cfb_roundtrip(tmp_path):
    """Load a real HWP, dump it without modification, then assert that
    every stream is byte-identical when read back through olefile."""
    import olefile

    out = tmp_path / "rt.hwp"
    entries = cfb.load(FIXTURE)
    cfb.dump(entries, str(out))

    a = olefile.OleFileIO(FIXTURE)
    b = olefile.OleFileIO(str(out))
    try:
        a_streams = _stream_set(a)
        b_streams = _stream_set(b)
        assert a_streams == b_streams, (
            f"stream set differs: only in original={a_streams - b_streams}, "
            f"only in roundtrip={b_streams - a_streams}"
        )
        for path in a_streams:
            data_a = a.openstream(list(path)).read()
            data_b = b.openstream(list(path)).read()
            assert data_a == data_b, f"stream {path!r} bytes differ"
    finally:
        a.close()
        b.close()
