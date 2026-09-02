---
description: >-
  Working notes on the HWP 5.0 record-level binary format in the BodyText and DocInfo streams: tag ids, level nesting, and size encoding.
---

# HWP 5.0 Record Format

Working notes for the record-level binary format used in `BodyText/Section*`
and `DocInfo` streams. Distilled from pyhwp, the HWP 5.0 spec, and what
Hancom actually accepts in practice.

> For how these binary records line up with their HWPX (OWPML) twins —
> and why the same `CharShape`, `BorderFill`, and HWPUNIT knowledge
> applies to both formats — see [OBJECT_MODEL.md](OBJECT_MODEL.md).

## Stream compression

`BodyText/Section*` and `DocInfo` are **raw deflate** (no zlib header).

```python
import zlib
zlib.decompress(stream_bytes, -15)               # decompress
zlib.compressobj(9, zlib.DEFLATED, -15)          # compress
```

The `FileHeader` stream's 32-bit value at offset 36 indicates compression:
bit 0 set → streams are compressed. Standard HWP files set this bit; some
templates exported from third-party tools don't. Always check.

## Record header

Each record begins with a little-endian uint32:

| Bits  | Field    |
|-------|----------|
| 0–9   | `tag_id` |
| 10–19 | `level`  |
| 20–31 | `size`   |

If `size == 0xFFF` (4095), the actual size is in the next 4 bytes,
making the header 8 bytes total. `hwpkit.records` tracks this via
`force_extended_header` on records that need the long form.

## Paragraph records

A paragraph is this sequence of records in order:

