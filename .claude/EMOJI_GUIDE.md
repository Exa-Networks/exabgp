# Emoji Communication Guide

**CRITICAL:** Use emojis systematically to convey information clearly and tersely.

---

## Purpose

Emojis enable terse communication while maintaining clarity. They replace verbose status descriptions with instant visual indicators.

**Benefit:** "✅ Tests pass" vs "I'm happy to report all tests passed successfully"

---

## Core Status Indicators

### Execution Status
- ✅ Success / Completed / Pass
- ❌ Failure / Error / Blocked
- ⏳ In progress / Running / Working
- ⏸️ Paused / Waiting for input
- ⏭️ Skipped / Not applicable
- 🔄 Retrying / Repeating

### Priority and Severity
- 🔴 HIGH priority / Critical / Urgent
- 🟡 MEDIUM priority / Warning / Attention needed
- 🟢 LOW priority / Info / Optional
- 🔵 Note / FYI / Informational
- ⚪ Neutral / Deferred

### Quality and State
- ✨ New / Enhanced / Improved
- 🐛 Bug / Issue / Problem
- 🔧 Fix / Repair / Maintenance
- 🚧 Work in progress / Unstable
- 💥 Breaking change / Destructive
- ⚠️ Warning / Caution
- 🚨 Alert / Critical warning

---

## File and Code Operations

### File Operations
- 📁 Directory / Folder reference
- 📄 File / Document
- 📝 Edit / Modified / Changed
- ➕ Added / Created
- ➖ Removed / Deleted
- 📋 List / Listing / Summary

### Code Operations
- 🔍 Search / Find / Inspect
- 🔬 Analyze / Deep inspection
- 🏗️ Build / Compile / Generate
- 🧪 Test / Testing
- 📊 Metrics / Statistics / Data
- 🎯 Target / Focus / Specific item

---

## Git Operations

- 📝 Commit
- ⬆️ Push
- ⬇️ Pull / Fetch
- 🔀 Merge / Branch
- ⏪ Revert / Rollback
- 🏷️ Tag / Release

---

## Session and Context

### Session Management
- 🔷 Current / Active instance
- ◽ Other active instance
- ⬜ Idle instance
- 💤 Sleeping / Suspended

### Communication
- 💬 User prompt / Question
- 💭 Thinking / Internal note
- 💡 Suggestion / Idea / Tip
- ❓ Question / Clarification needed
- ⁉️ Confusion / Something wrong

---

## Structured Output Patterns

### Status Report
```
✅ Tests pass
❌ Build failed
⏳ Linting...
```

### File Lists
```
📁 Modified files:
  📄 src/parser.py
  📄 src/tokeniser.py
  📄 tests/test_parser.py
```

### Priority Tasks
```
📊 Backlog:
  🔴 HIGH: Fix parser bug
  🟡 MEDIUM: Update docs
  🟢 LOW: Refactor helpers
```

### Test Results
```
🧪 Test Results:
  ✅ Unit tests: 1376 passed
  ✅ Linting: all checks passed
  ❌ Encoding test E: IPv6 address mismatch
```

### Multi-step Process
```
⏳ Build process:
  ✅ Compile source
  ✅ Run tests
  ⏳ Generate docs...
```

---

## Session Status Format

**Standard session header:**
```
📋 SESSION STATUS

🔷 CURRENT INSTANCE: 2025-11-04-1437
   Status: Active
   Working on: Parser refactoring

◽ OTHER INSTANCES:
   • 2025-11-03-1256 - Idle - Documentation work
   • 2025-11-02-1552 - Idle - Type annotations

📊 BACKLOG:
  🔴 HIGH: Fix encoding bug (urgent)
  🟡 MEDIUM: Update CLAUDE.md
  🟢 LOW: Refactor tests

📁 FILES MODIFIED:
  📄 src/parser.py
  📄 src/tokeniser.py

💬 What's next?
```

---

## Usage Guidelines

### Rule 1: Consistency
Always use the same emoji for the same meaning across all communications.

### Rule 2: Start Lines with Emoji
```
✅ GOOD: "✅ Tests pass"
❌ BAD:  "Tests pass ✅"
```

### Rule 3: Combine with Terse Text
```
✅ GOOD: "✅ Fixed"
❌ BAD:  "✅ I've successfully fixed the issue"
```

### Rule 4: Use in Lists
```
📊 Issues found:
  🐛 parser.py:45 - type error
  🐛 tokeniser.py:67 - missing import
  ⚠️ config.py:23 - deprecated syntax
```

### Rule 5: Hierarchy with Indentation
```
📁 src/
  📄 parser.py
  📄 tokeniser.py
  📁 tests/
    📄 test_parser.py
```

---

## Context-Specific Patterns

