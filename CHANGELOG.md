# Changelog

All notable changes to `hwpkit` are documented here. The format is based
on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this
project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-06-09

First stable release. The public API is now committed to Semantic
Versioning: no breaking changes without a 2.0.

### Added

- **`open_document(path)`** — opens a `.hwp` or `.hwpx` (detected by
  container content) and returns a uniform editor. One calling pattern
  across both formats; downstream code never branches on format.
- **`HwpFile`** — an object-oriented editor for binary `.hwp` mirroring
  `HwpxFile`: `open` / `paragraphs` / `describe` / `paragraph_text` /
  `inject_text` / `replace_text` / `swap_in_para_text` / `place_image` /
  `save`. Paragraphs are indexed across all `BodyText` sections.

### Notes

- Backward compatible: the functional helpers (`fill_hwp`, the
  `records`-list editors, the file-to-file `place_image`, and all
  extraction functions) are unchanged and remain supported.
- Development status promoted to Production/Stable.

## [0.2.1] — 2026-06-09

Docs & discoverability — no code changes; fully compatible with 0.2.0.

### Changed

- Rewrote the README around both formats and the pure-Python / no-Hancom
  story, with a clearer feature comparison and use-case framing.
- Expanded PyPI keywords and classifiers (HWPX, OWPML, RAG/LLM, NLP, RPA,
  Python 3.13); bumped Development Status to Beta; sharpened the summary.

## [0.2.0] — 2026-06-09

The dual-format release: `hwpkit` now spans both Hancom serializations —
binary `.hwp` and XML `.hwpx` — through one API, and gains image
insertion on both. `.hwp` and `.hwpx` are two encodings of one document
model, now documented in [docs/OBJECT_MODEL.md](docs/OBJECT_MODEL.md).

### Added

- **`.hwpx` (OWPML) support** — a new `hwpkit.hwpx` module:
  - `extract_text_from_hwpx(path)` — clean text from every section in
    document order, table-cell content included.
  - `HwpxFile` — an editor mirroring the binary verbs: `inject_text`,
    `replace_text`, `swap_in_para_text`, plus `describe()` /
    `paragraphs()` for locating fields. `save()` re-serializes only the
    parts that changed and copies the rest byte-for-byte (mimetype kept
    stored and first).
  - `fill_hwpx(in, out, edit_fn)` — the one-call analogue of `fill_hwp`.
- **Image insertion** on both formats:
  - `place_image(in, out, img, paragraph_index, width_mm=…)` for binary
    `.hwp` — adds a `BinData` stream, registers a `BIN_DATA` record +
    bumps the `ID_MAPPINGS` count, and anchors a `gso` picture object.
  - `HwpxFile.place_image(paragraph_index, img, width_mm=…)` for `.hwpx`
    — adds the `BinData/` part, registers it in `content.hpf`
    (`isEmbeded="1"`), and anchors an inline `<hp:pic>`.
  - Image extents follow the shared HWPUNIT rule (pixels × 75 = 7200/96).
- **CFB entry insertion** — `cfb.add_stream`, `cfb.add_storage`, and
  `cfb.find_entry`, built on a correct red-black-tree insert (so Hancom's
  on-open directory-tree validation passes). This is what makes adding a
  new `BinData` stream possible without corrupting the container.
- **Unified text extraction** — `extract_text_from_file(path)` detects
  `.hwp` vs `.hwpx` by container content (not extension); the
  `hwpkit-text` CLI dispatches the same way.
- **Docs** — `docs/OBJECT_MODEL.md` (binary-record ↔ OWPML map and the
  shared HWPUNIT unit); `docs/RECORD_FORMAT.md` gains an "Embedded
  images" section; `docs/GOTCHAS.md` gains §5 on image-extent sizing.
- **Optional extras** — `hwpkit[hwpx]` (lxml), `hwpkit[image]` (Pillow),
  `hwpkit[full]`. Both heavy deps are imported lazily, so the core
  install stays at just `olefile`.

### Notes

- Backward compatible: every existing import and function is unchanged.
- `lxml` / `Pillow` are only required for the features that use them; a
  binary-only `.hwp` workflow needs neither.

## [0.1.4] — 2026-05-19

- Credit Ebenworks in the README footer and PyPI sidebar.

## [0.1.1] – [0.1.3]

- Packaging and presentation polish: logo and GitHub social preview,
  absolute logo URL for PyPI rendering, expanded metadata/keywords, PyPI
  trusted-publishing workflow, badge cleanup.

## [0.1.0]

- Initial release (renamed from `hwpedit`): binary HWP 5.0 plain-text
  extraction, form filling (`inject_text` / `replace_text` /
  `swap_in_para_text`), the CFB rewriter that preserves directory-tree
  topology, per-script `CharShape` font control, and the `hwpkit-inspect`
  / `hwpkit-text` CLIs.

[1.0.0]: https://github.com/psychofict/hwpkit/releases/tag/v1.0.0
[0.2.1]: https://github.com/psychofict/hwpkit/releases/tag/v0.2.1
[0.2.0]: https://github.com/psychofict/hwpkit/releases/tag/v0.2.0
[0.1.4]: https://github.com/psychofict/hwpkit/releases/tag/v0.1.4
[0.1.0]: https://github.com/psychofict/hwpkit/releases/tag/v0.1.0
