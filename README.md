# hwpedit

Edit HWP 5.0 (Hancom Office) files in Python. Inject text into empty
paragraphs, swap substrings inside a cell, replace whole paragraphs —
and have Hancom open the file without "corrupted" errors.

HWP 5.0 is a Microsoft Compound File Binary (MS-CFB) container holding
a `DocInfo` stream and one or more `Section` streams (raw deflate). The
standard `olefile` library can only rewrite a stream if it stays the
same byte length, which is rarely true when you're inserting Korean
text. `hwpedit` rewrites the whole CFB container while preserving the
directory tree topology Hancom validates on open.

## Install

```bash
pip install hwpedit
```

(or, until published: `pip install git+https://github.com/psychofict/hwpedit`)

## Quickstart

```python
from hwpedit import fill_hwp, inject_text, swap_in_para_text, replace_text

def edit(records):
    inject_text(records, 24, "홍길동")                      # fill empty cell
    swap_in_para_text(records, 40, "□ 석사", "☑ 석사")      # tick checkbox
    replace_text(records, 75, "2026. 05. 19.")            # rewrite a cell

fill_hwp("template.hwp", "out.hwp", edit)
```

## Finding paragraph indices

```bash
hwpedit-inspect template.hwp
```

Prints one line per record with a text preview, so you can identify
which paragraph index is which form cell.

## Three operations

| Function | When to use | What it does |
|---|---|---|
| `inject_text(records, i, text)` | The paragraph is empty (cell on a blank template) | Adds a PARA_TEXT record, updates the char count, and dummies the cached layout |
| `swap_in_para_text(records, i, old, new)` | Same-length substring swap (checkboxes □ → ☑, single-char rewrites) | Pure byte replace; keeps the cached layout intact |
| `replace_text(records, i, text)` | Paragraph has existing text you want to overwrite entirely | Rewrites PARA_TEXT, updates char count, dummies layout if length changed |

## What's tricky about HWP

See [docs/GOTCHAS.md](docs/GOTCHAS.md). The short version:

- **`PARA_LINE_SEG` cache** — when a paragraph grows, the cached layout
  record must be replaced with 36 zero bytes. Anything else (keep,
  delete, fake multi-segment) either trips Hancom's corruption check
  or makes text render on a single smashed line.
- **CharShape has seven font slots** — Hangul / Latin / Hanja / Japanese
  / Symbol / User / Other. Hancom's font dropdown typically only
  changes the Hangul slot, so mixed-script paragraphs need explicit
  per-slot control via [`hwpedit.charshape`](hwpedit/charshape.py).
- **`replace_text("")` corrupts the file** — wiping a paragraph to
  empty produces a `(chars=1, PARA_TEXT="\r")` state that opens fine
  alone but fails Hancom's checks when combined with other edits. Use
  a space or em-dash placeholder.
- **Naive CFB writers fail RB-tree validation** — Hancom validates the
  red-black-tree directory invariants on open. `hwpedit.cfb` reads the
  original tree pointers byte-for-byte and reuses them.

## Comparison

| | `pyhwp` | `olefile` | `hwpedit` |
|---|---|---|---|
| Convert HWP → XML / text | ✅ | ❌ | ❌ |
| Read raw streams | ✅ | ✅ | ✅ |
| Rewrite same-size stream | ❌ | ✅ | ✅ |
| **Rewrite stream that grew/shrank** | ❌ | ❌ | ✅ |
| Hancom accepts the output | n/a | only if same-size | ✅ |

## See also

- [pyhwp](https://github.com/mete0r/pyhwp) — comprehensive HWP→XML
  converter. `hwpedit` learned the record format and the dummy-LineSeg
  trick from reading its source.
- [olefile](https://github.com/decalage2/olefile) — read-side dependency.
- The HWP 5.0 spec from Hancom (Korean).

## License

MIT — see [LICENSE](LICENSE).
