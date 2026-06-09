"""Tests for hwpkit.picture (image insertion).

The DocInfo / record-patching / anchoring logic is verified structurally
here. The end-to-end test is gated on HWPKIT_FIXTURE and proves the output
re-validates as a CFB and re-parses as records — but whether Hancom
*renders* the picture must be checked by opening the file in Hancom.
"""

from __future__ import annotations

import os
import struct

import pytest

from hwpkit import records as R
from hwpkit import picture as P
from hwpkit import _picture_donor as D


def test_gso_inline_control_shape():
    assert len(P.GSO_INLINE) == 16
    assert P.GSO_INLINE_CODE_UNITS == 8
    assert P.GSO_INLINE[0:2] == b"\x0b\x00"          # control start
    assert P.GSO_INLINE[2:6] == b"\x20\x6f\x73\x67"  # "gso " reversed
    assert P.GSO_INLINE[-2:] == b"\x0b\x00"          # control end


def test_px_and_mm_conversions():
    assert P.PX_TO_HWPUNIT == 75              # 7200 / 96
    assert P.mm_to_hwpunit(25.4) == 7200      # 1 inch


def _fake_docinfo(bindata_count, n_existing_bindata=0):
    body = struct.pack("<I", bindata_count) + b"\x00" * 20  # ID_MAPPINGS array
    recs = [{"tag": P.TAG_ID_MAPPINGS, "level": 0, "size": len(body),
             "header_len": 4, "body": body, "offset": -1}]
    for k in range(n_existing_bindata):
        b = struct.pack("<HHH", 0x0001, k + 1, 3) + "jpg".encode("utf-16-le")
        recs.append({"tag": P.TAG_BIN_DATA, "level": 1, "size": len(b),
                     "header_len": 4, "body": b, "offset": -1})
    # a trailing non-bindata record to prove insertion lands in the right spot
    recs.append({"tag": 0x13, "level": 1, "size": 0, "header_len": 4,
                 "body": b"", "offset": -1})
    return recs


def test_register_bindata_bumps_count_and_appends_record():
    di = _fake_docinfo(bindata_count=2, n_existing_bindata=2)
    new_id = P.register_bindata(di, "png")
    assert new_id == 3
    # count bumped
    assert struct.unpack_from("<I", di[0]["body"], 0)[0] == 3
    # new BIN_DATA inserted right after the last existing one (index 3), not at the end
    new = di[3]
    assert new["tag"] == P.TAG_BIN_DATA
    attr, bid, extlen = struct.unpack_from("<HHH", new["body"], 0)
    assert (attr, bid, extlen) == (0x0001, 3, 3)
    assert new["body"][6:].decode("utf-16-le") == "png"
    # the trailing 0x13 record is now last → insertion was positional, not appended
    assert di[-1]["tag"] == 0x13


def test_register_bindata_with_no_existing_bindata():
    di = _fake_docinfo(bindata_count=0, n_existing_bindata=0)
    new_id = P.register_bindata(di, ".PNG")  # leading dot + uppercase tolerated
    assert new_id == 1
    assert di[1]["tag"] == P.TAG_BIN_DATA
    assert di[1]["body"][6:].decode("utf-16-le") == "png"


def test_build_picture_records_patches_fields():
    recs = P.build_picture_records(bin_id=7, native_w=600, native_h=300,
                                   disp_w=200, disp_h=100, para_level=2)
    ch, sc, pic = recs
    assert (ch["tag"], ch["level"]) == (P.TAG_CTRL_HEADER, 3)
    assert (sc["tag"], sc["level"]) == (P.TAG_SHAPE_COMPONENT, 4)
    assert (pic["tag"], pic["level"]) == (P.TAG_SHAPE_COMPONENT_PICTURE, 5)
    # bin id
    assert struct.unpack_from("<H", pic["body"], D.PIC_BIN_ID)[0] == 7
    # display box in CTRL_HEADER
    assert struct.unpack_from("<I", ch["body"], D.CH_DISP_W)[0] == 200
    assert struct.unpack_from("<I", ch["body"], D.CH_DISP_H)[0] == 100
    # native + display in SHAPE_COMPONENT
    assert struct.unpack_from("<I", sc["body"], D.SC_NATIVE_W)[0] == 600
    assert struct.unpack_from("<I", sc["body"], D.SC_DISP_W)[0] == 200
    # source rectangle corner points (0,0),(W,0),(W,H),(0,H)
    pts = [struct.unpack_from("<ii", pic["body"], D.PIC_RECT + 8 * k) for k in range(4)]
    assert pts == [(0, 0), (600, 0), (600, 300), (0, 300)]


