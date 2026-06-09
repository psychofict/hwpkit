"""Tests for the OO binary editor (hwpkit.hwp.HwpFile) and the unified
open_document() dispatcher.

HwpFile needs a real .hwp container, so its integration tests are gated on
HWPKIT_FIXTURE (like test_roundtrip.py). The dispatcher's .hwpx branch is
exercised with a synthetic file and needs lxml.
"""

from __future__ import annotations

import os
import zipfile

import pytest

from hwpkit import open_document
from hwpkit.hwp import HwpFile

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"


def test_open_document_dispatches_to_hwpxfile(tmp_path):
    pytest.importorskip("lxml")
    from hwpkit.hwpx import HwpxFile
    p = tmp_path / "d.hwpx"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("mimetype", b"application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("Contents/section0.xml",
                    f'<hs:sec xmlns:hs="{HS}" xmlns:hp="{HP}">'
                    f'<hp:p><hp:run><hp:t>안녕</hp:t></hp:run></hp:p></hs:sec>')
    doc = open_document(str(p))
    assert isinstance(doc, HwpxFile)
    assert doc.paragraph_text(0) == "안녕"


# --------------------------------------------------------------------------- #
#  real-file integration (needs a binary .hwp fixture)                          #
# --------------------------------------------------------------------------- #
FIXTURE = os.environ.get("HWPKIT_FIXTURE")
requires_fixture = pytest.mark.skipif(
    not FIXTURE or not os.path.exists(FIXTURE),
    reason="set HWPKIT_FIXTURE=path/to/file.hwp to enable",
)


@requires_fixture
def test_open_document_returns_hwpfile_for_hwp():
    doc = open_document(FIXTURE)
    assert isinstance(doc, HwpFile)
    assert len(doc) > 0


@requires_fixture
def test_hwpfile_text_edit_roundtrip(tmp_path):
    out = str(tmp_path / "edited.hwp")
    doc = HwpFile.open(FIXTURE)
    n = len(doc)
    target = next(i for i, t in doc.paragraphs() if t.strip())
    doc.replace_text(target, "○HWPKIT_OO_SENTINEL○")
    doc.save(out)

    doc2 = HwpFile.open(out)
    assert len(doc2) == n                                   # structure intact
    assert doc2.paragraph_text(target) == "○HWPKIT_OO_SENTINEL○"


@requires_fixture
def test_hwpfile_place_image(tmp_path):
    pytest.importorskip("PIL")
    from PIL import Image
    from hwpkit import cfb, records as R
    from hwpkit.pipeline import file_header_compressed
    from hwpkit.picture import TAG_SHAPE_COMPONENT_PICTURE

    seal = tmp_path / "seal.png"
    Image.new("RGBA", (160, 64), (0, 0, 200, 255)).save(seal)
    out = str(tmp_path / "with_image.hwp")

    doc = HwpFile.open(FIXTURE)
    bin_id = doc.place_image(0, str(seal), width_mm=25)
    doc.save(out)

    entries = cfb.load(out)                                 # re-validates as CFB
    assert cfb.find_entry(entries, "BinData", "BIN%04d.png" % bin_id) is not None
    comp = file_header_compressed(entries)
    sid = cfb.find_entry(entries, "BodyText", "Section0")
    raw = entries[sid].data
    sec = R.parse(R.decompress(raw) if comp else raw)
    assert any(r["tag"] == TAG_SHAPE_COMPONENT_PICTURE for r in sec)
