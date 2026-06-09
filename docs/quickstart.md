# Quickstart

## Install

Python 3.9+.

```bash
pip install hwpkit            # core: binary .hwp read + edit
pip install hwpkit[hwpx]      # + .hwpx (OWPML) support  (adds lxml)
pip install hwpkit[image]     # + seal / signature insertion  (adds Pillow)
pip install hwpkit[full]      # everything
```

## Extract text — for RAG, search, or an LLM

```python
from hwpkit import extract_text_from_file

text = extract_text_from_file("notice.hwpx")   # .hwp or .hwpx, auto-detected
```

```bash
# from the shell — works on both formats
hwpkit-text contract.hwp | llm "Summarize the key obligations in Korean"
```

Extraction strips inline controls (tables, images, footnote refs, autonumbers,
page-number controls, bookmarks) and returns clean, one-line-per-paragraph text
— table-cell content included — ready for chunkers, embeddings, or any context
window.

## Edit a form — one API, either format

```python
from hwpkit import open_document

doc = open_document("template.hwp")            # or "template.hwpx" — auto-detected
print(doc.describe())                           # list paragraphs to find field indices
doc.inject_text(24, "홍길동")                    # fill an empty cell
doc.swap_in_para_text(40, "□ 석사", "☑ 석사")    # tick a checkbox
doc.replace_text(75, "2026. 05. 19.")           # overwrite a cell
doc.save("out.hwp")
```

!!! tip "Finding the right paragraph index"
    `doc.describe()` prints one line per paragraph with a text preview, so you
    can spot which index maps to which form field. For binary `.hwp` you can
    also run `hwpkit-inspect template.hwp` from the shell.

### Edit verbs

| Method | Use when | What it does |
|---|---|---|
| `inject_text(i, text)` | the paragraph is empty (a blank form cell) | fills it with text |
| `replace_text(i, text)` | the paragraph has text you want to overwrite | rewrites the whole paragraph |
| `swap_in_para_text(i, old, new)` | a substring swap (checkboxes `□ → ☑`) | replaces the first occurrence |

## Stamp a seal / signature

```python
doc = open_document("form.hwp")        # or .hwpx
doc.place_image(42, "seal.png", width_mm=30)   # 30 mm wide, aspect preserved
doc.save("out.hwp")
```

`width_mm` sets the displayed width; omit it to use the image's native pixel
size. Works for `.hwp` and `.hwpx` alike.

## Prefer plain functions?

The object API is a convenience layer — the original functional helpers are
still fully supported:

```python
from hwpkit import fill_hwp, inject_text, swap_in_para_text, replace_text, place_image

def edit(records):
    inject_text(records, 24, "홍길동")
    swap_in_para_text(records, 40, "□ 석사", "☑ 석사")
    replace_text(records, 75, "2026. 05. 19.")

fill_hwp("template.hwp", "out.hwp", edit)
place_image("form.hwp", "out.hwp", "seal.png", paragraph_index=42, width_mm=30)
```

```python
from hwpkit import fill_hwpx
fill_hwpx("template.hwpx", "out.hwpx", lambda d: d.replace_text(12, "홍길동"))
```

## Index a whole corpus (RAG)

```python
import glob
from hwpkit import extract_text_from_file

for path in glob.glob("corpus/**/*.hwp*", recursive=True):   # .hwp and .hwpx
    vector_db.add(doc_id=path, content=extract_text_from_file(path))
```

See the [API reference](api.md) for everything, or the
[internals](OBJECT_MODEL.md) for how it works.
