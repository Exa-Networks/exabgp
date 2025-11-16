# Emoji Guide

**Purpose:** Terse communication with visual clarity.

---

## Core Emojis

| Category | Emoji | Meaning |
|----------|-------|---------|
| **Status** | ✅ ❌ ⏳ ⏸️ ⏭️ 🔄 | Success, Fail, Running, Paused, Skipped, Retry |
| **Priority** | 🔴 🟡 🟢 🔵 ⚪ | High, Medium, Low, Info, Neutral |
| **Quality** | ✨ 🐛 🔧 🚧 💥 ⚠️ 🚨 | New, Bug, Fix, WIP, Breaking, Warning, Critical |
| **Files** | 📁 📄 📝 ➕ ➖ 📋 | Dir, File, Edit, Add, Remove, List |
| **Code** | 🔍 🔬 🏗️ 🧪 📊 🎯 | Search, Analyze, Build, Test, Metrics, Target |
| **Git** | 📝 ⬆️ ⬇️ 🔀 ⏪ 🏷️ | Commit, Push, Pull, Merge, Revert, Tag |
| **Comm** | 💬 💭 💡 ❓ ⁉️ | Prompt, Note, Idea, Question, Confusion |

---

## Usage Rules

1. **Start lines with emoji:** `✅ Tests pass` NOT `Tests pass ✅`
2. **Be consistent:** Same emoji = same meaning
3. **Be terse:** `✅ Fixed` NOT `✅ I successfully fixed the issue`
4. **Use in lists:**
   ```
   🐛 parser.py:45 - type error
   🐛 tokeniser.py:67 - missing import
   ```

---

## Patterns

### Status Report
```
✅ Tests pass
❌ Build failed
⏳ Running...
```

### File List
```
📁 Modified:
  📄 src/parser.py
  📄 src/tokeniser.py
```

### Priority Tasks
```
🔴 Fix parser bug
🟡 Update docs
🟢 Refactor helpers
```

### Test Results
```
🧪 Tests:
  ✅ ruff: clean
  ✅ pytest: 1376 passed
  ❌ encoding: failed
```

---

## Examples

❌ **Verbose:** "I've run all the tests and I'm happy to report that everything passed!"
✅ **Terse:** `✅ All tests pass (ruff + pytest: 1376)`

❌ **Verbose:** "I've made changes to parser.py, tokeniser.py, and test_parser.py"
✅ **Terse:** `📁 Modified: parser.py, tokeniser.py, test_parser.py`

---

**Updated:** 2025-11-16
