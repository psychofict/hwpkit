# CLAUDE.md

Guidance for Claude Code (and contributors) working in this repository.

## What this is

`hwpkit` is a **pure-Python library for Korean HWP / HWPX (Hancom Office)
documents** — read, extract text, edit (fill forms), and insert images, across
**both** the binary `.hwp` (HWP 5.0) and XML `.hwpx` (OWPML) formats, with **no
Hancom and no Windows** required. Published on PyPI as `hwpkit`; docs at
**https://hwpkit.ebenworks.co**. MIT licensed. Author: Ebenworks (GitHub
`psychofict/hwpkit`).

`.hwp` and `.hwpx` are **two serializations of one document model** (OWPML).
The same concepts — CharShape, BorderFill, paragraphs, the layout cache,
embedded images — exist in both; see `docs/OBJECT_MODEL.md`.

## Layout

```
hwpkit/
  cfb.py            MS-CFB container: load/dump (rebuilds the whole container,
                    preserving directory-tree topology); add_stream/add_storage/
                    find_entry (red-black-tree insert for adding streams).
  records.py        HWP 5.0 record parse/serialize; inject_text / replace_text /
                    swap_in_para_text; extract_text; index_paragraphs;
                    decompress/compress; the dummy-LineSeg fix (_regenerate_lineseg).
  charshape.py      DocInfo CharShape (tag 0x15) 7-slot font helpers.
  pipeline.py       fill_hwp (functional binary editor); section0_sid /
                    docinfo_sid / file_header_compressed.
  picture.py        Binary image insertion: register_bindata (DocInfo),
                    build_picture_records + anchor_picture (BodyText), the
                    file-to-file place_image. Sizing constant PX_TO_HWPUNIT.
  _picture_donor.py Bundled, neutralized picture-object record bodies (extracted
                    from a real Hancom file) + patch-offset constants. Used by
                    picture.build_picture_records — do not hand-edit the blobs.
  hwpx.py           HWPX: extract_text_from_hwpx, is_hwpx, HwpxFile (OO editor +
                    place_image), fill_hwpx. lazy-imports lxml.
  hwp.py            HwpFile (OO binary editor mirroring HwpxFile) + open_document
                    (auto-detects .hwp/.hwpx, returns the right editor). lazy PIL.
  extract.py        extract_text_from_hwp; extract_text_from_file (dispatcher);
                    `hwpkit-text` CLI.
  inspect.py        `hwpkit-inspect` CLI — dumps Section0 paragraph structure.
docs/               MkDocs Material site (see "Docs site"); OBJECT_MODEL.md,
                    RECORD_FORMAT.md, GOTCHAS.md are the format references.
tests/              pytest; some tests gate on local fixtures (see "Testing").
```

Two public API styles, both supported (do not break either):
- **Object**: `open_document(path)` → `HwpFile` / `HwpxFile` with identical
  methods (`paragraphs`/`describe`/`inject_text`/`replace_text`/
  `swap_in_para_text`/`place_image`/`save`). This is the recommended entry.
- **Functional**: `fill_hwp` + the `records`-list editors, `fill_hwpx`, the
  file-to-file `place_image`, and the `extract_text_*` functions.

## Commands

```bash
pip install -e .[full]          # editable install with lxml + Pillow

# Tests. Unit tests run with no fixture; integration tests need real files
# (NOT committed — see Testing). Point env vars at local samples:
HWPKIT_FIXTURE=/path/to/sample.hwp \
HWPKIT_HWPX_FIXTURE=/path/to/sample.hwpx \
  python -m pytest -q

# Docs site (Material). Build/preview locally:
pip install -r docs/requirements.txt
mkdocs serve            # or: mkdocs build
```

## Conventions & invariants

- **Optional deps are lazy.** Core install is `olefile` only. `lxml` (`.hwpx`)
  and `Pillow` (images) are imported *inside* the functions that use them, and
  declared as extras `[hwpx]` / `[image]` / `[full]`. Keep them lazy so a
  binary-only `.hwp` workflow needs neither — never add a top-level
  `import lxml`/`PIL` to a module imported by `hwpkit/__init__.py`.
- **API is stable (SemVer, ≥1.0).** No breaking changes to the public API
  without a major bump. Add, don't rename/remove.
