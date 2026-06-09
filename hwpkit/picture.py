"""Insert an image (seal / signature / stamp) into a binary HWP 5.0 file.

Inserting a picture touches three places (see docs/RECORD_FORMAT.md
"Embedded images" and docs/OBJECT_MODEL.md):

  1. CFB container  — add a `BinData/BIN%04d.<ext>` stream (the bytes).
  2. DocInfo        — bump `ID_MAPPINGS[0]` (BinData count) and append a
                      `BIN_DATA` record pointing at the stream.
  3. BodyText       — clone a bundled, Hancom-authored picture-object
                      record chain (`gso -> $pic -> SHAPE_COMPONENT_PICTURE`),
                      patch its bin-id + extents, and anchor it with an
                      inline GSO control in a target paragraph.

The picture-object bytes come from a real Hancom file (see
`_picture_donor`), so they are byte-identical to genuine output — only the
bin-id and the size fields are patched.

Extents use HWPUNIT = 1/7200 inch; a bitmap's native extent is pixels x 75
(= 7200/96, i.e. assume 96 px/inch). See GOTCHAS.md §5.

    from hwpkit.picture import place_image
    place_image("form.hwp", "out.hwp", "seal.png",
                paragraph_index=42, width_mm=30)

NOTE: the CFB + DocInfo steps are structurally verified here (round-trip,
re-parse, olefile re-validation). Whether Hancom *renders* the picture is
not locally checkable (LibreOffice can't open these files) — open the
output in Hancom to confirm, and report back so the donor can be tuned.
"""

from __future__ import annotations

import struct
from typing import List, Optional

from . import cfb
from . import records as R
from . import _picture_donor as D
from .pipeline import section0_sid, docinfo_sid, file_header_compressed

TAG_ID_MAPPINGS = 0x11
TAG_BIN_DATA = 0x12
TAG_CTRL_HEADER = 0x47
TAG_SHAPE_COMPONENT = 0x4C
TAG_SHAPE_COMPONENT_PICTURE = 0x55

PX_TO_HWPUNIT = 75            # 7200 / 96  (assume 96 px/inch); see GOTCHAS §5
HWPUNIT_PER_MM = 7200 / 25.4  # 1/7200 inch per unit

# Inline anchor for a GSO control inside PARA_TEXT: 8 code units (16 bytes) =
# [0x0B] + ctrl-id "gso " stored reversed + 8 zero bytes + [0x0B].
GSO_INLINE = b"\x0b\x00" + b"\x20\x6f\x73\x67" + b"\x00" * 8 + b"\x0b\x00"
GSO_INLINE_CODE_UNITS = len(GSO_INLINE) // 2   # 8


def mm_to_hwpunit(mm: float) -> int:
    return round(mm * HWPUNIT_PER_MM)


# --------------------------------------------------------------------------- #
#  2. DocInfo — register the binary                                             #
# --------------------------------------------------------------------------- #
def _bindata_indices(di: List[dict]):
    return [i for i, r in enumerate(di) if r["tag"] == TAG_BIN_DATA]


def register_bindata(docinfo_records: List[dict], ext: str) -> int:
    """Register a new embedded binary in DocInfo: bump the BinData count in
    `ID_MAPPINGS` and append a `BIN_DATA` record (type=embedding). Returns the
    new bin id (1-based, matches the `%04d` in the stream name). Mutates the
    record list in place.
    """
    # bump ID_MAPPINGS[0] (BinData count)
    idm = next((r for r in docinfo_records if r["tag"] == TAG_ID_MAPPINGS), None)
    if idm is None:
        raise ValueError("DocInfo has no ID_MAPPINGS record")
    body = bytearray(idm["body"])
    count = struct.unpack_from("<I", body, 0)[0]
    new_id = count + 1
    struct.pack_into("<I", body, 0, new_id)
    idm["body"] = bytes(body)

    # build the BIN_DATA record:  <attr u16=0x0001 embed><id u16><extlen u16><ext utf16le>
    ext = ext.lstrip(".").lower()
    ext_b = ext.encode("utf-16-le")
    rec_body = struct.pack("<HHH", 0x0001, new_id, len(ext)) + ext_b
    bin_rec = {
        "tag": TAG_BIN_DATA, "level": 1, "size": len(rec_body),
        "header_len": 4, "body": rec_body, "offset": -1,
    }

    # insert after the last existing BIN_DATA, else right after ID_MAPPINGS
    existing = _bindata_indices(docinfo_records)
    if existing:
        pos = existing[-1] + 1
    else:
        pos = docinfo_records.index(idm) + 1
    docinfo_records.insert(pos, bin_rec)
    return new_id


