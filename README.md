<p align="center">
  <img src="https://raw.githubusercontent.com/psychofict/hwpkit/main/assets/logo.jpeg" alt="hwpkit — read, edit & extract Korean HWP / HWPX documents in pure Python" width="320">
</p>

<h1 align="center">hwpkit</h1>

<p align="center">
  <b>The pure-Python toolkit for Korean HWP &amp; HWPX (Hancom Office) documents.</b><br>
  Read it, edit it, extract its text — <i>no Hancom, no Windows, no COM automation.</i>
</p>

<p align="center">
  <a href="https://pypi.org/project/hwpkit/"><img src="https://img.shields.io/pypi/v/hwpkit.svg" alt="PyPI"></a>
  <a href="https://pypi.org/project/hwpkit/"><img src="https://img.shields.io/pypi/pyversions/hwpkit.svg" alt="Python versions"></a>
  <a href="https://github.com/psychofict/hwpkit/actions/workflows/ci.yml"><img src="https://github.com/psychofict/hwpkit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="https://hwpkit.ebstar.co/"><img src="https://img.shields.io/badge/docs-hwpkit.ebstar.co-1A6FC4.svg" alt="Documentation"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
</p>

<p align="center">
  📖 <b><a href="https://hwpkit.ebstar.co/">Documentation</a></b> ·
  <a href="https://pypi.org/project/hwpkit/">PyPI</a> ·
  <a href="CHANGELOG.md">Changelog</a>
</p>

---

Korean government, universities, courts, and most Korean enterprises run on
**HWP** (한글, Hangul Word Processor) — the `.hwp` and `.hwpx` formats from
Hancom Office. The rest of the world's tooling (`python-docx`, `pdfplumber`,
`unstructured`, LibreOffice) **can't read them**, and the few that try
need a Windows box with Hancom installed driving it over COM.

**`hwpkit` is the missing piece.** Pure Python, cross-platform, zero
external apps — install it and start reading, editing, and extracting
Korean documents in three lines.

```bash
pip install hwpkit[full]
```

```python
from hwpkit import extract_text_from_file
print(extract_text_from_file("계약서.hwp"))      # …or .hwpx — auto-detected
```

That's it. No Hancom license. No Windows. No headless office server.

## Why hwpkit

- 📄 **Both formats, one API.** Binary `.hwp` (HWP 5.0) *and* XML `.hwpx`
  (OWPML) — extract, edit, and insert images through the same calls.
  `open_document()` hands you the same object either way, so you learn it
  once and never branch on format.
- 🐍 **Pure Python, runs anywhere.** Linux, macOS, Windows, containers,
  Lambda. No Hancom, no `pywin32`, no COM, no LibreOffice subprocess.
- 🤖 **Built for LLM / RAG.** Clean Korean text out of any `.hwp`/`.hwpx`,
  ready to chunk and embed. The preprocessing step your retrieval pipeline
  was missing.
- ✍️ **Edit without corrupting.** Fill government & university forms, tick
  checkboxes, rewrite cells — and `hwpkit` rewrites the binary container
  while preserving the directory-tree structure Hancom validates on open.
  (This is the genuinely hard part. We solved it. See [the gotchas](docs/GOTCHAS.md).)
- 🖋️ **Insert seals & signatures.** Stamp a 도장/직인/서명 image into a form
  cell — into both `.hwp` and `.hwpx`.
- 🪶 **Tiny core.** The base install is just `olefile`; `lxml` and `Pillow`
  are optional extras, loaded lazily only when you use `.hwpx` or images.
- ⚖️ **MIT licensed.** Use it anywhere, commercially or not.

## Install

Python 3.9+.

```bash
pip install hwpkit            # core: binary .hwp read + edit
pip install hwpkit[hwpx]      # + .hwpx (OWPML) support  (adds lxml)
pip install hwpkit[image]     # + seal / signature insertion  (adds Pillow)
pip install hwpkit[full]      # everything
```

## Quickstart

**Extract text from any Korean document — for RAG, search, or an LLM:**

```python
from hwpkit import extract_text_from_file

text = extract_text_from_file("notice.hwpx")   # .hwp or .hwpx, auto-detected
```

```bash
# from the shell — works on both formats
hwpkit-text contract.hwp | llm "Summarize the key obligations in Korean"
```

