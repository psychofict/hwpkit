# API reference

Auto-generated from the source docstrings.

## Unified entry point

The recommended way in — open any `.hwp` or `.hwpx` and get a uniform editor.

::: hwpkit.hwp.open_document

## Editors

Both classes expose the same methods, so code written against one works against
the other.

::: hwpkit.hwp.HwpFile

::: hwpkit.hwpx.HwpxFile

## Text extraction

::: hwpkit.extract.extract_text_from_file

::: hwpkit.extract.extract_text_from_hwp

::: hwpkit.hwpx.extract_text_from_hwpx

::: hwpkit.hwpx.is_hwpx

## Functional helpers (binary `.hwp`)

The original record-level API. `fill_hwp` hands your callback the parsed record
list; the editors below mutate it in place.

::: hwpkit.pipeline.fill_hwp

::: hwpkit.records.inject_text

::: hwpkit.records.replace_text

::: hwpkit.records.swap_in_para_text

::: hwpkit.records.extract_text

::: hwpkit.records.describe

## Functional helpers (`.hwpx`)

::: hwpkit.hwpx.fill_hwpx

## Image insertion

::: hwpkit.picture.place_image

## Low-level CFB container

The MS-CFB reader/writer that makes corruption-free rewrites possible.

::: hwpkit.cfb.load

::: hwpkit.cfb.dump

::: hwpkit.cfb.add_stream

::: hwpkit.cfb.add_storage

::: hwpkit.cfb.find_entry
