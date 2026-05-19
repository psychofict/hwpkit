"""hwpkit — edit HWP 5.0 (Hancom Office) files in Python.

Quickstart:

    from hwpkit import fill_hwp, inject_text, swap_in_para_text

    def edit(records):
        inject_text(records, 24, "홍길동")
        swap_in_para_text(records, 40, "□ 석사", "☑ 석사")

    fill_hwp("template.hwp", "out.hwp", edit)
"""

from .cfb import load, dump
from .records import (
    TAG_PARA_HEADER,
    TAG_PARA_TEXT,
    TAG_PARA_CHAR_SHAPE,
    TAG_PARA_LINE_SEG,
    compress,
    decompress,
    describe,
    extract_text,
    index_paragraphs,
    inject_text,
    parse,
    replace_text,
    serialize,
    swap_in_para_text,
)
from .pipeline import (
    docinfo_sid,
    file_header_compressed,
    fill_hwp,
    section0_sid,
)
from .extract import extract_text_from_hwp

__version__ = "0.1.0"

__all__ = [
    "load",
    "dump",
    "parse",
    "serialize",
    "decompress",
    "compress",
    "inject_text",
    "swap_in_para_text",
    "replace_text",
    "describe",
    "extract_text",
    "extract_text_from_hwp",
    "index_paragraphs",
    "fill_hwp",
    "section0_sid",
    "docinfo_sid",
    "file_header_compressed",
    "TAG_PARA_HEADER",
    "TAG_PARA_TEXT",
    "TAG_PARA_CHAR_SHAPE",
    "TAG_PARA_LINE_SEG",
    "__version__",
]
