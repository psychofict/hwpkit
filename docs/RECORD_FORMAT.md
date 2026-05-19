# HWP 5.0 Record Format

Working notes for the record-level binary format used in `BodyText/Section*`
and `DocInfo` streams. Distilled from pyhwp, the HWP 5.0 spec, and what
Hancom actually accepts in practice.

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
