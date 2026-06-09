"""Object-oriented editor for binary HWP 5.0 — the `.hwp` twin of
`hwpkit.hwpx.HwpxFile`.

It gives `.hwp` the same interface as `.hwpx` (`open` / `paragraphs` /
`describe` / `paragraph_text` / `inject_text` / `replace_text` /
`swap_in_para_text` / `place_image` / `save`), so one calling pattern works
across both Hancom formats — see `open_document`.

    from hwpkit import open_document
    doc = open_document("form.hwp")     # or "form.hwpx" — same methods
    doc.replace_text(12, "홍길동")
    doc.place_image(42, "seal.png", width_mm=30)
    doc.save("out.hwp")

The functional helpers (`fill_hwp`, the `records`-list editors, and the
file-to-file `place_image`) remain for backward compatibility; this class
is a thin, stateful convenience layer over them.
"""

from __future__ import annotations

from typing import Optional

from . import cfb
from . import records as R
from . import picture as _pic
from .pipeline import docinfo_sid, file_header_compressed


class HwpFile:
    """Load a binary `.hwp`, edit it in memory, and save a new file.

    Paragraphs are indexed in document order across every `BodyText/Section*`
    stream, matching `HwpxFile`'s convention.
    """

    def __init__(self, path: str):
        self.entries = cfb.load(path)
        self.compressed = file_header_compressed(self.entries)

        sections = []
        for sid, de in self.entries.items():
            if de.etype == 2 and de.data and de.name.startswith("Section"):
                try:
                    idx = int(de.name[len("Section"):])
                except ValueError:
                    continue
                sections.append((idx, sid))
        sections.sort()

        self._sections = []          # [(sid, records)]
        for _idx, sid in sections:
            raw = self.entries[sid].data
            recs = R.parse(R.decompress(raw) if self.compressed else raw)
            self._sections.append((sid, recs))

        self._di_sid = docinfo_sid(self.entries)
        self._docinfo = None         # parsed lazily on first image insert
        self._dirty_sections = set()
        self._docinfo_dirty = False

        # global paragraph index -> (section_pos, local_ordinal)
        self._paras = []
        for spos, (_sid, recs) in enumerate(self._sections):
            for local in range(len(R.index_paragraphs(recs))):
                self._paras.append((spos, local))

    @classmethod
    def open(cls, path: str) -> "HwpFile":
        return cls(path)

    def __len__(self):
        return len(self._paras)

    # -- inspection -------------------------------------------------------- #
    def _locate(self, index):
        spos, local = self._paras[index]
        return spos, local, self._sections[spos][1]

    def paragraph_text(self, index: int) -> str:
        spos, local, recs = self._locate(index)
        pr = R.index_paragraphs(recs)[local]
        pt = R._para_text_after(recs, pr)
        return R._extract_para_text(recs[pt]["body"]) if pt is not None else ""

    def paragraphs(self):
        for i in range(len(self._paras)):
            yield i, self.paragraph_text(i)

    def describe(self) -> str:
        return "\n".join(f"P{i:3d}: {t[:70]!r}" for i, t in self.paragraphs())

    # -- text edits (delegate to the records-level functions) -------------- #
    def inject_text(self, index: int, text: str):
        spos, local, recs = self._locate(index)
        R.inject_text(recs, local, text)
        self._dirty_sections.add(spos)

    def replace_text(self, index: int, text: str):
        spos, local, recs = self._locate(index)
        R.replace_text(recs, local, text)
        self._dirty_sections.add(spos)

    def swap_in_para_text(self, index: int, old: str, new: str):
        spos, local, recs = self._locate(index)
        R.swap_in_para_text(recs, local, old, new)
        self._dirty_sections.add(spos)

    # -- image insertion --------------------------------------------------- #
    def place_image(self, index: int, image_path: str,
                    width_mm: Optional[float] = None) -> int:
        """Embed `image_path` and anchor it in paragraph `index`. `width_mm`
        sets the displayed width (height follows aspect); native size if
        omitted. Returns the new bin id. Needs Pillow (`hwpkit[image]`)."""
        try:
            from PIL import Image
        except ImportError:  # pragma: no cover
            raise ImportError("image insertion needs Pillow — `pip install hwpkit[image]`")
        px_w, px_h = Image.open(image_path).size
        ext = image_path.rsplit(".", 1)[-1].lower()
        nw, nh = px_w * _pic.PX_TO_HWPUNIT, px_h * _pic.PX_TO_HWPUNIT
        if width_mm:
            dw = _pic.mm_to_hwpunit(width_mm)
            dh = round(dw * px_h / px_w)
        else:
            dw, dh = nw, nh

        if self._docinfo is None:
            raw = self.entries[self._di_sid].data
            self._docinfo = R.parse(R.decompress(raw) if self.compressed else raw)
        bin_id = _pic.register_bindata(self._docinfo, ext)
        self._docinfo_dirty = True

        with open(image_path, "rb") as f:
            raw_img = f.read()
        data = R.compress(raw_img) if self.compressed else raw_img
        store = cfb.add_storage(self.entries, "BinData")
        cfb.add_stream(self.entries, "BIN%04d.%s" % (bin_id, ext), data, parent_sid=store)

        spos, local, recs = self._locate(index)
        para_level = recs[R.index_paragraphs(recs)[local]]["level"]
        pic_recs = _pic.build_picture_records(bin_id, nw, nh, dw, dh, para_level)
        _pic.anchor_picture(recs, local, pic_recs)
        self._dirty_sections.add(spos)
        return bin_id

    # -- output ------------------------------------------------------------ #
    def save(self, out_path: str):
        """Write a new `.hwp`. Only edited sections (and DocInfo, if an image
        was added) are re-serialized; the rest of the container is rebuilt
        from the original entries with the directory tree preserved."""
        for spos in self._dirty_sections:
            sid, recs = self._sections[spos]
            raw = R.serialize(recs)
            self.entries[sid].data = R.compress(raw) if self.compressed else raw
        if self._docinfo_dirty and self._docinfo is not None:
            raw = R.serialize(self._docinfo)
            self.entries[self._di_sid].data = R.compress(raw) if self.compressed else raw
        cfb.dump(self.entries, out_path)


def open_document(path: str):
    """Open a `.hwp` or `.hwpx` and return a uniform editor — `HwpFile` or
    `HwpxFile`, detected by container content (not extension). Both expose the
    same methods, so downstream code doesn't care which format it got."""
    from .hwpx import is_hwpx
    if is_hwpx(path):
        from .hwpx import HwpxFile
        return HwpxFile.open(path)
    return HwpFile.open(path)
