"""Tests for .hwpx (OWPML) text extraction.

A minimal .hwpx is built in-test, so these run without any fixture (lxml
must be installed — it's the hwpx extra). An optional real-file check is
gated on HWPKIT_HWPX_FIXTURE.
"""

from __future__ import annotations

import os
import zipfile

import pytest

pytest.importorskip("lxml")

from hwpkit import hwpx
from hwpkit.extract import extract_text_from_file

HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"

SECTION_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<hs:sec xmlns:hs="{HS}" xmlns:hp="{HP}">
  <hp:p><hp:run><hp:t>첫째 줄</hp:t></hp:run></hp:p>
  <hp:p><hp:run><hp:t>둘째 </hp:t><hp:t>줄</hp:t></hp:run></hp:p>
  <hp:p><hp:run>
    <hp:tbl><hp:tr><hp:tc><hp:subList>
      <hp:p><hp:run><hp:t>셀 텍스트</hp:t></hp:run></hp:p>
    </hp:subList></hp:tc></hp:tr></hp:tbl>
  </hp:run></hp:p>
</hs:sec>"""


def _make_hwpx(path, with_mimetype=True):
    with zipfile.ZipFile(path, "w") as zf:
        if with_mimetype:
            zf.writestr("mimetype", b"application/hwp+zip")
        zf.writestr("Contents/section0.xml", SECTION_XML)


def test_extract_text_from_hwpx(tmp_path):
    p = tmp_path / "doc.hwpx"
    _make_hwpx(p)
    text = hwpx.extract_text_from_hwpx(str(p))
    lines = [l for l in text.split("\n") if l.strip()]
    assert lines == ["첫째 줄", "둘째 줄", "셀 텍스트"]


def test_multiple_sections_in_order(tmp_path):
    p = tmp_path / "multi.hwpx"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("mimetype", b"application/hwp+zip")
        for i, word in enumerate(["악", "비", "차"]):
            zf.writestr(
                f"Contents/section{i}.xml",
                f'<hs:sec xmlns:hs="{HS}" xmlns:hp="{HP}">'
                f"<hp:p><hp:run><hp:t>{word}</hp:t></hp:run></hp:p></hs:sec>",
            )
    text = hwpx.extract_text_from_hwpx(str(p))
    assert [l for l in text.split("\n") if l.strip()] == ["악", "비", "차"]


def test_is_hwpx_detection(tmp_path):
    p = tmp_path / "doc.hwpx"
    _make_hwpx(p)
    assert hwpx.is_hwpx(str(p)) is True

    # mimetype omitted but section layout present → still detected
    p2 = tmp_path / "nomime.hwpx"
    _make_hwpx(p2, with_mimetype=False)
    assert hwpx.is_hwpx(str(p2)) is True

    # a binary .hwp (CFB magic, not a zip) is not hwpx
    fake_hwp = tmp_path / "fake.hwp"
    fake_hwp.write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 64)
    assert hwpx.is_hwpx(str(fake_hwp)) is False


def test_dispatcher_routes_hwpx(tmp_path):
    p = tmp_path / "doc.hwpx"
    _make_hwpx(p)
    text = extract_text_from_file(str(p))
    assert "셀 텍스트" in text


# --------------------------------------------------------------------------- #
#  editing                                                                      #
# --------------------------------------------------------------------------- #
EDIT_XML = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hs:sec xmlns:hs="{HS}" xmlns:hp="{HP}">
  <hp:p><hp:run charPrIDRef="7"><hp:t>이름</hp:t></hp:run></hp:p>
  <hp:p><hp:run charPrIDRef="7"><hp:t></hp:t></hp:run></hp:p>
  <hp:p><hp:run charPrIDRef="7"><hp:t>□ 동의함</hp:t></hp:run></hp:p>
  <hp:p><hp:run charPrIDRef="7"><hp:t>학력: </hp:t></hp:run><hp:run charPrIDRef="9"><hp:t>학사</hp:t></hp:run></hp:p>
</hs:sec>"""