**Fill a form, tick a checkbox, stamp a seal — one API, either format:**

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

`open_document` returns an `HwpFile` or `HwpxFile` depending on the file —
both expose the **same methods**, so your code never branches on format.

Prefer plain functions? The originals are still there:
`fill_hwp(...)`, `inject_text(records, i, text)`, and the file-to-file
`place_image("in.hwp", "out.hwp", "seal.png", paragraph_index=42)`.

**Find which paragraph is which field:**

```bash
hwpkit-inspect template.hwp        # one line per record, with a text preview
```

## Built for Korean RAG & LLM pipelines

Korean enterprises ship contracts, policies, regulations, government
notices, court filings, internal memos, and academic papers as `.hwp` /
`.hwpx`. If your retrieval pipeline can't read HWP, it simply can't index
Korean enterprise data — and the standard stack (`pdfplumber`,
`python-docx`, `unstructured`) doesn't cover it.

`hwpkit` is a clean, dependency-light text source you can plug into
anything — no LLM SDK required:

```python
import glob
from hwpkit import extract_text_from_file

for path in glob.glob("corpus/**/*.hwp*", recursive=True):   # .hwp and .hwpx
    vector_db.add(doc_id=path, content=extract_text_from_file(path))
```

Extraction strips inline controls (tables, images, footnote refs,
autonumbers, page-number controls, bookmarks) and returns clean,
one-line-per-paragraph text — table-cell content included — ready for
chunkers, embeddings, or any context window.

## Who uses this

- **AI / RAG engineers** indexing Korean documents into vector DBs.
- **Gov-tech & RPA teams** auto-filling 관공서·대학 forms at scale.
- **Data engineers** migrating HWP archives to text / structured data.
- **Anyone** who needs to edit a `.hwp` without clicking through Hancom.

## hwpkit vs the alternatives

|  | `pyhwp` | `pyhwpx` | `olefile` | **`hwpkit`** |
|---|:---:|:---:|:---:|:---:|
| Pure Python (no Hancom / no Windows) | ✅ | ❌ *(needs Hancom + COM)* | ✅ | ✅ |
| Extract text — `.hwp` | ✅ | ✅ | ❌ | ✅ |
| Extract text — `.hwpx` | ❌ | ✅ | ❌ | ✅ |
| Edit text without corrupting the file | ❌ | ✅ *(via Hancom)* | ❌ | ✅ |
| Rewrite a stream that grew / shrank | ❌ | n/a | ❌ | ✅ |
| Insert an image (seal / signature) | ❌ | ✅ *(via Hancom)* | ❌ | ✅ |
| One API across `.hwp` **and** `.hwpx` | ❌ | ✅ | ❌ | ✅ |
| Runs in CI / Linux / containers | ✅ | ❌ | ✅ | ✅ |

`hwpkit` is the only option that does **all** of it in portable, pure
Python — no Hancom, no Windows, no COM bridge.

## How it works (for the curious)

Under the hood, `.hwp` is a Microsoft Compound File Binary (MS-CFB)
container of deflate-compressed record streams; `.hwpx` is a ZIP of OWPML
XML. `olefile` can only rewrite a stream if its byte length is unchanged —
almost never true when you inject Korean text. `hwpkit` rewrites the whole
container while preserving the **red-black-tree directory topology** Hancom
validates on open, and patches the record-level layout caches so text
re-flows correctly.

- [docs/OBJECT_MODEL.md](docs/OBJECT_MODEL.md) — how `.hwp` records map onto
  their `.hwpx` (OWPML) twins; the shared HWPUNIT geometry.
- [docs/RECORD_FORMAT.md](docs/RECORD_FORMAT.md) — the binary record format.
- [docs/GOTCHAS.md](docs/GOTCHAS.md) — the traps that take a week to find
  the first time (layout cache, 7-slot CharShape, RB-tree validation, image
  sizing). Read this if Hancom is rejecting your output.

For semantic HWP → XML (OWPML) conversion, see
[pyhwp](https://github.com/mete0r/pyhwp).

## Contributing

Issues, ideas, and PRs welcome. If `hwpkit` saved you from a Windows VM and
a Hancom license, a ⭐ on [GitHub](https://github.com/psychofict/hwpkit)
helps others find it.

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Made by <a href="https://ebenworks.ebstar.co/">Ebenworks</a>
</p>
