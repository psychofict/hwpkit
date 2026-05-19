# Test fixtures

Real HWP files aren't committed to this repo (see `.gitignore`).

To run the end-to-end CFB round-trip test in `tests/test_roundtrip.py`,
point `HWPKIT_FIXTURE` at a local `.hwp` file:

```bash
HWPKIT_FIXTURE=/path/to/some/blank.hwp pytest tests/test_roundtrip.py -v
```

Without that env var, the round-trip test is skipped. The unit tests
in `test_records.py` and `test_charshape.py` do not need a fixture
and run unconditionally.
