<p align="center">
  <img src="https://raw.githubusercontent.com/psychofict/hwpkit/main/assets/logo.jpeg" alt="hwpkit — open-source HWP editor in Python" width="320">
</p>

<p align="center">
  <a href="https://pypi.org/project/hwpkit/"><img src="https://img.shields.io/pypi/v/hwpkit.svg" alt="PyPI"></a>
  <a href="https://github.com/psychofict/hwpkit/actions/workflows/ci.yml"><img src="https://github.com/psychofict/hwpkit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
</p>

> **Read, fill, and edit Korean HWP / HWPX (Hancom Office) documents in Python.**
> Extract text for LLM / RAG pipelines, fill government & university forms
> (text *and* seal / signature images), and rewrite the binary without
> corrupting it — one API across both `.hwp` and `.hwpx`.

Korean government, universities, and most Korean enterprises run on
`.hwp` — the binary format Hancom Office uses. If you need to ingest
Korean enterprise documents into an LLM, automate form filling at
scale, or just edit an HWP file without manually clicking through
Hancom, `hwpkit` is the missing piece.

Under the hood, HWP 5.0 is a Microsoft Compound File Binary (MS-CFB)
container holding a `DocInfo` stream and one or more `Section` streams
(raw deflate). The standard `olefile` library can only rewrite a
stream if it stays the same byte length, which is rarely true when
you're inserting Korean text. `hwpkit` rewrites the whole CFB
container while preserving the directory tree topology Hancom
validates on open.

**Scope:** both Hancom formats are supported — the binary `.hwp` (the
format Office has shipped since 2010) and the XML-based `.hwpx`. Across
both you can extract text, edit text (inject / replace / swap), and
insert images, through the same API; the binary side additionally
rewrites the container without corrupting it. `.hwp` and `.hwpx` are two
serializations of one document model
([docs/OBJECT_MODEL.md](docs/OBJECT_MODEL.md)).

## Install

Python 3.9 or newer.

```bash
pip install hwpkit            # binary .hwp read + edit (core)
pip install hwpkit[hwpx]      # + .hwpx text extraction (lxml)
pip install hwpkit[image]     # + image insertion (Pillow)
pip install hwpkit[full]      # everything
```

## Quickstart

```python
from hwpkit import fill_hwp, inject_text, swap_in_para_text, replace_text

def edit(records):
    inject_text(records, 24, "홍길동")                      # fill empty cell
    swap_in_para_text(records, 40, "□ 석사", "☑ 석사")      # tick checkbox
    replace_text(records, 75, "2026. 05. 19.")            # rewrite a cell

fill_hwp("template.hwp", "out.hwp", edit)
```

## Finding paragraph indices

```bash
hwpkit-inspect template.hwp
```

Prints one line per record with a text preview, so you can identify
which paragraph index is which form cell.

## Extracting plain text

```bash
hwpkit-text file.hwp
```

Walks every section, strips inline controls (tables, images, footnote
refs, etc.) and prints just the literal character content. From Python:

```python
from hwpkit import extract_text_from_hwp
print(extract_text_from_hwp("file.hwp"))
```

### Both formats, one call

`.hwpx` (the XML format) extracts too — and `extract_text_from_file`
auto-detects which container it's looking at (by content, not just the
extension), so a mixed corpus of `.hwp` and `.hwpx` needs no branching:

```python
from hwpkit import extract_text_from_file   # .hwp or .hwpx
print(extract_text_from_file("doc.hwpx"))

from hwpkit import extract_text_from_hwpx    # .hwpx only (needs lxml)
```

The CLI dispatches the same way: `hwpkit-text file.hwp` or
`hwpkit-text file.hwpx`. HWPX text includes table-cell content (one line
per paragraph, document order).

