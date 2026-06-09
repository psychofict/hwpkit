"""Tests for adding entries to a CFB via the red-black-tree insert
(`cfb.add_stream` / `cfb.add_storage`).

The RB-invariant stress test needs no fixture and runs unconditionally.
The real-file integration test is gated on HWPKIT_FIXTURE, like
test_roundtrip.py:

    HWPKIT_FIXTURE=/path/to/template.hwp pytest tests/test_cfb_add.py
"""

from __future__ import annotations

import os
import random

import pytest

from hwpkit import cfb
from hwpkit.cfb import NOSTREAM, RED, BLACK, _name_key


def _fresh_root():
    return {0: cfb.DirEntryOut("Root Entry", 5, BLACK, NOSTREAM, NOSTREAM,
                               NOSTREAM, b"\x00" * 16, b"\x00" * 4,
                               b"\x00" * 8, b"\x00" * 8, None)}


def _check_rb(entries, root):
    """Assert the sibling tree at `root` satisfies the MS-CFB ordering AND the
    red-black invariants Hancom validates. Returns the black-height."""
    if root != NOSTREAM:
        assert entries[root].color == BLACK, "root must be black"

    def bh(sid):
        if sid == NOSTREAM:
            return 1
        n = entries[sid]
        if n.left != NOSTREAM:
            assert _name_key(entries[n.left].name) < _name_key(n.name), "BST left order"
        if n.right != NOSTREAM:
            assert _name_key(entries[n.right].name) > _name_key(n.name), "BST right order"
        if n.color == RED:
            assert not cfb._is_red(entries, n.left), "red node has red left child"
            assert not cfb._is_red(entries, n.right), "red node has red right child"
        lh, rh = bh(n.left), bh(n.right)
        assert lh == rh, f"black-height mismatch {lh} != {rh}"
        return lh + (1 if n.color == BLACK else 0)

    return bh(root)


def test_rb_insert_invariants_randomized():
    """300 randomized insertion runs; after every insert the tree must keep
    BST order (CFB comparator), no red-red edges, equal black-height, and a
    black root — and every inserted name must remain findable."""
    rng = random.Random(1234)
    for _ in range(300):
        entries = _fresh_root()
        names = set()
        for _ in range(rng.randint(1, 60)):
            length = rng.randint(1, 12)
            name = "".join(rng.choice("ABxy0123_") for _ in range(length))
            if name in names:
                continue
            names.add(name)
            cfb.add_stream(entries, name, b"d-" + name.encode(), parent_sid=0)
            _check_rb(entries, entries[0].child)
        for name in names:
            assert cfb.find_entry(entries, name) is not None, f"lost {name!r}"


def test_add_stream_rejects_duplicate():
    entries = _fresh_root()
    cfb.add_stream(entries, "DUP", b"a", parent_sid=0)
    with pytest.raises(ValueError):
        cfb.add_stream(entries, "DUP", b"b", parent_sid=0)


def test_add_storage_is_idempotent():
    entries = _fresh_root()
    s1 = cfb.add_storage(entries, "Store")
    s2 = cfb.add_storage(entries, "Store")  # already exists → same sid
    assert s1 == s2


# --------------------------------------------------------------------------- #
#  real-file integration (needs a fixture)                                      #
# --------------------------------------------------------------------------- #
FIXTURE = os.environ.get("HWPKIT_FIXTURE")

requires_fixture = pytest.mark.skipif(
    not FIXTURE or not os.path.exists(FIXTURE),
    reason="set HWPKIT_FIXTURE=path/to/file.hwp to enable",
)


@requires_fixture
def test_add_streams_preserves_original_and_validates(tmp_path):
    """Add a new stream (into a new storage) to a real HWP, dump it, reopen
    through olefile (an independent CFB parser — so the directory tree must
    validate), and assert: every original stream survives byte-for-byte and
    the new stream reads back exactly."""
    import olefile

    src = FIXTURE
    out = str(tmp_path / "added.hwp")

    a = olefile.OleFileIO(src)
    orig = {"/".join(s): a.openstream("/".join(s)).read()
            for s in a.listdir(streams=True)}
    a.close()

    entries = cfb.load(src)
    store = cfb.add_storage(entries, "HwpkitTest")
    payload = b"\x89PNG\r\n\x1a\n" + b"PAYLOAD" * 64
    cfb.add_stream(entries, "blob.bin", payload, parent_sid=store)
    cfb.dump(entries, out)

    b = olefile.OleFileIO(out)
    try:
        got = {"/".join(s): b.openstream("/".join(s)).read()
               for s in b.listdir(streams=True)}
    finally:
        b.close()

    for key, data in orig.items():
        assert key in got, f"original stream {key!r} vanished"
        assert got[key] == data, f"original stream {key!r} changed"
    assert got["HwpkitTest/blob.bin"] == payload
