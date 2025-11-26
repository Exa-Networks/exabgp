# Refactoring Plan: Rename `code`/`subcode` to `notification_code`/`notification_subcode`

**Status:** Planning
**Priority:** 🟡 Medium
**Created:** 2025-11-26

---

## 🎯 Objective

Rename `Notification.code` → `Notification.notification_code` and `Notification.subcode` → `Notification.notification_subcode` to resolve the name clash with `Message.code()` classmethod.

---

## 📊 Impact Summary

| Category | Files | Changes |
|----------|-------|---------|
| Core definition | 1 | 5 |
| API responses | 2 | 3 |
| Reactor | 2 | 8 |
| Unit tests | 2 | 48 |
| **Total** | **7** | **~64** |

---

## 📁 Files to Modify

### 1️⃣ `src/exabgp/bgp/message/notification.py` (Definition)

| Line | Current | New |
|------|---------|-----|
| 102 | `def __init__(self, code: int, subcode: int, ...)` | Parameters stay as `code`, `subcode` (local vars) |
| 104 | `self.code = code` | `self.notification_code = code` |
| 105 | `self.subcode = subcode` | `self.notification_subcode = subcode` |
| 111 | `if (code, subcode) not in ...` | No change (uses parameter) |
| 152 | `self._str_code.get(self.code, ...)` | `self._str_code.get(self.notification_code, ...)` |
| 153 | `self._str_subcode.get((self.code, self.subcode), ...)` | `self._str_subcode.get((self.notification_code, self.notification_subcode), ...)` |
| 175 | `bytes([self.code, self.subcode])` | `bytes([self.notification_code, self.notification_subcode])` |

**Also:** Remove `# type: ignore[assignment,method-assign]` comments (no longer needed)

---

### 2️⃣ `src/exabgp/reactor/api/response/json.py`

| Line | Current | New |
|------|---------|-----|
| 241 | `'code': message.code,` | `'code': message.notification_code,` |
| 242 | `'subcode': message.subcode,` | `'subcode': message.notification_subcode,` |

**Note:** JSON key names stay `code`/`subcode` (external API compatibility)

---

### 3️⃣ `src/exabgp/reactor/api/response/text.py`

| Line | Current | New |
|------|---------|-----|
| 56 | `code {message.code} subcode {message.subcode}` | `code {message.notification_code} subcode {message.notification_subcode}` |

---

### 4️⃣ `src/exabgp/reactor/protocol.py`

| Line | Current | New |
|------|---------|-----|
| 277 | `Notify(notify.code, notify.subcode, ...)` | `Notify(notify.notification_code, notify.notification_subcode, ...)` |
| 367 | `Notify(notify.code, notify.subcode, ...)` | `Notify(notify.notification_code, notify.notification_subcode, ...)` |
| 612 | `notification.code},{notification.subcode}` | `notification.notification_code},{notification.notification_subcode}` |
| 622 | `notification.code},{notification.subcode}` | `notification.notification_code},{notification.notification_subcode}` |

---

### 5️⃣ `src/exabgp/reactor/peer.py`

| Line | Current | New |
|------|---------|-----|
| 1016 | `notify.code},{notify.subcode}` | `notify.notification_code},{notify.notification_subcode}` |
| 1040 | `notification.code},{notification.subcode}` | `notification.notification_code},{notification.notification_subcode}` |
| 1095 | `notify.code},{notify.subcode}` | `notify.notification_code},{notify.notification_subcode}` |
| 1119 | `notification.code},{notification.subcode}` | `notification.notification_code},{notification.notification_subcode}` |

---

### 6️⃣ `tests/unit/test_notification.py`

| Line | Current | New |
|------|---------|-----|
| 47 | `notify_exc.code` | `notify_exc.notification_code` |
| 48 | `notify_exc.subcode` | `notify_exc.notification_subcode` |

---

### 7️⃣ `tests/unit/test_notification_comprehensive.py`

**46 changes** - all `.code` → `.notification_code` and `.subcode` → `.notification_subcode`:

Lines: 159, 160, 168, 169, 181, 182, 192, 193, 209, 210, 218, 219, 237, 238, 253, 254, 266, 267, 282, 283, 380, 381, 391, 392, 476, 477, 487, 488, 500, 501, 512, 513, 529, 530, 606, 607, 615, 616, 679, 680, 699, 700, 712, 713, 722, 723, 741, 742

---

## ⚠️ API Compatibility Consideration

The JSON API output uses keys `code` and `subcode`:
```json
{"code": 6, "subcode": 2, ...}
```

**Decision needed:** Should the JSON keys remain `code`/`subcode` for backward compatibility, or change to `notification_code`/`notification_subcode`?

**Recommendation:** Keep JSON keys as `code`/`subcode` (external API stability). Only internal attribute names change.

---

## 🧪 Verification Commands

After each step:
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/
```

After all changes:
```bash
./qa/bin/test_everything
```

---

## 📝 Execution Order (per MANDATORY_REFACTORING_PROTOCOL)

1. **Step 1:** `notification.py` - Change definition + remove type ignores
2. **Step 2:** `reactor/api/response/json.py`
3. **Step 3:** `reactor/api/response/text.py`
4. **Step 4:** `reactor/protocol.py`
5. **Step 5:** `reactor/peer.py`
6. **Step 6:** `tests/unit/test_notification.py`
7. **Step 7:** `tests/unit/test_notification_comprehensive.py`
8. **Step 8:** Full test suite verification

**Each step:** Make change → Run tests → Paste output → Proceed only if pass

---

## 🔧 Type Ignore Removals

After rename, these `# type: ignore` comments can be removed from `notification.py`:

| Line | Comment |
|------|---------|
| 104 | `# type: ignore[assignment,method-assign]` |
| 152 | `# type: ignore[call-overload]` |
| 153 | `# type: ignore[arg-type]` |
| 175 | `# type: ignore[list-item]` |

---

## 📋 Commit Message (when requested)

```
Refactor: Rename Notification.code/subcode to notification_code/notification_subcode

Resolves name clash with Message.code() classmethod.
Removes associated type: ignore comments.
```
