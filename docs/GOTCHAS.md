# HWP 5.0 Gotchas

The four things that take a week to figure out the first time. If
you're trying to edit HWP files programmatically and Hancom is
rejecting your output or rendering it strangely, start here.

## 1. Why does my edited HWP open as "corrupted"?

You probably edited a `BodyText/Section0` stream whose byte length
changed, then wrote it back through a naive CFB writer.

HWP is a Microsoft Compound File Binary (MS-CFB) container. Its
directory is a **red-black tree** of named entries — siblings are
ordered by name with specific comparison rules (MS-CFB §2.6.4: compare
UTF-16 lengths first, then case-folded code points). Hancom validates
the tree invariants on open, and most naive implementations get the
name comparison wrong.

The standard library workaround `olefile.OleFileIO.write_stream`
sidesteps the problem by only allowing same-size rewrites — but you
almost always change size when injecting Korean text.

**The fix:** read the original 128-byte directory records straight
from the file (not through olefile's parsed view) and preserve their
`sid_left`, `sid_right`, `sid_child`, and `color` fields byte-for-byte
in the output. The tree topology is already valid; reusing it
sidesteps the comparison-rule trap entirely.

`hwpedit.cfb.load` / `hwpedit.cfb.dump` does this.

## 2. Why does my injected text render as a smashed single line?

You updated `PARA_HEADER.chars` and added or replaced `PARA_TEXT`, but
didn't touch the `PARA_LINE_SEG` record (tag `0x45`). Hancom caches
the rendered line layout in that record. With stale cache data Hancom
draws all your new characters overlaid on the original one-character
line.

Things you might try, and why they fail:

| Approach | Result |
|----------|--------|
| Leave the original LineSeg alone | New text smashes onto a single line — Hancom uses the stale cache |
| Delete the PARA_LINE_SEG record | Hancom rejects the file as corrupted (record is mandatory) |
| Build a multi-segment LineSeg covering the new chars | Cell grows vertically, but text still smashes onto the last segment |
| **Replace the body with 36 zero bytes** | ✅ Hancom recomputes layout from PARA_CHAR_SHAPE metrics |

The all-zero LineSeg is pyhwp's documented "dummy LineSeg" fallback
(`hwp5/xmlmodel.py`, comment "더미 LineSeg를 만들어 준다"). Hancom
treats it as a sentinel meaning "no cached layout, please recompute."

`hwpedit.records.inject_text` and `replace_text` already do this
whenever the character count changes. Only when the count stays
identical (e.g. a single-character checkbox swap `□` → `☑`) is it safe
to leave the LineSeg untouched — and that's what `swap_in_para_text`
relies on.

## 3. Why does my English text refuse to change font in Hancom?

HWP's `CharShape` record (DocInfo tag `0x15`) has **seven** per-script
font slots:

| Slot | Script         | When it's used                     |
|------|----------------|------------------------------------|
| 0    | 한글 (Hangul)  | Korean syllables                   |
| 1    | 영문 (Latin)   | A–Z, a–z, basic punctuation        |
| 2    | 한자 (Hanja)   | CJK Unified Ideographs             |
| 3    | 일어 (Japanese)| Hiragana, Katakana                 |
| 4    | 기호 (Symbol)  | Symbols                            |
| 5    | 사용자 (User)  | User-defined script range          |
| 6    | 기타 (Other)   | Everything else                    |

Hancom's font dropdown in the toolbar typically binds to **one slot**
— usually Hangul. So if your paragraph mixes Korean and Latin text
and the Latin slot points to a different font, changing the font via
the toolbar silently fails on the Latin runs. The Korean part updates,
the English part doesn't.

**Fix in Hancom (GUI):** select the text, press <kbd>Alt</kbd>+<kbd>L</kbd>
to open 글자 모양, set 대표 글꼴 and check the "모든 언어" / per-language
boxes to propagate.

**Fix programmatically:** use `hwpedit.charshape.flatten_to_face` to
overwrite all 7 face_name_ids with the same face id. Operate on the
DocInfo stream's parsed records, not BodyText.

```python
from hwpedit import cfb, records
from hwpedit.pipeline import docinfo_sid, file_header_compressed
from hwpedit import charshape

entries = cfb.load("template.hwp")
di_sid = docinfo_sid(entries)
raw = entries[di_sid].data
if file_header_compressed(entries):
    raw = records.decompress(raw)
di = records.parse(raw)

i = charshape.find_charshape(di, 18)   # the 19th CharShape in DocInfo
charshape.flatten_to_face(di[i], 0)    # all slots → face_id 0
```

## 4. Why does `replace_text("")` corrupt the file?

`replace_text(records, N, "")` sets `PARA_HEADER.chars` to 1 and the
PARA_TEXT body to `\r` (UTF-16). On its own, this paragraph opens
fine in Hancom. But combined with other table-cell edits in the same
document, Hancom flags the file as corrupted on open.

The reason: an *originally* empty HWP paragraph has `chars == 1` and
**no** PARA_TEXT record at all. A paragraph wiped via `replace_text("")`
has `chars == 1` *plus* a PARA_TEXT record whose body is `\r`. The
two states are not equivalent. Hancom tolerates the inconsistency in
isolation but trips a corruption check when sibling cells in the same
table have also grown via narrative injects.

Empirical bisect on one document:

| Edits applied | Opens? |
|---|---|
| Minimum required only | ✅ |
| Min + 6 long narrative injects | ✅ |
| Min + all `replace_text` calls (including a replace-to-empty) | ✅ |
| **Min + narratives + replace-to-empty** | ❌ corrupted |
| Min + narratives + score boxes | ✅ |
| Min + narratives + date/sig replacements | ✅ |

**Fix:** don't wipe a paragraph to empty. Either leave template-hint
text intact, or use `" "` or `"—"` as a placeholder. If you're hitting
"corrupted" on open and one of your edits is a replace-to-empty,
remove it and bisect from there.
