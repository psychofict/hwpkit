"""Bundled donor picture-object records (the `gso -> $pic ->
SHAPE_COMPONENT_PICTURE` chain) extracted from a real, Hancom-authored HWP
and neutralized (object label blanked). `hwpkit.picture` clones these and
patches the bin-id + extents — see docs/RECORD_FORMAT.md "Embedded images".

These are format scaffolding (geometry + control ids + identity transform
matrices), not document content. Levels: CTRL_HEADER=3, SHAPE_COMPONENT=4,
SHAPE_COMPONENT_PICTURE=5 (relative to a paragraph at level 2)."""

import base64

# patch offsets (see docs/RECORD_FORMAT.md)
CH_DISP_W, CH_DISP_H = 16, 20          # CTRL_HEADER: display box w/h (u32, HWPUNIT)
SC_NATIVE_W, SC_NATIVE_H = 20, 24      # SHAPE_COMPONENT: native w/h (u32)
SC_DISP_W, SC_DISP_H = 28, 32          # SHAPE_COMPONENT: display w/h (u32)
PIC_BIN_ID = 71                        # SHAPE_COMPONENT_PICTURE: bin id (u16)
PIC_RECT = 12                          # 4 corner points (i32 x,y) -> native rect

CTRL_HEADER = base64.b64decode(
    "IG9zZxEjKgQAAAAAAAAAAPBRAAAEEAAAAwAAAAAAAAAAAAAA1xBNXQAAAABKAPitvLmFx8iy5LIuAA0ACgDQxvi8IAD4rby5WMcgAHTHhLk6ACAA/KxZ1TCuIMIVyPS8tdHgwoC9XwBtrV8AjMiwxi4AagBwAGcADQAKANDG+LwgAPitvLlYxyAAbNAwrjoAIAAArFy4IAA1ADkAOABwAGkAeABlAGwALAAgADjBXLggADEAIAAgACAAIAAgACAAIAAAAA=="
)
SHAPE_COMPONENT = base64.b64decode(
    "Y2lwJGNpcCQAAAAATf7//wAAAQDo6QAAiCwAAPBRAAAEEAAAAAAIJAAA+CgAAAIIAAABAAAAAAAAAPA/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8D8AAAAAADB7wOy9ezZTa9Y/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAASHAfwX0E1z8AAAAAADB7QAAAAAAAAPA/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8D8AAAAAAAAAAA=="
)
PICTURE = base64.b64decode(
    "AAAAAAAAAAAAAAAAAAAAAAAAAADo6QAAAAAAAOjpAACILAAAAAAAAIgsAAAAAAAAAAAAAPh/AADYGAAAAAAAAAAAAAAAAAABAADYEE0dAAAAAPh/AADYGAAAAA=="
)