### Testing
```
🧪 Running test suite:
  ✅ ruff format src
  ✅ ruff check src
  ✅ pytest (1376 passed)
  ⏳ functional tests...
```

### Git Operations
```
📝 Commit changes:
  📄 src/parser.py - Fix type annotations
  📄 tests/test_parser.py - Add new tests

⬆️ Ready to push? (y/n)
```

### Issue Analysis
```
🔍 Analyzing parser.py:

🐛 Issues found:
  1. Line 45: Union[int, str] required
  2. Line 67: Missing TYPE_CHECKING import

🔧 Fix approach:
  1. Add typing imports
  2. Update signatures
  3. Run tests
```

### Build Process
```
🏗️ Building:
  ✅ Format code
  ✅ Check types
  ✅ Run tests
  ⏳ Package binary...
```

---

## Quick Reference Legend

When output is complex, include a legend:

```
📋 Legend:
  ✅ Complete  ❌ Failed  ⏳ Running
  🔴 High  🟡 Medium  🟢 Low
  📁 Directory  📄 File
```

---

## Anti-Patterns (DON'T)

### ❌ Don't Overuse
```
BAD: "✅ I've ✨ successfully 🔧 fixed 🐛 the issue ✅"
GOOD: "✅ Fixed"
```

### ❌ Don't Use Ambiguous Emoji
```
BAD: "😀 Tests pass!"  (emotion, not status)
GOOD: "✅ Tests pass"
```

### ❌ Don't Mix Meanings
```
BAD: Using ✅ for both "completed" and "correct"
GOOD: ✅ for completed, 🔵 for informational note
```

### ❌ Don't Use Decorative Emoji
```
BAD: "🎉🎊 All done! 🎈"
GOOD: "✅ Done"
```

---

## Examples: Before and After

### Example 1: Test Results
```
❌ VERBOSE:
"I've run all the tests and I'm happy to report that everything
passed! The linting checks came back clean, and all 1376 unit
tests passed successfully."

✅ TERSE WITH EMOJI:
"✅ All tests pass
  ✅ ruff: clean
  ✅ pytest: 1376 passed"
```

### Example 2: File Changes
```
❌ VERBOSE:
"I've made changes to the following files: parser.py, tokeniser.py,
and test_parser.py"

✅ TERSE WITH EMOJI:
"📁 Modified:
  📄 parser.py
  📄 tokeniser.py
  📄 test_parser.py"
```

### Example 3: Multi-Step Task
```
❌ VERBOSE:
"I'm now working on the first step. After that I'll move to the
second step, and finally complete the third step."

✅ TERSE WITH EMOJI:
"⏳ Step 1: Format code
⏸️ Step 2: Run tests (waiting)
⏸️ Step 3: Build package (waiting)"

[After step 1 completes:]

"✅ Step 1: Format code
⏳ Step 2: Run tests
⏸️ Step 3: Build package (waiting)"
```

### Example 4: Problem Report
```
❌ VERBOSE:
"Unfortunately, I encountered an error. The parser is missing a
type annotation on line 45, and there's also a missing import
on line 67."

✅ TERSE WITH EMOJI:
"❌ Errors:
  🐛 parser.py:45 - missing type annotation
  🐛 parser.py:67 - missing import"
```

---

## Implementation Checklist

When creating structured output:

- [ ] Section headers use appropriate emoji (📋🎯📊🔍)
- [ ] All list items have status indicators (✅⏳❌)
- [ ] Priority levels marked (🔴🟡🟢)
- [ ] File references marked (📁📄)
- [ ] User prompts marked (💬💡)
- [ ] Consistent emoji meaning throughout
- [ ] No decorative/emotional emoji
- [ ] Legend included if output is complex

---

## Maintenance

**Review quarterly:**
- Are emojis improving readability?
- Are new emoji needs emerging?
- Is usage consistent across sessions?
- User feedback on effectiveness?

**When adding new emojis:**
- Update this guide first
- Ensure no conflicts with existing meanings
- Test readability in terminal
- Document in appropriate section

---

## Terminal Compatibility

**Note:** All emojis in this guide are chosen for broad terminal support. They should render correctly in:
- Modern terminal emulators (iTerm2, Terminal.app, Windows Terminal)
- VS Code integrated terminal
- Most Linux terminal emulators

If rendering issues occur, fall back to ASCII alternatives:
- ✅ → [PASS]
- ❌ → [FAIL]
- ⏳ → [RUNNING]

---

**Last Updated:** 2025-11-14
**Maintainer:** Project team
**Version:** 1.0

---

**STARTUP PROTOCOL:** When reading this file at session start: output "✅ EMOJI_GUIDE.md" only. NO summaries. NO thinking. Knowledge retained in context.
