<p align="center">
  <img src="https://raw.githubusercontent.com/psychofict/hwpkit/main/assets/logo.jpeg" alt="hwpkit — open-source HWP editor in Python" width="320">
</p>

<p align="center">
  <a href="https://pypi.org/project/hwpkit/"><img src="https://img.shields.io/pypi/v/hwpkit.svg" alt="PyPI"></a>
  <a href="https://github.com/psychofict/hwpkit/actions/workflows/ci.yml"><img src="https://github.com/psychofict/hwpkit/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.9+-blue.svg" alt="Python 3.9+"></a>
  <a href="https://pypi.org/project/hwpkit/"><img src="https://img.shields.io/pypi/dm/hwpkit.svg" alt="PyPI downloads"></a>
</p>

> **Read, fill, and edit Korean HWP (Hancom Office) documents in Python.**
> Extract text for LLM / RAG pipelines, fill government & university
> forms programmatically, and rewrite the binary without corrupting it.

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

**Scope:** targets HWP 5.0 (the binary `.hwp` format Hancom Office has
shipped since 2010). The newer XML-based `.hwpx` format is not covered
— for `.hwpx` you can edit the inner OWPML XML directly with any zip
+ XML library.

## Install

Python 3.9 or newer.

```bash
pip install hwpkit
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

For semantic HWP → XML (OWPML) conversion, use
[pyhwp](https://github.com/mete0r/pyhwp) — that's a much bigger job.

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
| Extract plain text | ✅ | ❌ | ✅ |
| Convert HWP → XML / OWPML (semantic) | ✅ | ❌ | ❌ |
| Read raw streams | ✅ | ✅ | ✅ |
| Rewrite same-size stream | ❌ | ✅ | ✅ |
| **Rewrite stream that grew/shrank** | ❌ | ❌ | ✅ |
| Hancom accepts the output | n/a | only if same-size | ✅ |

## See also

- [pyhwp](https://github.com/mete0r/pyhwp) — comprehensive HWP→XML
  converter. `hwpkit` learned the record format and the dummy-LineSeg
  trick from reading its source.
- [olefile](https://github.com/decalage2/olefile) — read-side dependency.
- The HWP 5.0 spec from Hancom (Korean).

## License

MIT — see [LICENSE](LICENSE).