For semantic HWP → XML (OWPML) conversion, use
[pyhwp](https://github.com/mete0r/pyhwp) — that's a much bigger job.

## Editing `.hwpx`

`.hwpx` files edit through `HwpxFile`, mirroring the binary edit verbs —
so the same calling pattern works on both formats. There's no layout
cache to manage; Hancom recomputes from the XML.

```python
from hwpkit import HwpxFile

doc = HwpxFile.open("form.hwpx")
print(doc.describe())                       # find paragraph indices
doc.inject_text(1, "홍길동")                 # fill an empty paragraph
doc.replace_text(12, "2026. 05. 19.")        # overwrite a cell
doc.swap_in_para_text(8, "□ 동의", "☑ 동의")  # tick a checkbox
doc.save("out.hwpx")
```

Or the one-call form, matching `fill_hwp`:

```python
from hwpkit import fill_hwpx
fill_hwpx("form.hwpx", "out.hwpx", lambda d: d.replace_text(12, "홍길동"))
```

Paragraphs are indexed in document order across all sections (table-cell
paragraphs included), the same convention as the binary side. Needs
`lxml` (`pip install hwpkit[hwpx]`).

Images insert into `.hwpx` too — `place_image` adds the `BinData/` part,
registers it in `content.hpf` (`isEmbeded="1"`), and anchors an inline
`<hp:pic>` in the target paragraph (extents = pixels × 75):

```python
doc = HwpxFile.open("form.hwpx")
doc.place_image(42, "seal.png", width_mm=25)   # 25 mm wide, aspect preserved
doc.save("out.hwpx")
```

Needs Pillow (`pip install hwpkit[image]`).

## For LLM / RAG pipelines

Korean enterprises ship contracts, policies, regulations, government
notices, internal memos, and academic papers as `.hwp`. If your
retrieval / RAG pipeline can't read HWP, it can't index Korean
enterprise data. The standard text-extraction stack (`pdfplumber`,
`python-docx`, `unstructured`) doesn't cover HWP — they all need a
preprocessing step.

`hwpkit` is that step. The library has no LLM dependencies; it's just
a clean Korean-text source you can plug into anything:

```python
# Index every HWP in a directory tree as documents for a vector DB
import glob
from hwpkit import extract_text_from_hwp

for path in glob.glob("corpus/**/*.hwp", recursive=True):
    text = extract_text_from_hwp(path)
    vector_db.add(doc_id=path, content=text)
```

```bash
# One-shot: pipe an HWP into any LLM CLI
hwpkit-text contract.hwp | llm "Summarize the key obligations in Korean"

# Bulk: convert a folder of HWPs to .txt for downstream tooling
for f in *.hwp; do hwpkit-text "$f" > "${f%.hwp}.txt"; done
```

The extractor walks every `Section*` stream, decodes UTF-16LE, and
strips inline controls (tables, images, footnote refs, autonumbers,
page-number ctrls, bookmarks) so what you get is clean text — usable
directly as input to chunkers, embeddings, or any LLM context.

## Edit operations

| Function | When to use | What it does |
|---|---|---|
| `inject_text(records, i, text)` | The paragraph is empty (cell on a blank template) | Adds a PARA_TEXT record, updates the char count, and dummies the cached layout |
| `swap_in_para_text(records, i, old, new)` | Same-length substring swap (checkboxes □ → ☑, single-char rewrites) | Pure byte replace; keeps the cached layout intact |
| `replace_text(records, i, text)` | Paragraph has existing text you want to overwrite entirely | Rewrites PARA_TEXT, updates char count, dummies layout if length changed |
| `charshape.flatten_to_face(rec, face_id)` | Mixed-script paragraph (Korean + English) won't pick up font changes | Sets all 7 per-script CharShape slots to the same face — see [GOTCHAS §3](docs/GOTCHAS.md#3-why-does-my-english-text-refuse-to-change-font-in-hancom) |
| `place_image(in, out, img, paragraph_index, width_mm=…)` | Stamp a seal / signature / stamp image into a form | Adds the image stream to the CFB, registers it in DocInfo, and anchors a picture object in the target paragraph — see below |

## Inserting an image (seal / signature / stamp)

Form filling often needs a 도장/직인/서명 image, not just text. `place_image`
embeds a PNG/JPG and anchors it in a paragraph:

```python
from hwpkit import place_image

place_image("form.hwp", "out.hwp", "seal.png",
            paragraph_index=42, width_mm=30)   # 30 mm wide, aspect preserved
```

Under the hood this does the three things a picture needs — add a
`BinData/BIN%04d.<ext>` stream to the container (via a red-black-tree
node insert), bump the DocInfo BinData count + add a `BIN_DATA` record,
and anchor a `gso` picture object in the paragraph. Image extents use
HWPUNIT (pixels × 75); see [GOTCHAS §5](docs/GOTCHAS.md#5-why-does-my-embedded-image-come-out-the-wrong-size)
and [RECORD_FORMAT.md](docs/RECORD_FORMAT.md#embedded-images).

## What's tricky about HWP

See [docs/GOTCHAS.md](docs/GOTCHAS.md). The short version:

- **`PARA_LINE_SEG` cache** — when a paragraph grows, the cached layout
  record must be replaced with 36 zero bytes. Anything else (keep,
  delete, fake multi-segment) either trips Hancom's corruption check
  or makes text render on a single smashed line.
- **CharShape has seven font slots** — Hangul / Latin / Hanja / Japanese
  / Symbol / User / Other. Hancom's font dropdown typically only
  changes the Hangul slot, so mixed-script paragraphs need explicit
  per-slot control via [`hwpkit.charshape`](hwpkit/charshape.py).
- **`replace_text("")` corrupts the file** — wiping a paragraph to
  empty produces a `(chars=1, PARA_TEXT="\r")` state that opens fine
  alone but fails Hancom's checks when combined with other edits. Use
  a space or em-dash placeholder.
- **Naive CFB writers fail RB-tree validation** — Hancom validates the
  red-black-tree directory invariants on open. `hwpkit.cfb` reads the
  original tree pointers byte-for-byte and reuses them.

## Comparison

| | `pyhwp` | `olefile` | `hwpkit` |
|---|---|---|---|
| Extract plain text (`.hwp`) | ✅ | ❌ | ✅ |
| **Extract plain text (`.hwpx`)** | ❌ | ❌ | ✅ |
| Convert HWP → XML / OWPML (semantic) | ✅ | ❌ | ❌ |
| Read raw streams | ✅ | ✅ | ✅ |
| Rewrite same-size stream | ❌ | ✅ | ✅ |
| **Rewrite stream that grew/shrank** | ❌ | ❌ | ✅ |
| **Insert an image (seal / signature)** | ❌ | ❌ | ✅ |
| Hancom accepts the output | n/a | only if same-size | ✅ |

## See also

- [docs/OBJECT_MODEL.md](docs/OBJECT_MODEL.md) — how the binary `.hwp`
  records map onto their HWPX (OWPML) twins. `.hwp` and `.hwpx` are two
  serializations of one document model, so `CharShape`/`BorderFill`/
  HWPUNIT knowledge transfers between them.
- [pyhwp](https://github.com/mete0r/pyhwp) — comprehensive HWP→XML
  converter. `hwpkit` learned the record format and the dummy-LineSeg
  trick from reading its source.
- [olefile](https://github.com/decalage2/olefile) — read-side dependency.
- The HWP 5.0 spec from Hancom (Korean).

## License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Made by <a href="https://ebenworks.ebstar.co/">Ebenworks</a>
</p>