def _make_editable(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", b"application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("Contents/section0.xml", EDIT_XML)
        zf.writestr("version.xml", b"<x/>")


def test_paragraph_indexing_and_text(tmp_path):
    p = tmp_path / "f.hwpx"
    _make_editable(p)
    doc = hwpx.HwpxFile.open(str(p))
    assert len(doc) == 4
    assert doc.paragraph_text(0) == "이름"
    assert doc.paragraph_text(1) == ""             # empty
    assert doc.paragraph_text(3) == "학력: 학사"     # spans two runs


def test_inject_replace_swap_roundtrip(tmp_path):
    p = tmp_path / "f.hwpx"
    out = tmp_path / "out.hwpx"
    _make_editable(p)

    doc = hwpx.HwpxFile.open(str(p))
    doc.inject_text(1, "홍길동")
    doc.replace_text(3, "학력: 박사")
    doc.swap_in_para_text(2, "□", "☑")
    doc.save(str(out))

    # reopen the SAVED file (proves the zip re-serialized and re-parses)
    doc2 = hwpx.HwpxFile.open(str(out))
    assert doc2.paragraph_text(1) == "홍길동"
    assert doc2.paragraph_text(2) == "☑ 동의함"
    assert doc2.paragraph_text(3) == "학력: 박사"
    # extraction sees the edits too
    text = hwpx.extract_text_from_hwpx(str(out))
    assert "홍길동" in text and "☑ 동의함" in text and "박사" in text


def test_inject_rejects_nonempty(tmp_path):
    p = tmp_path / "f.hwpx"
    _make_editable(p)
    doc = hwpx.HwpxFile.open(str(p))
    with pytest.raises(ValueError):
        doc.inject_text(0, "x")   # P0 already has "이름"


def test_swap_missing_raises(tmp_path):
    p = tmp_path / "f.hwpx"
    _make_editable(p)
    doc = hwpx.HwpxFile.open(str(p))
    with pytest.raises(ValueError):
        doc.swap_in_para_text(0, "없음", "X")


def test_save_preserves_unmodified_entries_and_mimetype(tmp_path):
    p = tmp_path / "f.hwpx"
    out = tmp_path / "out.hwpx"
    _make_editable(p)
    doc = hwpx.HwpxFile.open(str(p))
    doc.replace_text(0, "성명")
    doc.save(str(out))
    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert names[0] == "mimetype"                       # first entry
        assert zf.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
        assert zf.read("version.xml") == b"<x/>"            # untouched, verbatim
        assert "application/hwp+zip" == zf.read("mimetype").decode()


def test_fill_hwpx_helper(tmp_path):
    p = tmp_path / "f.hwpx"
    out = tmp_path / "out.hwpx"
    _make_editable(p)
    hwpx.fill_hwpx(str(p), str(out), lambda d: d.replace_text(0, "성명"))
    assert hwpx.HwpxFile.open(str(out)).paragraph_text(0) == "성명"


# --------------------------------------------------------------------------- #
#  image insertion                                                              #
# --------------------------------------------------------------------------- #
HC = "http://www.hancom.co.kr/hwpml/2011/core"
OPF = "http://www.idpf.org/2007/opf/"

PIC_SEC = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<hs:sec xmlns:hs="{HS}" xmlns:hp="{HP}" xmlns:hc="{HC}">
  <hp:p><hp:run charPrIDRef="3"><hp:t>날인:</hp:t></hp:run></hp:p>
  <hp:p><hp:run charPrIDRef="3"></hp:run></hp:p>
</hs:sec>"""

PIC_HPF = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<opf:package xmlns:opf="{OPF}" xmlns:hp="{HP}">
  <opf:manifest>
    <opf:item id="section0" href="Contents/section0.xml" media-type="application/xml"/>
  </opf:manifest>
  <opf:spine><opf:itemref idref="section0" linear="yes"/></opf:spine>
</opf:package>"""


def _make_with_hpf(path):
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", b"application/hwp+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("Contents/content.hpf", PIC_HPF)
        zf.writestr("Contents/section0.xml", PIC_SEC)


def _seal(path, size=(200, 80)):
    Image = pytest.importorskip("PIL.Image")
    Image.new("RGBA", size, (200, 0, 0, 255)).save(path)


def test_place_image_wires_all_three_parts(tmp_path):
    pytest.importorskip("PIL")
    from lxml import etree
    seal = tmp_path / "seal.png"
    _seal(seal, (200, 80))
    src = tmp_path / "f.hwpx"
    out = tmp_path / "out.hwpx"
    _make_with_hpf(src)

    doc = hwpx.HwpxFile.open(str(src))
    item = doc.place_image(1, str(seal), width_mm=30)
    assert item == "image1"
    doc.save(str(out))

    with zipfile.ZipFile(out) as z:
        # 1. bytes stored under BinData, byte-identical
        assert "BinData/image1.png" in z.namelist()
        assert z.read("BinData/image1.png") == seal.read_bytes()
        # 2. content.hpf registers the embedded item
        hpf = z.read("Contents/content.hpf").decode()
        assert 'href="BinData/image1.png"' in hpf
        assert 'isEmbeded="1"' in hpf
        assert 'media-type="image/png"' in hpf
        # 3. section anchors a <hp:pic> referencing that id, sized px×75
        root = etree.fromstring(z.read("Contents/section0.xml"))
        pics = root.findall(".//{%s}pic" % HP)
        assert len(pics) == 1
        assert pics[0].find("{%s}img" % HC).get("binaryItemIDRef") == "image1"
        org = pics[0].find("{%s}orgSz" % HP)
        assert org.get("width") == str(200 * 75)
        assert org.get("height") == str(80 * 75)
        sz = pics[0].find("{%s}sz" % HP)
        assert int(sz.get("width")) == round(30 * 7200 / 25.4)


def test_place_image_native_size_and_id_increment(tmp_path):
    pytest.importorskip("PIL")
    from lxml import etree
    s1 = tmp_path / "a.png"; _seal(s1, (100, 100))
    s2 = tmp_path / "b.png"; _seal(s2, (50, 50))
    src = tmp_path / "f.hwpx"; out = tmp_path / "out.hwpx"
    _make_with_hpf(src)

    doc = hwpx.HwpxFile.open(str(src))
    assert doc.place_image(0, str(s1)) == "image1"     # native size
    assert doc.place_image(1, str(s2)) == "image2"     # id increments
    doc.save(str(out))

    with zipfile.ZipFile(out) as z:
        assert "BinData/image1.png" in z.namelist()
        assert "BinData/image2.png" in z.namelist()
        root = etree.fromstring(z.read("Contents/section0.xml"))
        pics = root.findall(".//{%s}pic" % HP)
        assert len(pics) == 2
        # native: curSz == orgSz, scaMatrix == 1
        org = pics[0].find("{%s}orgSz" % HP); cur = pics[0].find("{%s}curSz" % HP)
        assert org.get("width") == cur.get("width") == str(100 * 75)
        # unique pic ids
        ids = {p.get("id") for p in pics} | {p.get("instid") for p in pics}
        assert len(ids) == 4


# --------------------------------------------------------------------------- #
#  optional real-file check                                                     #
# --------------------------------------------------------------------------- #
HWPX_FIXTURE = os.environ.get("HWPKIT_HWPX_FIXTURE")


@pytest.mark.skipif(not HWPX_FIXTURE or not os.path.exists(HWPX_FIXTURE),
                    reason="set HWPKIT_HWPX_FIXTURE=path/to/file.hwpx to enable")
def test_real_hwpx_has_substantial_text():
    text = hwpx.extract_text_from_hwpx(HWPX_FIXTURE)
    assert len(text) > 500
    assert "\n" in text


@pytest.mark.skipif(not HWPX_FIXTURE or not os.path.exists(HWPX_FIXTURE),
                    reason="set HWPKIT_HWPX_FIXTURE=path/to/file.hwpx to enable")
def test_real_hwpx_edit_roundtrip(tmp_path):
    """Edit one paragraph of a real Hancom .hwpx, save, reopen: the edit
    sticks and the rest of the (large) document is preserved."""
    out = str(tmp_path / "edited.hwpx")
    doc = hwpx.HwpxFile.open(HWPX_FIXTURE)
    n_before = len(doc)
    full_before = hwpx.extract_text_from_hwpx(HWPX_FIXTURE)
    # pick the first non-empty paragraph and overwrite it with a sentinel
    target = next(i for i, t in doc.paragraphs() if t.strip())
    doc.replace_text(target, "○HWPKIT_SENTINEL○")
    doc.save(out)

    doc2 = hwpx.HwpxFile.open(out)
    assert len(doc2) == n_before                       # structure intact
    assert doc2.paragraph_text(target) == "○HWPKIT_SENTINEL○"
    after = hwpx.extract_text_from_hwpx(out)
    assert "○HWPKIT_SENTINEL○" in after
    # the bulk of the document is unchanged (only one paragraph differs)
    assert abs(len(after) - len(full_before)) < 200
