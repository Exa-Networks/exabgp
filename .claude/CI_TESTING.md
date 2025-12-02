# CI Testing

Run ALL tests before declaring code ready.

---

## Required Test Sequence

```bash
./qa/bin/test_everything  # ALL tests, exits on first failure
```

**Individual commands (for debugging only):**
```bash
uv run ruff format src && uv run ruff check src
env exabgp_log_enable=false uv run pytest ./tests/unit/
./qa/bin/functional encoding
./qa/bin/functional decoding
./sbin/exabgp configuration validate -nrv ./etc/exabgp/conf-ipself6.conf
```

---

## Pre-Commit Checklist

- [ ] `./qa/bin/test_everything` passes all 6 suites
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
- Unit tests (Python 3.10-3.13)
- Functional tests (Python 3.10-3.13)