- **Version lives in two places** — bump both: `pyproject.toml` `version` and
  `hwpkit/__init__.py` `__version__`. Also add a `CHANGELOG.md` entry.

## Format gotchas (the hard-won knowledge — see docs/GOTCHAS.md)

- **CFB rewrite must preserve the directory red-black tree.** Hancom validates
  it on open. `cfb.dump` rebuilds the container from `entries`, copying
  left/right/child/color byte-for-byte; `cfb.add_stream` does a correct RB
  insert so a new `BinData` stream can be added.
- **LineSeg cache.** When a paragraph's char count changes, its `PARA_LINE_SEG`
  must be replaced with **36 zero bytes** (dummy) or text renders smashed onto
  one line. `records._regenerate_lineseg` does this; the no-op case is a
  same-length `swap_in_para_text`.
- **`replace_text("")` corrupts the file** when combined with other edits. Use
  a `" "` / `"—"` placeholder, never empty.
- **CharShape has 7 per-script font slots** (Hangul/Latin/Hanja/JP/Symbol/User/
  Other). Changing one (the toolbar default) leaves mixed-script runs unchanged;
  use `charshape.flatten_to_face`.
- **Image extents = pixels × 75** (`PX_TO_HWPUNIT`), i.e. `7200/96` HWPUNIT per
  px — the same constant for binary `SHAPE_COMPONENT_PICTURE` and HWPX
  `<hp:orgSz>`.
- **HWPX image wiring lives in `Contents/content.hpf`** as
  `<opf:item … isEmbeded="1">`; `<hc:img binaryItemIDRef>` references that item
  id. There is **no** `<hh:binItem>` in `header.xml` and **no** entry in
  `META-INF/manifest.xml` (it's empty `<odf:manifest/>`). Mirror real Hancom
  output, which is how `HwpxFile.place_image` was built.
- **Binary picture insertion uses a bundled donor** (`_picture_donor.py`) cloned
  from genuine Hancom output and re-targeted (bin-id + extents) — chosen over
  hand-synthesis because it's byte-identical to what Hancom accepts.

## Testing & verification

- No `.hwp`/`.hwpx` fixtures are committed (`.gitignore`: `tests/fixtures/*.hwp*`).
  Integration tests skip unless `HWPKIT_FIXTURE` / `HWPKIT_HWPX_FIXTURE` point at
  local samples; unit tests (`test_records`, `test_charshape`, `test_cfb_add`,
  the synthetic `test_hwpx` cases) run unconditionally.
- **There is no local HWP renderer.** LibreOffice cannot open these files.
  Verify edits **structurally** — round-trip through `cfb` + re-parse, reopen the
  output with `olefile` (an independent CFB parser) — and for anything visual
  (images, layout) the author opens the output in **Hancom**. HWPX edits are
  fully checkable locally (re-zip → re-parse).

## Release process

`publish.yml` publishes to PyPI via **trusted publishing**, triggered **only by
a published GitHub Release** (never by a push). To cut a release:

1. Bump `version` in `pyproject.toml` **and** `__version__` in
   `hwpkit/__init__.py`; add a `CHANGELOG.md` entry.
2. Validate before publishing: `python -m build` + `twine check dist/*` (and,
   if classifiers changed, check them against `trove-classifiers`). A clean-venv
   `pip install -e .[full]` + `pytest` catches metadata/import breakage.
3. Commit to `main`, then `gh release create vX.Y.Z --target main` → this fires
   `publish.yml`. PyPI versions are immutable — never reuse one.

CI (`ci.yml`) runs the test matrix (Python 3.9–3.13) on push/PR and installs
`.[full]` so the `.hwpx`/image tests actually run.

## Docs site

MkDocs Material (`mkdocs.yml` + `docs/`), deployed to the `gh-pages` branch via
`docs.yml` on every push to `main` (`mkdocs gh-deploy`). `docs/CNAME` pins the
custom domain `hwpkit.ebenworks.co`. The API reference is auto-generated from
docstrings by `mkdocstrings` (so keep docstrings accurate). There's a blog
(`docs/blog/`, Material blog plugin) for SEO posts; `docs/robots.txt` +
the generated `sitemap.xml` cover crawlers.

## Security

Never commit secrets. The PyPI account recovery-codes file pattern
(`*Recovery-Codes*`), `*.pypirc`, and `.env` are gitignored; keep credentials
out of the working tree entirely.
