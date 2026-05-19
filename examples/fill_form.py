#!/usr/bin/env python3
"""Generic HWP form-fill example driven by a JSON spec.

Use `hwpkit-inspect <template.hwp>` first to discover paragraph indices,
then describe the edits in a JSON file:

    {
      "template": "template.hwp",
      "output":   "filled.hwp",
      "inject":  { "24": "홍길동", "26": "2023021683" },
      "replace": { "75": "2026. 05. 19." },
      "swap":    { "40": ["□ 석사", "☑ 석사"] }
    }

Run:

    python fill_form.py example_data.json
"""

from __future__ import annotations

import json
import sys

from hwpkit import fill_hwp, inject_text, replace_text, swap_in_para_text


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: fill_form.py <data.json>", file=sys.stderr)
        sys.exit(2)

    with open(argv[0], encoding="utf-8") as f:
        spec = json.load(f)

    def edit(records):
        for pi, val in spec.get("inject", {}).items():
            inject_text(records, int(pi), val)
        for pi, val in spec.get("replace", {}).items():
            replace_text(records, int(pi), val)
        for pi, pair in spec.get("swap", {}).items():
            old, new = pair
            swap_in_para_text(records, int(pi), old, new)

    sizes = fill_hwp(spec["template"], spec["output"], edit)
    print(f"wrote {spec['output']}: raw {sizes[0]}->{sizes[1]}, "
          f"compressed {sizes[2]}->{sizes[3]}")


if __name__ == "__main__":
    main()
