---
description: >-
  How hwpkit differs from pyhwp, pyhwpx and olefile for reading and editing .hwp files in Python: pure-Python vs COM automation, write support, HWPX coverage and what each one can actually do.
---

# hwpkit vs pyhwp, pyhwpx & olefile

If you're trying to **read, parse, or edit `.hwp` / `.hwpx` files in Python**,
these are the options. Here's how they actually differ.

|  | `pyhwp` | `pyhwpx` | `olefile` | **`hwpkit`** |
|---|:---:|:---:|:---:|:---:|
| Pure Python (no Hancom / no Windows) | ✅ | ❌ *(needs Hancom + COM)* | ✅ | ✅ |
| Extract text — `.hwp` | ✅ | ✅ | ❌ | ✅ |
| Extract text — `.hwpx` | ❌ | ✅ | ❌ | ✅ |
| Edit text without corrupting the file | ❌ | ✅ *(via Hancom)* | ❌ | ✅ |
| Rewrite a stream that grew / shrank | ❌ | n/a | ❌ | ✅ |
| Insert an image (seal / signature) | ❌ | ✅ *(via Hancom)* | ❌ | ✅ |
| One API across `.hwp` **and** `.hwpx` | ❌ | ✅ | ❌ | ✅ |
| Runs in CI / Linux / containers | ✅ | ❌ | ✅ | ✅ |

## When to use which

### `hwpkit`
Use it when you need to **read or edit HWP/HWPX anywhere** — Linux servers, CI,
containers, serverless — with no Hancom license and no Windows. It extracts
clean text (great for RAG), fills forms, ticks checkboxes, and stamps
seal/signature images, then writes a file Hancom opens cleanly. One API
([`open_document`](api.md)) covers both formats.

### [`pyhwp`](https://github.com/mete0r/pyhwp)
The reference implementation for the **binary HWP 5.0 record format** and for
**semantic HWP → XML (OWPML) conversion**. Read-oriented; it doesn't edit
files in place or handle `.hwpx`. `hwpkit` learned the binary record format
from reading its source — if you need a full structural HWP→XML conversion,
reach for `pyhwp`.

### `pyhwpx`
Automates the **Hancom Office application** over Windows COM. Extremely capable
*because it drives the real editor* — but that's also the catch: it **requires
Windows and a Hancom installation**, so it can't run on a Linux server, in CI,
or in a container. Great for desktop RPA; wrong tool for a backend pipeline.

### [`olefile`](https://github.com/decalage2/olefile)
A low-level **MS-CFB container** reader/writer. It can read raw HWP streams and
rewrite a stream *only if its byte length is unchanged* — which it almost never
is once you insert Korean text. `hwpkit` uses `olefile` on the read side and
adds the full container rewrite on top.

## The short version

`hwpkit` is the only option that **reads, edits, and stamps images into both
`.hwp` and `.hwpx`** in **portable, pure Python** — no Hancom, no Windows, no
COM bridge. If your code runs anywhere other than a Windows desktop, that's the
difference that matters.

[Get started →](quickstart.md){ .md-button .md-button--primary }