def test_anchor_picture_into_empty_paragraph():
    # synthetic section: empty paragraph (chars=1, no PARA_TEXT) + lineseg, then next para
    ph = {"tag": R.TAG_PARA_HEADER, "level": 2, "size": 4, "header_len": 4,
          "body": struct.pack("<I", 1), "offset": -1}
    cs = {"tag": R.TAG_PARA_CHAR_SHAPE, "level": 3, "size": 8, "header_len": 4,
          "body": b"\x00" * 8, "offset": -1}
    ls = {"tag": R.TAG_PARA_LINE_SEG, "level": 3, "size": 36, "header_len": 4,
          "body": b"\x11" * 36, "offset": -1}
    ph2 = {"tag": R.TAG_PARA_HEADER, "level": 2, "size": 4, "header_len": 4,
           "body": struct.pack("<I", 1), "offset": -1}
    sec = [ph, cs, ls, ph2]

    pics = P.build_picture_records(3, 600, 300, 200, 100, para_level=2)
    P.anchor_picture(sec, 0, pics)

    # char count bumped 1 -> 9
    assert struct.unpack_from("<I", sec[0]["body"], 0)[0] & 0x7FFFFFFF == 9
    # a PARA_TEXT was created carrying the inline control
    pt = sec[1]
    assert pt["tag"] == R.TAG_PARA_TEXT
    assert pt["body"].startswith(P.GSO_INLINE)
    # lineseg dummied to 36 zero bytes
    ls_new = next(r for r in sec if r["tag"] == R.TAG_PARA_LINE_SEG)
    assert ls_new["body"] == b"\x00" * 36
    # the 3 picture records were inserted before the 2nd PARA_HEADER, at right levels
    tags = [r["tag"] for r in sec]
    i_pic = tags.index(P.TAG_SHAPE_COMPONENT_PICTURE)
    i_ph2 = [k for k, t in enumerate(tags) if t == R.TAG_PARA_HEADER][1]
    assert i_pic < i_ph2
    assert tags[i_pic - 2:i_pic + 1] == [P.TAG_CTRL_HEADER, P.TAG_SHAPE_COMPONENT,
                                         P.TAG_SHAPE_COMPONENT_PICTURE]


# --------------------------------------------------------------------------- #
#  end-to-end (needs a fixture); Hancom render still must be checked by hand    #
# --------------------------------------------------------------------------- #
FIXTURE = os.environ.get("HWPKIT_FIXTURE")
requires_fixture = pytest.mark.skipif(
    not FIXTURE or not os.path.exists(FIXTURE),
    reason="set HWPKIT_FIXTURE=path/to/file.hwp to enable",
)


@requires_fixture
def test_place_image_end_to_end_structural(tmp_path):
    """place_image on a real template: the output must (a) re-validate as a CFB
    via olefile, (b) gain a BinData stream, (c) have DocInfo BinData count
    bumped, (d) re-parse cleanly as records. (Hancom-render check is manual.)"""
    import olefile
    from PIL import Image
    from hwpkit import cfb
    from hwpkit.pipeline import docinfo_sid, file_header_compressed

    seal = tmp_path / "seal.png"
    Image.new("RGBA", (200, 80), (200, 0, 0, 255)).save(seal)
    out = str(tmp_path / "with_image.hwp")

    # bindata count before
    e0 = cfb.load(FIXTURE)
    comp = file_header_compressed(e0)
    di0 = R.parse(R.decompress(e0[docinfo_sid(e0)].data) if comp else e0[docinfo_sid(e0)].data)
    idm0 = next(r for r in di0 if r["tag"] == P.TAG_ID_MAPPINGS)
    count0 = struct.unpack_from("<I", idm0["body"], 0)[0]

    bin_id = P.place_image(FIXTURE, out, str(seal), paragraph_index=0, width_mm=30)

    r = olefile.OleFileIO(out)  # independent CFB parser must accept it
    streams = {"/".join(s) for s in r.listdir(streams=True)}
    r.close()
    assert any(p.startswith("BinData/BIN%04d" % bin_id) for p in streams), streams

    e1 = cfb.load(out)
    di1 = R.parse(R.decompress(e1[docinfo_sid(e1)].data) if comp else e1[docinfo_sid(e1)].data)
    idm1 = next(r for r in di1 if r["tag"] == P.TAG_ID_MAPPINGS)
    assert struct.unpack_from("<I", idm1["body"], 0)[0] == count0 + 1
    # section re-parses and contains a picture record
    sec = R.parse(R.decompress(e1[cfb.find_entry(e1, "BodyText", "Section0")].data)
                  if comp else e1[cfb.find_entry(e1, "BodyText", "Section0")].data)
    assert any(rr["tag"] == P.TAG_SHAPE_COMPONENT_PICTURE for rr in sec)
