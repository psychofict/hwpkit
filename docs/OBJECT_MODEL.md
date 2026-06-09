# One model, two serializations: HWP 5.0 ↔ HWPX

`.hwp` (binary) and `.hwpx` (XML) are **not two formats** so much as two
*serializations of the same document object model* (Hancom calls it
OWPML). The binary format writes the model as tagged records inside an
MS-CFB container; HWPX writes the same model as OWPML XML inside a ZIP.

This matters for `hwpkit` because **knowledge transfers even where code
doesn't.** If you understand the binary `CharShape` record, you already
understand the HWPX `<hh:charPr>` element — they carry the same fields.
Anything you learn fixing one side is a head start on the other.

This doc is the Rosetta Stone. `hwpkit` ships binary editing today;
HWPX support (planned) will reuse this mapping rather than relearn it.

## The shared unit: HWPUNIT = 1/7200 inch

Both serializations measure geometry in **HWPUNIT = 1/7200 inch**
(see [RECORD_FORMAT.md](RECORD_FORMAT.md) — `PARA_LINE_SEG` is in
HWPUNIT; HWPX `<hp:sz>`/`<hp:curSz>`/`<hp:orgSz>` are too, with
`widthRelTo="ABSOLUTE"`).

That gives one constant that shows up in *both* formats when you embed an
image and need its native size in document units:

```
1 px @ 96 dpi  =  7200 / 96  =  75 HWPUNIT
native_extent  =  pixels × 75
```

