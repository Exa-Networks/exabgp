# Backport Tracking

Bug fixes that need backporting to stable branches.

**Last reviewed commit:** cbc231b9

---

## Pending Backports

| Date | Commit | Description | Target Branch | Status |
|------|--------|-------------|---------------|--------|
| 2025-11 | 086b3ec1 | Config reload race condition - API processes see stale neighbor config (fixes #1340) | 5.0 | 🔴 Pending |
| 2025-11 | 48e4405c | Critical RIB race conditions - iterator crash, cache corruption, missing routes | 5.0 | 🔴 Pending |
| 2025-11 | be0d1a55 | SAFI typo - 'mcast-vpnmpls-vpn' split into separate values | 5.0 | 🔴 Pending |
| 2025-11 | 04410ed5 | BGP-LS srv6endx.py JSON bug - hexstring().json() would fail | 5.0 | 🔴 Pending |
| 2025-11 | 7677b415 | Process change detection - config reload failure handling | 5.0 | 🟡 Review |
| 2025-11 | 30caf8e7 | Duplicate capability detection in BGP OPEN parsing | 5.0 | 🟡 Review |
| 2025-11 | 05c35fce | handle_connection bug - return value not propagated, md5 param confusion | 5.0 | 🔴 Pending |
| 2025-11 | 6553be10 | .afi_safi() bug - invalid call on tuple in inject_operational | 5.0 | 🔴 Pending |
| 2025-11 | 2f4d05d0 | write_async bug - was using sock_sendall(int), now uses os.write() | 5.0 | 🔴 Pending |
| 2025-11 | (pending) | attributes.py:340 - `attribute.ID` should be `aid` (bytes has no .ID, crashes on duplicate attr) | 5.0 | 🔴 Pending |
| 2025-11 | (pending) | multitopology.py:90 - `__str__` calls non-existent `self.pack()`, should be `self.pack_tlv()` | 5.0 | 🟡 Review |
| 2025-11 | (pending) | neighbor.py:144-145 - `str(None)` produces "None" instead of "not set" for peer/local-address | 5.0 | 🟡 Review |
| 2025-11 | (pending) | aggregator.py:65 - JSON format used `%d` for IPv4 speaker address, should be `%s` | 5.0 | 🔴 Pending |
| 2025-11 | (pending) | `__neq__` typo - 16 classes had `__neq__` instead of `__ne__`, method was dead code (never called) | 5.0 | 🔴 Pending |
| 2025-11 | 1cd928bd | Preserve singleton identity through deepcopy for ADD-PATH | 5.0 | 🔴 Pending |
| 2025-11 | (pending) | linkid.py JSON bug - `json()` returned invalid JSON (missing `{}` wrapper) | 5.0 | 🔴 Pending |
| 2025-11 | (pending) | link.py `link_identifiers` bug - assigned single object to list, stayed empty | 5.0 | 🔴 Pending |
| 2025-11 | (pending) | check.py ADD_PATH bug - used all known families instead of neighbor's configured addpath families | 5.0 | 🔴 Pending |
| 2025-11 | (pending) | message.py register() - checked `klass.TYPE` (bytes) but dict uses `klass.ID` (int), duplicate registration check broken | 5.0 | 🔴 Pending |

---

## Priority Legend

- 🔴 **Pending** - Needs backport, confirmed bug fix
- 🟡 **Review** - Needs review to determine if backport needed
- 🟢 **Done** - Backported
- ⚪ **Skip** - Not applicable for backport (6.0-only feature, etc.)

---

## Notes

**Not backported (6.0-only or refactoring):**
- Python 3.10+ syntax changes (ca284e03, ade3edff)
- Async mode fixes (9a6a9e49, f2d6852d, 8f4c046e) - async is 6.0-only
- CLI fixes (c2036349, 1b8e359f, 5c6f7c36) - new CLI is 6.0-only
- Type annotation fixes without runtime impact
- Test-only fixes

---

## Completed Backports

| Date | Commit | Description | Backported To | PR |
|------|--------|-------------|---------------|-----|
| | | | | |