| Tag    | Name             | Notes |
|--------|------------------|-------|
| `0x42` | `PARA_HEADER`    | First 4 bytes = char count (uint32). High bit `0x80000000` is a "control paragraph" flag — preserve it when updating count. |
| `0x43` | `PARA_TEXT`      | UTF-16LE bytes. Use `\n` for soft line breaks, `\r` only as paragraph terminator. Char count must equal `len(text + "\r")`. |
| `0x44` | `PARA_CHAR_SHAPE`| List of `(start_pos, shape_id)` pairs. A single `(0, shape_id)` entry remains valid for any new char count — Hancom inherits the shape. |
| `0x45` | `PARA_LINE_SEG`  | Cached line layout. See [GOTCHAS.md §2](GOTCHAS.md#2-why-does-my-injected-text-render-as-a-smashed-single-line). |

Other tags encountered in BodyText: `0x47` `CTRL_HEADER`, `0x48`
`LIST_HEADER`, `0x4D` `TABLE`.

## Empty paragraph

A paragraph that is "empty" in Hancom's UI has:

- `PARA_HEADER.chars == 1` (the implicit trailing `\r`)
- **no** `PARA_TEXT` record

To fill it: update char count, insert PARA_TEXT after PARA_HEADER,
dummy-out PARA_LINE_SEG. `hwpkit.records.inject_text` handles all
three. A paragraph that was *previously* non-empty is a different
state — see [GOTCHAS.md §4](GOTCHAS.md#4-why-does-replace_text-corrupt-the-file).

## LineSeg struct (36 bytes per entry)

| Offset | Type    | Field             |
|--------|---------|-------------------|
| 0      | int32   | `chpos`           |
| 4      | int32   | `y`               |
| 8      | int32   | `height`          |
| 12     | int32   | `height_text`     |
| 16     | int32   | `height_baseline` |
| 20     | int32   | `space_below`     |
| 24     | int32   | `x`               |
| 28     | int32   | `width`           |
| 32     | uint32  | `flags` (default `0x00060000` = bits 17+18 = `line_head` + `line_tail`) |

Units are HWPUNIT = 1/7200 inch. Typical values: cell width 43764,
line height ~1100, space_below ~332.

## CharShape (DocInfo tag 0x15)

Body layout — first 46 bytes (the rest is color / attr / border data):

| Offset | Type        | Field          |
|--------|-------------|----------------|
| 0      | 7 × uint16  | `face_name_ids` per script |
| 14     | 7 × uint8   | `ratios`        |
| 21     | 7 × int8    | `char_spacings` |
| 28     | 7 × uint8   | `rel_sizes`     |
| 35     | 7 × int8    | `char_offsets`  |
| 42     | int32       | `base_size` (1/100 pt; 1100 = 11pt) |

Per-script slot order: Hangul, Latin, Hanja, Japanese, Symbol, User,
Other. See [GOTCHAS.md §3](GOTCHAS.md#3-why-does-my-english-text-refuse-to-change-font-in-hancom).

## Embedded images

Reverse-engineered from a real multi-image HWP. Inserting a picture
touches **three** places — the CFB container, DocInfo, and BodyText.

### 1. CFB container — the bytes

The image bytes live in a stream `BinData/BIN%04d.<ext>` (decimal id,
original extension preserved — e.g. `BIN0003.png`). Compression follows
the `BIN_DATA` record's attribute bits (below); with the default the
stream is raw-deflate like every other stream. Adding this stream means
splicing a node into the directory red-black tree — use
`cfb.add_stream` / `cfb.add_storage` (creates the `BinData` storage if
absent). See [GOTCHAS.md §1](GOTCHAS.md#1-why-does-my-edited-hwp-open-as-corrupted).

### 2. DocInfo — register the binary

- **`ID_MAPPINGS` (tag `0x11`)**: an array of `int32` counts; **index 0
  is the BinData count.** Increment it by one per image added.
- **`BIN_DATA` (tag `0x12`)**, appended after the existing `BIN_DATA`
  records (level 1), body:

  | Offset | Type | Field |
  |--------|------|-------|
  | 0 | uint16 | `attr` — `0x0001` = type *embedding*. Low nibble = type (0 link / 1 embed / 2 storage); bits 4–5 = compress (0 default / 1 force / 2 none). |
  | 2 | uint16 | `bin_id` — matches the `%04d` in the stream name |
  | 4 | uint16 | `ext_len` — extension length in UTF-16 code units |
  | 6 | UTF-16LE | extension, e.g. `png` |

  Observed: `0100 0100 0300 6a0070006700` = embed, id 1, `"jpg"`.

### 3. BodyText — the picture object + its anchor

A picture is a **GSO** (general shape object). In the host paragraph:

- **Inline anchor** in `PARA_TEXT`: an extended control occupying **8
  code units (16 bytes)** — `[0x0B]` + ctrl-id `"gso "` stored reversed
  (`20 6f 73 67`) + 8 zero bytes + `[0x0B]`. The `0x0B` count (here 8)
  **plus the trailing `0x0D`** is the paragraph's `chars`. Replace
  `PARA_LINE_SEG` with the 36-byte dummy ([GOTCHAS §2](GOTCHAS.md#2-why-does-my-injected-text-render-as-a-smashed-single-line)).
- **`CTRL_HEADER` (`0x47`)**, ctrl-id `"gso "` — common object position/
  size attributes (HWPUNIT).
- **`SHAPE_COMPONENT` (`0x4C`)**, ctrl-id `"$pic"`, then 4×4 transform
  matrices as IEEE-754 `double` (identity = `00 00 00 00 00 00 f0 3f`).
- **`SHAPE_COMPONENT_PICTURE` (`0x55`)**, 91 bytes observed: border
  line/fill, 4 corner points (image rect, HWPUNIT), crop, inner margins,
  then the **`bin_id` (uint16) at offset 71**, then bright/contrast/
  effect. Extents are pixels × 75 (see
  [OBJECT_MODEL.md](OBJECT_MODEL.md#the-shared-unit-hwpunit--17200-inch)).

So: register bytes (1+2), then anchor the GSO chain (3) in a target
paragraph, with the picture record pointing back at the `bin_id`.