# --------------------------------------------------------------------------- #
#  3. BodyText — picture object (donor clone) + inline anchor                   #
# --------------------------------------------------------------------------- #
def _mkrec(tag: int, level: int, body: bytes) -> dict:
    rec = {"tag": tag, "level": level, "size": len(body),
           "header_len": 4, "body": bytes(body), "offset": -1}
    if len(body) >= 0xFFF:
        rec["force_extended_header"] = True
        rec["header_len"] = 8
    return rec


def build_picture_records(bin_id: int, native_w: int, native_h: int,
                          disp_w: int, disp_h: int, para_level: int) -> List[dict]:
    """Clone the bundled donor picture-object chain and patch its bin-id and
    extents (all HWPUNIT). Returns [CTRL_HEADER, SHAPE_COMPONENT,
    SHAPE_COMPONENT_PICTURE] at the correct levels for a host paragraph at
    `para_level`."""
    ch = bytearray(D.CTRL_HEADER)
    sc = bytearray(D.SHAPE_COMPONENT)
    pic = bytearray(D.PICTURE)

    struct.pack_into("<I", ch, D.CH_DISP_W, disp_w)
    struct.pack_into("<I", ch, D.CH_DISP_H, disp_h)
    struct.pack_into("<I", sc, D.SC_NATIVE_W, native_w)
    struct.pack_into("<I", sc, D.SC_NATIVE_H, native_h)
    struct.pack_into("<I", sc, D.SC_DISP_W, disp_w)
    struct.pack_into("<I", sc, D.SC_DISP_H, disp_h)
    struct.pack_into("<H", pic, D.PIC_BIN_ID, bin_id)
    # source image rectangle: (0,0),(W,0),(W,H),(0,H)
    off = D.PIC_RECT
    for x, y in ((0, 0), (native_w, 0), (native_w, native_h), (0, native_h)):
        struct.pack_into("<i", pic, off, x)
        struct.pack_into("<i", pic, off + 4, y)
        off += 8

    return [
        _mkrec(TAG_CTRL_HEADER, para_level + 1, ch),
        _mkrec(TAG_SHAPE_COMPONENT, para_level + 2, sc),
        _mkrec(TAG_SHAPE_COMPONENT_PICTURE, para_level + 3, pic),
    ]


def anchor_picture(section_records: List[dict], paragraph_index: int,
                   picture_records: List[dict]):
    """Insert the GSO inline control into paragraph `paragraph_index` and place
    the picture-object records after that paragraph's cached layout. Bumps the
    paragraph char count by 8 and dummies its PARA_LINE_SEG. Mutates in place."""
    para_starts = R.index_paragraphs(section_records)
    pr_idx = para_starts[paragraph_index]
    para = section_records[pr_idx]
    para_level = para["level"]

    # bump char count by the 8-code-unit control
    body = bytearray(para["body"])
    chars_raw = struct.unpack_from("<I", body, 0)[0]
    high = chars_raw & 0x80000000
    chars = chars_raw & 0x7FFFFFFF
    struct.pack_into("<I", body, 0, high | ((chars + GSO_INLINE_CODE_UNITS) & 0x7FFFFFFF))
    para["body"] = bytes(body)

    # insert the control into PARA_TEXT (create one for an empty paragraph)
    pt_idx = pr_idx + 1 if (pr_idx + 1 < len(section_records)
                            and section_records[pr_idx + 1]["tag"] == R.TAG_PARA_TEXT) else None
    if pt_idx is None:
        pt_rec = _mkrec(R.TAG_PARA_TEXT, para_level + 1, GSO_INLINE + b"\x0d\x00")
        section_records.insert(pr_idx + 1, pt_rec)
        pt_idx = pr_idx + 1
    else:
        pt = section_records[pt_idx]
        tb = pt["body"]
        # place the control at the front, before any existing text/terminator
        pt["body"] = GSO_INLINE + tb
        pt["size"] = len(pt["body"])
        if pt["size"] >= 0xFFF:
            pt["force_extended_header"] = True
            pt["header_len"] = 8

    # dummy the PARA_LINE_SEG so Hancom recomputes layout (GOTCHAS §2)
    R._regenerate_lineseg(section_records, pr_idx, chars + GSO_INLINE_CODE_UNITS)

    # find the insertion point: after the host paragraph's layout records,
    # before the next PARA_HEADER
    ins = pr_idx + 1
    j = pr_idx + 1
    while j < len(section_records) and section_records[j]["tag"] != R.TAG_PARA_HEADER:
        if section_records[j]["tag"] in (R.TAG_PARA_TEXT, R.TAG_PARA_CHAR_SHAPE,
                                         R.TAG_PARA_LINE_SEG):
            ins = j + 1
        j += 1
    for k, rec in enumerate(picture_records):
        section_records.insert(ins + k, rec)


