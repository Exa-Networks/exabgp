# Testing Before Refactoring Protocol

**MANDATORY:** Read this before ANY code modification. This is not optional.

---

## Core Principle

**Never refactor code without first ensuring adequate test coverage.**

Refactoring without tests is like performing surgery without monitoring vital signs - you won't know if you've killed the patient until it's too late.

---

## The Protocol: Test-Verify-Refactor-Verify

### Step 1: Identify What You're Changing

Before touching any code, answer:
- What file(s) will I modify?
- What functions/classes/methods will change?
- What is the public interface (inputs → outputs)?

### Step 2: Find Existing Tests

```bash
# Search for test files
ls tests/unit/test_*.py | xargs grep -l "ClassName\|function_name"

# Search for test functions
grep -rn "def test_.*classname\|def test_.*function" tests/

# Check functional tests
./qa/bin/functional encoding --list | grep -i "feature_name"
```

**Ask yourself:**
- Do tests exist for this code?
- Do they cover the public interface?
- Do they cover edge cases?
- What is the current pass/fail status?

### Step 3: Run Existing Tests FIRST

```bash
# Run specific tests
env exabgp_log_enable=false uv run pytest tests/unit/test_<name>.py -v

# Run and record baseline
env exabgp_log_enable=false uv run pytest tests/unit/test_<name>.py -v 2>&1 | tee /tmp/baseline.txt
```

**Document the baseline:**
- How many tests pass?
- How many tests exist?
- Any skipped tests? Why?

### Step 4: Assess Test Coverage

**If tests exist but coverage is poor:**
- Add tests for uncovered paths BEFORE refactoring
- Each public method needs at least one test
- Each branch/condition needs coverage

**If no tests exist:**
- STOP. Write tests first.
- Tests document current behavior (even if buggy)
- This protects against unintended changes

### Step 5: Write Missing Tests BEFORE Refactoring

```python
# Test template for NLRI classes
class TestClassName:
    def test_create_basic(self):
        """Test basic creation with typical values."""

    def test_pack_unpack_roundtrip(self):
        """Pack then unpack preserves all data."""

    def test_pack_format(self):
        """Verify wire format structure."""

    def test_unpack_known_data(self):
        """Unpack known wire bytes produces expected values."""

    def test_json_output(self):
        """JSON serialization format."""

    def test_str_representation(self):
        """String representation."""

    def test_edge_cases(self):
        """Boundary conditions, empty values, max values."""
```

### Step 6: Verify New Tests Pass

```bash
# New tests must pass with CURRENT code
env exabgp_log_enable=false uv run pytest tests/unit/test_<name>.py -v
```

If new tests fail with current code, you've found a bug - document it, decide whether to fix it as part of this work or separately.

### Step 7: NOW Refactor

Only after steps 1-6 are complete, begin refactoring.

Make small, incremental changes. Run tests after each change:
```bash
env exabgp_log_enable=false uv run pytest tests/unit/test_<name>.py -v
```

### Step 8: Verify All Tests Still Pass

```bash
# Full test suite
./qa/bin/test_everything
```

Compare with baseline from Step 3. Same tests should pass.

---

## Checklist Template

Copy this for each refactoring task:

```markdown
## Pre-Refactoring Checklist: [Feature/File Name]

### 1. Scope
- [ ] Files to modify: ___
- [ ] Functions/classes affected: ___
- [ ] Public interface documented: ___

### 2. Existing Tests
- [ ] Test files found: ___
- [ ] Test count: ___
- [ ] Baseline recorded: ___ passing / ___ total

### 3. Coverage Assessment
- [ ] All public methods have tests: Yes/No
- [ ] Edge cases covered: Yes/No
- [ ] Missing coverage: ___

### 4. Tests Added (if needed)
- [ ] test___ added
- [ ] test___ added
- [ ] New tests pass with current code: Yes/No

### 5. Ready to Refactor
- [ ] All prerequisites complete
- [ ] Baseline established
- [ ] Incremental approach planned

### 6. Post-Refactoring
- [ ] All original tests pass
- [ ] All new tests pass
- [ ] ./qa/bin/test_everything passes
```

---

## Red Flags - STOP If You See These

1. **No tests exist** → Write tests first
2. **Tests are failing** → Fix tests or code first, don't add more breakage
3. **"I'll add tests later"** → No. Tests come BEFORE refactoring.
4. **"It's a simple change"** → Simple changes break things. Test anyway.
5. **"Tests are slow"** → Run them anyway. Faster than debugging production.

---

## Why This Matters

| Without Tests First | With Tests First |
|---------------------|------------------|
| "It works on my machine" | Reproducible verification |
| Silent behavior changes | Immediate regression detection |
| Hours debugging | Minutes to identify issues |
| Fear of refactoring | Confidence to improve |
| Technical debt grows | Technical debt shrinks |

---

## Integration with Existing Protocols

This protocol integrates with:
- `ESSENTIAL_PROTOCOLS.md` - Verification before claiming
- `MANDATORY_REFACTORING_PROTOCOL.md` - Safe refactoring practices
- `CI_TESTING.md` - Full test suite requirements

**The order is:**
1. Read ESSENTIAL_PROTOCOLS.md (always)
2. Read TESTING_BEFORE_REFACTORING_PROTOCOL.md (this file)
3. Execute the checklist
4. Then proceed with refactoring

---

## Quick Reference

```bash
# Find tests for a file
grep -rn "test.*ClassName" tests/

# Run specific tests with verbose output
env exabgp_log_enable=false uv run pytest tests/unit/test_X.py -v

# Run tests matching a pattern
env exabgp_log_enable=false uv run pytest tests/unit/ -k "vpls" -v

# Full suite (required before declaring success)
./qa/bin/test_everything
```

---

**Remember:** The best time to write tests is before you need them. The second best time is now.
