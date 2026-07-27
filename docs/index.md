# hwpkit

**The pure-Python toolkit for Korean HWP &amp; HWPX (Hancom Office) documents.**
Read it, edit it, extract its text — *no Hancom, no Windows, no COM automation.*

[Get started](quickstart.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/psychofict/hwpkit){ .md-button }
[PyPI](https://pypi.org/project/hwpkit/){ .md-button }

---

Korean government, universities, courts, and most Korean enterprises run on
**HWP** (한글, Hangul Word Processor) — the `.hwp` and `.hwpx` formats from
Hancom Office. The rest of the world's tooling (`python-docx`, `pdfplumber`,
`unstructured`, LibreOffice) **can't read them**, and the few that try need a
Windows box with Hancom installed driving it over COM.

**`hwpkit` is the missing piece.** Pure Python, cross-platform, zero external
apps — install it and start reading, editing, and extracting Korean documents
in three lines.

```bash
pip install hwpkit[full]
```

```python
from hwpkit import extract_text_from_file
print(extract_text_from_file("계약서.hwp"))      # …or .hwpx — auto-detected
```

That's it. No Hancom license. No Windows. No headless office server.

## Why hwpkit

<div class="grid cards" markdown>

-   📄 __Both formats, one API__

    Binary `.hwp` (HWP 5.0) *and* XML `.hwpx` (OWPML). `open_document()` hands
    you the same editor either way — you never branch on format.

-   🐍 __Pure Python, runs anywhere__

    Linux, macOS, Windows, containers, Lambda. No Hancom, no `pywin32`, no COM,
    no LibreOffice subprocess.

-   🤖 __Built for LLM / RAG__

    Clean Korean text out of any `.hwp`/`.hwpx`, ready to chunk and embed — the
    preprocessing step your retrieval pipeline was missing.

-   ✍️ __Edit without corrupting__

    Fill government & university forms, tick checkboxes, rewrite cells — and the
    binary container is rebuilt while preserving the directory tree Hancom
    validates on open.

-   🖋️ __Insert seals & signatures__

    Stamp a 도장/직인/서명 image into a form cell — into both `.hwp` and `.hwpx`.

-   ⚖️ __MIT licensed, tiny core__

    Base install is just `olefile`; `lxml` and `Pillow` are optional extras,
    loaded lazily only when you use `.hwpx` or images.

</div>

## One API, both formats

```python
from hwpkit import open_document

doc = open_document("template.hwp")            # or "template.hwpx" — auto-detected
print(doc.describe())                           # list paragraphs to find field indices
doc.inject_text(24, "홍길동")                    # fill an empty cell
doc.swap_in_para_text(40, "□ 석사", "☑ 석사")    # tick a checkbox
doc.replace_text(75, "2026. 05. 19.")           # overwrite a cell
doc.place_image(42, "seal.png", width_mm=30)    # stamp a 도장 / signature
doc.save("out.hwp")
```

`open_document` returns an [`HwpFile`](api.md#hwpkit.hwp.HwpFile) or
[`HwpxFile`](api.md#hwpkit.hwpx.HwpxFile) depending on the file — both expose
the **same methods**.

## Who uses this

- **AI / RAG engineers** indexing Korean documents into vector DBs.
- **Gov-tech & RPA teams** auto-filling 관공서·대학 forms at scale.
- **Data engineers** migrating HWP archives to text / structured data.
- **Anyone** who needs to edit a `.hwp` without clicking through Hancom.

## Next steps

- [Quickstart](quickstart.md) — extract, edit, and stamp in a few lines.
- [hwpkit vs alternatives](comparison.md) — how it compares to `pyhwp`,
  `pyhwpx`, and `olefile`.
- [API reference](api.md) — every public function and class.
- [Internals](OBJECT_MODEL.md) — how `.hwp` and `.hwpx` map onto one model.

---

Made by [Ebenworks](https://ebenworks.co/) · MIT licensed.