# --------------------------------------------------------------------------- #
#  high-level orchestration                                                     #
# --------------------------------------------------------------------------- #
def place_image(input_path: str, output_path: str, image_path: str,
                paragraph_index: int, width_mm: Optional[float] = None,
                section: str = "Section0"):
    """Embed `image_path` into `input_path` and anchor it in paragraph
    `paragraph_index` of the given BodyText section; write `output_path`.

    `width_mm` sets the displayed width (height follows the image's aspect
    ratio); if omitted, the image is shown at its native pixel size.
    Returns the new bin id.
    """
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover
        raise ImportError("place_image needs Pillow — `pip install hwpkit[image]`")
    img = Image.open(image_path)
    px_w, px_h = img.size
    ext = image_path.rsplit(".", 1)[-1].lower()

    native_w = px_w * PX_TO_HWPUNIT
    native_h = px_h * PX_TO_HWPUNIT
    if width_mm:
        disp_w = mm_to_hwpunit(width_mm)
        disp_h = round(disp_w * px_h / px_w)
    else:
        disp_w, disp_h = native_w, native_h

    entries = cfb.load(input_path)
    compressed = file_header_compressed(entries)

    # ---- DocInfo: register the binary ----
    di_sid = docinfo_sid(entries)
    di_raw = entries[di_sid].data
    di = R.parse(R.decompress(di_raw) if compressed else di_raw)
    bin_id = register_bindata(di, ext)
    di_out = R.serialize(di)
    entries[di_sid].data = R.compress(di_out) if compressed else di_out

    # ---- CFB: add the image bytes as BinData/BIN%04d.<ext> ----
    raw_img = img_bytes(image_path)
    stream_data = R.compress(raw_img) if compressed else raw_img
    store = cfb.add_storage(entries, "BinData")
    cfb.add_stream(entries, "BIN%04d.%s" % (bin_id, ext), stream_data, parent_sid=store)

    # ---- BodyText: picture object + inline anchor ----
    sec_sid = _section_sid(entries, section)
    sec_raw = entries[sec_sid].data
    sec = R.parse(R.decompress(sec_raw) if compressed else sec_raw)
    para_level = sec[R.index_paragraphs(sec)[paragraph_index]]["level"]
    pic_recs = build_picture_records(bin_id, native_w, native_h, disp_w, disp_h, para_level)
    anchor_picture(sec, paragraph_index, pic_recs)
    sec_out = R.serialize(sec)
    entries[sec_sid].data = R.compress(sec_out) if compressed else sec_out

    cfb.dump(entries, output_path)
    return bin_id


def img_bytes(image_path: str) -> bytes:
    with open(image_path, "rb") as f:
        return f.read()


def _section_sid(entries, section: str) -> int:
    sid = cfb.find_entry(entries, "BodyText", section)
    if sid is None:
        raise ValueError(f"BodyText/{section} not found")
    return sid
