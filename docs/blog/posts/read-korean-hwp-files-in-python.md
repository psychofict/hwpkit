---
date: 2026-06-09
authors: [ebenworks]
categories:
  - Tutorials
description: >-
  A practical guide to reading, extracting text from, and editing Korean HWP
  and HWPX (Hancom Office) files in Python — without Hancom or Windows.
---

# How to read and extract text from Korean HWP files in Python

If you've ever tried to open a Korean `.hwp` file in Python, you already know
the problem: `python-docx` doesn't touch it, `pdfplumber` is for PDFs, and
`unstructured` skips it. HWP — 한글, the Hangul Word Processor format from
Hancom Office — is the default document format across Korean government,
universities, courts, and enterprises, yet almost no portable tooling reads it.

This guide shows how to **read, extract text from, and edit both `.hwp` and
`.hwpx` files in pure Python** using [`hwpkit`](https://github.com/psychofict/hwpkit)
— no Hancom installation and no Windows required, so it runs on a Linux
server, in CI, or in a container.

<!-- more -->

## Install

```bash
pip install hwpkit[full]
```

The core install is just `olefile`; the `[full]` extra adds `lxml` (for
`.hwpx`) and `Pillow` (for image insertion).

## Extract text from a `.hwp` or `.hwpx` file

The most common need — turning a Korean document into plain text for search,
indexing, or an LLM:

```python
from hwpkit import extract_text_from_file

text = extract_text_from_file("계약서.hwp")     # works on .hwpx too
print(text)
```

`extract_text_from_file` auto-detects the format by inspecting the container
(not just the file extension), so a mixed folder of `.hwp` and `.hwpx` needs no
branching. Behind the scenes it walks every section, decodes the text, and
strips inline controls (tables, images, footnote markers, page-number fields,
bookmarks) — returning clean, one-line-per-paragraph text with table-cell
content included.

From the command line:

```bash
hwpkit-text contract.hwp
```

## Use it for a Korean RAG / LLM pipeline

This is exactly the preprocessing step most Korean retrieval pipelines are
missing. Index a whole archive into a vector database:

```python
import glob
from hwpkit import extract_text_from_file

for path in glob.glob("corpus/**/*.hwp*", recursive=True):   # .hwp and .hwpx
    text = extract_text_from_file(path)
    vector_db.add(doc_id=path, content=text)
```

`hwpkit` has no LLM dependencies — it's just a clean Korean-text source you can
feed into any chunker, embedding model, or context window.

## Edit a document: fill forms, tick checkboxes

Reading is only half of it. Korean offices live on `.hwp` *forms* —
application forms, 결격사유 checklists, score sheets. `hwpkit` edits them
without corrupting the file, using one object API for both formats:

```python
from hwpkit import open_document

doc = open_document("지원서.hwp")              # or "지원서.hwpx"
print(doc.describe())                          # list paragraphs to find fields
doc.inject_text(24, "홍길동")                   # fill an empty cell
doc.swap_in_para_text(40, "□ 동의", "☑ 동의")   # tick a checkbox
doc.replace_text(75, "2026. 05. 19.")          # overwrite a cell
doc.save("작성완료.hwp")
```

## Insert a seal or signature image

Forms often need a 도장/직인/서명 image, not just text:

```python
doc = open_document("계약서.hwp")
doc.place_image(42, "도장.png", width_mm=30)   # 30 mm wide, aspect preserved
doc.save("날인완료.hwp")
```

## Why not just automate Hancom?

The other way to script HWP is `pyhwpx`, which drives the Hancom Office app
over Windows COM. It's powerful — but it **requires Windows and a Hancom
installation**, so it can't run on a Linux server, in CI, or in a container.
`hwpkit` is pure Python and runs anywhere. (`pyhwp` is excellent for the binary
record format and HWP→XML conversion, but is read-oriented and doesn't handle
`.hwpx`.) There's a full
[comparison here](../../comparison.md).

## What makes editing `.hwp` hard

A binary `.hwp` is a Microsoft Compound File Binary (MS-CFB) container of
deflate-compressed record streams. The moment you insert Korean text, a stream
changes byte length — and a naive rewrite fails, because Hancom validates the
red-black-tree directory structure on open and re-renders text from a cached
per-paragraph layout you have to invalidate correctly. `hwpkit` handles both.
If you're going deeper, the [gotchas](../../GOTCHAS.md) and the
[object model](../../OBJECT_MODEL.md) writeups cover the traps.

## Wrapping up

If you need to read, extract, or edit Korean HWP/HWPX documents from Python —
for a RAG pipeline, a form-automation job, or a one-off migration — `hwpkit`
does it in pure Python on any platform.

```bash
pip install hwpkit[full]
```

- **GitHub:** [github.com/psychofict/hwpkit](https://github.com/psychofict/hwpkit)
- **Docs:** [hwpkit.ebenworks.co](https://hwpkit.ebenworks.co)

Questions or a format edge case `hwpkit` doesn't handle yet? Open an issue —
feedback shapes the roadmap.
