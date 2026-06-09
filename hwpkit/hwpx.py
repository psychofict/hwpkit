"""Plain-text extraction from a .hwpx (OWPML) file.

`.hwpx` is the XML serialization of the same document model as binary
`.hwp` (see docs/OBJECT_MODEL.md) — a ZIP holding `Contents/section*.xml`
whose paragraphs are `<hp:p>` → `<hp:run>` → `<hp:t>`. Tables nest more
`<hp:p>` inside cells, so a document-order walk that breaks a line at each
`<hp:p>` yields clean, RAG-ready text including table-cell content.

    from hwpkit import extract_text_from_hwpx
    print(extract_text_from_hwpx("file.hwpx"))

This needs `lxml` (`pip install hwpkit[hwpx]`); it is imported lazily so
the binary `.hwp` path never requires it.
"""

from __future__ import annotations

import re
import zipfile

HP_NS = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HC_NS = "http://www.hancom.co.kr/hwpml/2011/core"
OPF_NS = "http://www.idpf.org/2007/opf/"
_SECTION_RE = re.compile(r"Contents/section\d+\.xml$", re.IGNORECASE)
_HPF_NAME = "Contents/content.hpf"
PX_TO_HWPUNIT = 75              # 7200 / 96 (assume 96 px/inch); see GOTCHAS §5
HWPUNIT_PER_MM = 7200 / 25.4
_MEDIA_TYPE = {"png": "image/png", "jpg": "image/jpg", "jpeg": "image/jpeg",
               "bmp": "image/bmp", "gif": "image/gif", "tif": "image/tiff",
               "tiff": "image/tiff"}


def _q(ns, tag):
    return "{%s}%s" % (ns, tag)


def _section_names(zf: zipfile.ZipFile):
    """Section XML parts in numeric order (section0, section1, …)."""
    names = [n for n in zf.namelist() if _SECTION_RE.search(n)]

    def order(n):
        m = re.search(r"section(\d+)\.xml$", n, re.IGNORECASE)
        return int(m.group(1)) if m else 0

    return sorted(names, key=order)


def _localname(tag) -> str:
    if not isinstance(tag, str):  # comments / PIs
        return ""
    return tag.rsplit("}", 1)[-1]


def _walk(el, lines):
    """Document-order walk. Start a new line at every <hp:p>; emit the full
    text of each <hp:t> (including nested inline text) without recursing into
    it again (so nothing is double-counted)."""
    name = _localname(el.tag)
    if name == "p":
        lines.append([])
    if name == "t":
        if lines:
            lines[-1].append("".join(el.itertext()))
        return
    for child in el:
        _walk(child, lines)


def extract_text_from_hwpx(path: str) -> str:
    """Read a .hwpx and return its plain text — one line per paragraph, in
    document order, across every section (table-cell text included)."""
    try:
        from lxml import etree
    except ImportError:  # pragma: no cover
        raise ImportError("HWPX support needs lxml — `pip install hwpkit[hwpx]`")

    with zipfile.ZipFile(path) as zf:
        sections = _section_names(zf)
        lines = []
        for name in sections:
            root = etree.fromstring(zf.read(name))
            _walk(root, lines)
    return "\n".join("".join(parts) for parts in lines)


def _p_tag():
    return "{%s}p" % HP_NS


def _own_t_elements(p):
    """The <hp:t> elements that belong to paragraph `p` itself — i.e. not
    inside a nested <hp:p> (table cells hold their own paragraphs, which get
    their own index)."""
    res = []

    def rec(el):
        for child in el:
            ln = _localname(child.tag)
            if ln == "p":
                continue  # nested paragraph — a different index
            if ln == "t":
                res.append(child)
            rec(child)

    rec(p)
    return res


def _para_text(p) -> str:
    return "".join("".join(t.itertext()) for t in _own_t_elements(p))