So an HWPX `<hp:orgSz>` (and the binary picture's original extent) is the
PNG's `(width_px × 75, height_px × 75)`; the *displayed* size is reached
by a scale matrix / current-size field. The "magic ×75" you see in
image-embedding code is just "assume the bitmap is 96 px/inch." Same
number, both formats.

> Provenance: this constant was first nailed down on the HWPX side (an
> external WeasyPrint/python-hwpx proposal builder uses `F = 75` for
> `<hp:orgSz>`). It is `7200/96`, so it applies verbatim to binary
> `SHAPE_COMPONENT_PICTURE` extents.

## Record ↔ element map

DocInfo / BodyText **records** (binary) vs OWPML **elements** (HWPX). Tag
numbers are the binary DocInfo/BodyText record tags; element names use
the HWPX namespaces `hh:` (head), `hp:` (paragraph), `hc:` (core).

| Concept | Binary record (tag) | HWPX element | Notes |
|---|---|---|---|
| Font face | `FACE_NAME` (`0x13`) | `<hh:font>` in `<hh:fontface>` | One registration per face; referenced by id. |
| **Char formatting** | `CHAR_SHAPE` (`0x15`) | `<hh:charPr>` (+ 7-lang `<hh:fontRef>`) | **7 per-script font slots in both** — see [GOTCHAS §3](GOTCHAS.md#3-why-does-my-english-text-refuse-to-change-font-in-hancom). The single most important shared insight. |
| Para formatting | `PARA_SHAPE` (`0x19`) | `<hh:paraPr>` | align, indent, spacing, border ref, page-break-before. |
| Border + fill | `BORDER_FILL` (`0x14`) | `<hh:borderFill>` + `<hc:fillBrush>`/`<hc:winBrush>` | per-side border type/width/color + solid fill. Tables, callout boxes, header bands. |
| Paragraph | `PARA_HEADER` (`0x42`) | `<hp:p>` | first 4 bytes = char count (high bit = control-para flag). |
| Text run | `PARA_TEXT` (`0x43`) | `<hp:run>`/`<hp:t>` | UTF-16LE; inline controls share the run. `\r` terminates a paragraph. |
| Run→shape binding | `PARA_CHAR_SHAPE` (`0x44`) | `charPrIDRef` on `<hp:run>` | `(start_pos, shape_id)` pairs ↔ per-run id reference. |
| **Layout cache** | `PARA_LINE_SEG` (`0x45`) | `<hp:linesegarray>`/`<hp:lineseg>` | Cached line metrics in *both*. Binary: zero it to force recompute ([GOTCHAS §2](GOTCHAS.md#2-why-does-my-injected-text-render-as-a-smashed-single-line)). HWPX: builders usually omit it and let Hancom recompute. |
| Table | `TABLE` (`0x4D`) under `CTRL_HEADER` (`0x47`) | `<hp:tbl>`/`<hp:tr>`/`<hp:tc>` | cell border/fill via the border-fill id. |
| Embedded binary | `BIN_DATA` (`0x12`) + a `BinData/BIN%04X` CFB stream | `BinData/` ZIP part + manifest `<opf:item>` | the bytes of the image live here; everything else just references the id. |
| **Picture** | `SHAPE_COMPONENT_PICTURE` (`0x55`) under a GSO `CTRL_HEADER` (`0x47`), inline-control char `0x0B` in `PARA_TEXT` | `<hp:pic>` (+ `<hc:img binaryItemIDRef>`, `<hp:orgSz>`/`<hp:curSz>`/`<hp:imgClip>`) | sizing = px × 75 (above). This is direction A's synthesis target. |

## Embedding an image: same three moves in both formats

Whether binary or HWPX, inserting a picture is the same three logical
steps — only the encoding differs:

1. **Store the bytes.**
   - Binary: add a `BinData/BIN%04X` stream to the CFB container *and* a
     `BIN_DATA` record (`0x12`) in DocInfo that points at it. (Adding a
     CFB stream needs a red-black-tree node insert — see
     [GOTCHAS §1](GOTCHAS.md#1-why-does-my-edited-hwp-open-as-corrupted);
     `cfb.dump` already re-lays the container, so only the tree splice is new.)
   - HWPX: add a file under `BinData/` in the ZIP *and* a manifest
     `<opf:item>` with `isEmbeded="1"`; the picture's `<hc:img>` uses
     `binaryItemIDRef` = that manifest item id (not the header bin-item id).
2. **Declare the picture object.**
   - Binary: a GSO `CTRL_HEADER` (`0x47`) + `SHAPE_COMPONENT` (`0x4C`) +
     `SHAPE_COMPONENT_PICTURE` (`0x55`), with the original extent in
     HWPUNIT (px × 75) and the display extent as the current size.
   - HWPX: `<hp:pic>` with `<hp:orgSz>` = px × 75, `<hp:curSz>` =
     display, and a `<hc:scaMatrix>` carrying `display / native`.
3. **Anchor it in the text.**
   - Binary: an inline control char (`0x0B`) in the target paragraph's
     `PARA_TEXT`, counted in `PARA_HEADER.chars`, plus a dummy
     `PARA_LINE_SEG` so layout recomputes.
   - HWPX: the `<hp:pic>` sits inside an `<hp:run>` (treat-as-char), no
     cache to invalidate.

The asymmetry is real: HWPX hides the CFB tree and the layout cache, so
its image path is *shorter*. The binary path is longer but the geometry
math (the ×75 extents, the scale-to-display ratio) is identical.

## Why this is worth writing down

- The **CharShape ↔ charPr 7-slot** equivalence ([GOTCHAS §3](GOTCHAS.md#3-why-does-my-english-text-refuse-to-change-font-in-hancom))
  means the mixed-script font bug is *one* bug with two fixes, not two bugs.
- The **HWPUNIT / ×75** constant means image sizing is solved once for both.
- When HWPX support lands, this table is the spec — the new code mirrors
  the binary record handlers element-for-element, not from scratch.

## See also

- [RECORD_FORMAT.md](RECORD_FORMAT.md) — binary record byte layouts.
- [GOTCHAS.md](GOTCHAS.md) — the traps, several of which are cross-format.
- [pyhwp](https://github.com/mete0r/pyhwp) — binary record reference.
- The HWP 5.0 / OWPML specs from Hancom (Korean).
