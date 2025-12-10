# CI Testing

Run ALL tests before declaring code ready.

---

## Required Test Sequence

```bash
./qa/bin/test_everything  # ALL 15 tests, exits on first failure
```

**Individual commands (for debugging only):**
```bash
uv run ruff format src && uv run ruff check src
env exabgp_log_enable=false uv run pytest ./tests/unit/
./qa/bin/functional encoding
./qa/bin/functional decoding
./sbin/exabgp configuration validate -nrv ./etc/exabgp/conf-ipself6.conf
./qa/bin/test_api_encode              # cmd→raw verification
./qa/bin/test_api_encode --self-check # raw→cmd→raw round-trip
./qa/bin/test_json                    # JSON decode regression tests
```

---

## Pre-Commit Checklist

- [ ] `./qa/bin/test_everything` passes all 15 tests
- [ ] `git status` reviewed
- [ ] User approval

**If ANY unchecked: DO NOT COMMIT**

---

## Debugging

### Encoding Test Failures

Run server + client in separate terminals:

```bash
# Terminal 1 (start FIRST)
./qa/bin/functional encoding --server <test_id>

# Terminal 2 (start SECOND)
./qa/bin/functional encoding --client <test_id>
```

**See:** `.claude/FUNCTIONAL_TEST_DEBUGGING_GUIDE.md` for complete process.

### Port Conflicts

```bash
killall -9 Python  # macOS uses capital P
```

---

## CI Workflows

All must pass:
- Linting (Python 3.12)
- Type checking (Python 3.12)
- Unit tests (Python 3.12-3.14)
- Functional tests (Python 3.12-3.14)