class HwpxFile:
    """In-memory editor for a .hwpx. Mirrors the binary edit API
    (`inject_text` / `replace_text` / `swap_in_para_text`) but on OWPML, so
    the same calling code works across both Hancom formats.

    Paragraphs are indexed in document order across every section (nested
    table-cell paragraphs included), matching `hwpkit.records.index_paragraphs`.
    There is no layout cache to invalidate — Hancom recomputes from the XML.

        from hwpkit.hwpx import HwpxFile
        doc = HwpxFile.open("form.hwpx")
        doc.replace_text(12, "홍길동")
        doc.swap_in_para_text(8, "□ 동의", "☑ 동의")
        doc.save("out.hwpx")
    """

    def __init__(self, path: str):
        from lxml import etree  # lazy: HWPX is optional
        self._etree = etree
        self._path = path
        self._entries = []          # [(ZipInfo, bytes)] in original order
        self._sections = []         # [(entry_index, lxml_root)]
        self._trees = {}            # entry_index -> lxml_root (sections + hpf)
        self._modified = set()      # entry indices whose XML changed
        self._paras = []            # [(section_pos, p_element)] doc order
        self._hpf_ei = None         # entry index of Contents/content.hpf
        self._hpf_root = None
        self._load()

    @classmethod
    def open(cls, path: str) -> "HwpxFile":
        return cls(path)

    def _load(self):
        etree = self._etree
        with zipfile.ZipFile(self._path) as zf:
            for info in zf.infolist():
                self._entries.append((info, zf.read(info.filename)))
        for ei, (info, data) in enumerate(self._entries):
            if _SECTION_RE.search(info.filename):
                root = etree.fromstring(data)
                self._sections.append((ei, root))
                self._trees[ei] = root
            elif info.filename == _HPF_NAME:
                self._hpf_ei = ei
                self._hpf_root = etree.fromstring(data)
                self._trees[ei] = self._hpf_root
        # sort sections by numeric order, then index every paragraph
        self._sections.sort(key=lambda er: self._entries[er[0]][0].filename)
        for spos, (_ei, root) in enumerate(self._sections):
            for p in root.iter(_p_tag()):
                self._paras.append((spos, p))

    # -- inspection -------------------------------------------------------- #
    def __len__(self):
        return len(self._paras)

    def paragraph_text(self, index: int) -> str:
        return _para_text(self._paras[index][1])

    def paragraphs(self):
        """Yield (index, text) for every paragraph — the HWPX analogue of
        `records.describe`, for locating which index is which form field."""
        for i, (_s, p) in enumerate(self._paras):
            yield i, _para_text(p)

    def describe(self) -> str:
        return "\n".join(f"P{i:3d}: {text[:70]!r}" for i, text in self.paragraphs())

    # -- edits ------------------------------------------------------------- #
    def _set_text(self, index: int, text: str):
        etree = self._etree
        spos, p = self._paras[index]
        ts = _own_t_elements(p)
        if ts:
            first = ts[0]
            for ch in list(first):
                first.remove(ch)
            first.text = text
            for extra in ts[1:]:
                extra.getparent().remove(extra)
        else:
            run = p.find("{%s}run" % HP_NS)
            if run is None:
                run = etree.SubElement(p, "{%s}run" % HP_NS)
            etree.SubElement(run, "{%s}t" % HP_NS).text = text
        self._modified.add(self._sections[spos][0])

    def replace_text(self, index: int, text: str):
        """Rewrite paragraph `index`'s entire text content (keeps the first
        run's char formatting; drops any extra runs' text)."""
        self._set_text(index, text)

    def inject_text(self, index: int, text: str):
        """Fill an empty paragraph. Raises if it already has text (use
        replace_text to overwrite)."""
        if self.paragraph_text(index) != "":
            raise ValueError(f"P{index} is not empty; use replace_text")
        self._set_text(index, text)

    def swap_in_para_text(self, index: int, old: str, new: str):
        """Replace the first occurrence of `old` with `new` inside paragraph
        `index` (e.g. a checkbox □ → ☑). `old` must lie within a single text
        run."""
        spos, p = self._paras[index]
        for t in _own_t_elements(p):
            joined = "".join(t.itertext())
            if t.text and old in t.text:
                t.text = t.text.replace(old, new, 1)
                self._modified.add(self._sections[spos][0])
                return
            if old in joined:
                raise ValueError(
                    f"P{index}: {old!r} spans inline elements; not a simple swap")
        raise ValueError(f"P{index} does not contain {old!r}")

    # -- images ------------------------------------------------------------ #
    def _next_image_id(self) -> str:
        n = 0
        if self._hpf_root is not None:
            for item in self._hpf_root.iter(_q(OPF_NS, "item")):
                m = re.match(r"image(\d+)$", item.get("id") or "")
                if m:
                    n = max(n, int(m.group(1)))
        return "image%d" % (n + 1)

    def _next_pic_ids(self):
        mx = 0
        for _ei, root in self._sections:
            for pic in root.iter(_q(HP_NS, "pic")):
                for a in ("id", "instid"):
                    v = pic.get(a)
                    if v and v.isdigit():
                        mx = max(mx, int(v))
        base = max(mx + 1, 1_000_000_000)
        return str(base), str(base + 1)

    def _add_hpf_item(self, item_id, href, media):
        etree = self._etree
        if self._hpf_root is None:
            raise ValueError("no Contents/content.hpf — cannot register an image")
        manifest = self._hpf_root.find(_q(OPF_NS, "manifest"))
        item = etree.SubElement(manifest, _q(OPF_NS, "item"))
        item.set("id", item_id)
        item.set("href", href)
        item.set("media-type", media)
        item.set("isEmbeded", "1")          # Hancom's spelling — required
        self._modified.add(self._hpf_ei)

    def _build_pic(self, run, item_id, nw, nh, dw, dh):
        etree = self._etree
        pic_id, inst_id = self._next_pic_ids()
        scax = dw / nw if nw else 1.0
        scay = dh / nh if nh else 1.0

        def S(parent, ns, tag, **attrs):
            return etree.SubElement(parent, _q(ns, tag),
                                    {k: str(v) for k, v in attrs.items()})

        pic = S(run, HP_NS, "pic", id=pic_id, zOrder="0", numberingType="PICTURE",
                textWrap="TOP_AND_BOTTOM", textFlow="BOTH_SIDES", lock="0",
                dropcapstyle="None", href="", groupLevel="0", instid=inst_id, reverse="0")
        S(pic, HP_NS, "offset", x="0", y="0")
        S(pic, HP_NS, "orgSz", width=nw, height=nh)
        S(pic, HP_NS, "curSz", width=dw, height=dh)
        S(pic, HP_NS, "flip", horizontal="0", vertical="0")
        S(pic, HP_NS, "rotationInfo", angle="0", centerX=dw // 2, centerY=dh // 2,
          rotateimage="1")
        ri = S(pic, HP_NS, "renderingInfo")
        S(ri, HC_NS, "transMatrix", e1="1", e2="0", e3="0", e4="0", e5="1", e6="0")
        S(ri, HC_NS, "scaMatrix", e1="%.6f" % scax, e2="0", e3="0", e4="0",
          e5="%.6f" % scay, e6="0")
        S(ri, HC_NS, "rotMatrix", e1="1", e2="0", e3="0", e4="0", e5="1", e6="0")
        S(pic, HC_NS, "img", binaryItemIDRef=item_id, bright="0", contrast="0",
          effect="REAL_PIC", alpha="0")
        rect = S(pic, HP_NS, "imgRect")
        S(rect, HC_NS, "pt0", x="0", y="0")
        S(rect, HC_NS, "pt1", x=nw, y="0")
        S(rect, HC_NS, "pt2", x=nw, y=nh)
        S(rect, HC_NS, "pt3", x="0", y=nh)
        S(pic, HP_NS, "imgClip", left="0", right=nw, top="0", bottom=nh)
        S(pic, HP_NS, "inMargin", left="0", right="0", top="0", bottom="0")
        S(pic, HP_NS, "imgDim", dimwidth=nw, dimheight=nh)
        S(pic, HP_NS, "effects")
        S(pic, HP_NS, "sz", width=dw, widthRelTo="ABSOLUTE", height=dh,
          heightRelTo="ABSOLUTE", protect="0")
        S(pic, HP_NS, "pos", treatAsChar="1", affectLSpacing="0", flowWithText="1",
          allowOverlap="0", holdAnchorAndSO="0", vertRelTo="PARA", horzRelTo="PARA",
          vertAlign="TOP", horzAlign="CENTER", vertOffset="0", horzOffset="0")
        S(pic, HP_NS, "outMargin", left="0", right="0", top="0", bottom="0")

    def place_image(self, paragraph_index: int, image_path: str,
                    width_mm: float = None) -> str:
        """Embed `image_path` and anchor it (inline, treat-as-char) at the end
        of paragraph `paragraph_index`. `width_mm` sets the displayed width
        (height follows aspect); native size if omitted. Returns the image id.

        Needs Pillow (`pip install hwpkit[image]`)."""
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover
            raise ImportError("image insertion needs Pillow — `pip install hwpkit[image]`")
        px_w, px_h = Image.open(image_path).size
        ext = image_path.rsplit(".", 1)[-1].lower()
        nw, nh = px_w * PX_TO_HWPUNIT, px_h * PX_TO_HWPUNIT
        if width_mm:
            dw = round(width_mm * HWPUNIT_PER_MM)
            dh = round(dw * px_h / px_w)
        else:
            dw, dh = nw, nh

        item_id = self._next_image_id()
        href = "BinData/%s.%s" % (item_id, ext)
        self._add_hpf_item(item_id, href, _MEDIA_TYPE.get(ext, "image/" + ext))

        # add the image bytes as a new ZIP entry
        zi = zipfile.ZipInfo(href)
        zi.compress_type = zipfile.ZIP_DEFLATED
        with open(image_path, "rb") as f:
            self._entries.append((zi, f.read()))

        # anchor a <hp:pic> inside a new run in the target paragraph
        spos, p = self._paras[paragraph_index]
        existing = p.findall("{%s}run" % HP_NS)
        char_id = existing[0].get("charPrIDRef") if existing else "0"
        run = self._etree.SubElement(p, "{%s}run" % HP_NS)
        if char_id is not None:
            run.set("charPrIDRef", char_id)
        self._build_pic(run, item_id, nw, nh, dw, dh)
        self._modified.add(self._sections[spos][0])
        return item_id

    # -- output ------------------------------------------------------------ #
    def save(self, out_path: str):
        """Write the (possibly edited) document. Unmodified parts are copied
        byte-for-byte; only changed XML parts (sections / content.hpf) are
        re-serialized; newly added parts (BinData images) are appended. The
        mimetype entry keeps its original (stored) compression and position."""
        etree = self._etree
        serialized = {}
        for ei, root in self._trees.items():
            if ei in self._modified:
                serialized[ei] = etree.tostring(
                    root, xml_declaration=True, encoding="UTF-8", standalone=True)
        with zipfile.ZipFile(out_path, "w") as zf:
            for ei, (info, data) in enumerate(self._entries):
                payload = serialized.get(ei, data)
                # reuse the original ZipInfo so compress_type / mimetype-stored
                # / timestamps are preserved
                zf.writestr(info, payload)


def fill_hwpx(input_path: str, output_path: str, edit_fn):
    """Open `input_path`, hand the HwpxFile to `edit_fn` to mutate, then save
    to `output_path` — the HWPX analogue of `hwpkit.fill_hwp`.

        def edit(doc):
            doc.replace_text(12, "홍길동")
        fill_hwpx("form.hwpx", "out.hwpx", edit)
    """
    doc = HwpxFile.open(input_path)
    edit_fn(doc)
    doc.save(output_path)


def is_hwpx(path: str) -> bool:
    """True if `path` looks like a .hwpx (ZIP with an `application/hwp+zip`
    mimetype part), regardless of extension."""
    try:
        with zipfile.ZipFile(path) as zf:
            try:
                return zf.read("mimetype").strip() == b"application/hwp+zip"
            except KeyError:
                # some writers omit mimetype; fall back to the section layout
                return bool(_section_names(zf))
    except (zipfile.BadZipFile, OSError):
        return False
