# PR #[NUMBER]: [Title]

**Part of:** Async/Await Migration (See `ASYNC_MIGRATION_PLAN.md`)
**Phase:** [1/2/3/4/5]
**Risk Level:** [Low/Medium/High]
**Estimated Time:** [X hours]

---

## Summary

[Brief 2-3 sentence description of what this PR does]

---

## Generators Converted

### Files Modified
- `path/to/file.py` - [N generators → async def]

### Functions Converted
- [ ] `function_name_1()` → `async def function_name_1()` (line XX)
- [ ] `function_name_2()` → `async def function_name_2()` (line YY)
- [ ] `function_name_3()` → `async def function_name_3()` (line ZZ)

**Total:** [N] generator functions converted to async/await

---

## Changes Made

### Code Changes
- Change 1: [Description]
- Change 2: [Description]
- Change 3: [Description]

### Pattern Used
[Describe the conversion pattern - reference Appendix B in migration plan if applicable]

```python
# BEFORE
def old_function():
    yield result

# AFTER
async def old_function():
    return await async_result()
```

---

## Testing

### Test Results
```bash
# Unit tests
PYTHONPATH=src python -m pytest tests/unit/ -v
Result: [PASS/FAIL] - [X/Y tests passed]

# Fuzz tests
PYTHONPATH=src python -m pytest tests/fuzz/ -v
Result: [PASS/FAIL] - [X/Y tests passed]

# Full test suite
PYTHONPATH=src python -m pytest tests/ -v --cov=src/exabgp
Result: [PASS/FAIL] - Coverage: [X%]
```

### New Tests Added
- [ ] `test_file.py::test_name_1` - Tests [what]
- [ ] `test_file.py::test_name_2` - Tests [what]

### Manual Testing
- [ ] Tested [scenario 1]
- [ ] Tested [scenario 2]
- [ ] Verified [behavior]

---

## Backward Compatibility

- [x] Existing generator-based code still works
- [x] No breaking changes to external API
- [x] Stable test files (`test_connection_advanced.py`, etc.) remain unmodified

---

## Dependencies

### Requires (must be merged first)
- [ ] PR #[X]: [Title]

### Blocks (must merge before)
- [ ] PR #[Y]: [Title]
- [ ] PR #[Z]: [Title]

---

## Risk Assessment

**Risk Level:** [Low/Medium/High]

**Justification:**
[Why this risk level? What could go wrong?]

**Mitigation:**
- Mitigation 1
- Mitigation 2

---

## Rollback Plan

If this PR causes issues:

1. **Immediate Rollback:**
   ```bash
   git revert [commit-hash]
   ```

2. **Feature Flag:** [If applicable]
   - Set `ENABLE_ASYNC_MODE=false` in config

3. **Backward Compatibility:**
   - ASYNC class still supports generators
   - Can toggle mode via [mechanism]

---

## Performance Impact

### Benchmarks (if available)
```
Before: [metric]
After:  [metric]
Change: [±X%]
```

### Expected Impact
- [ ] No performance change expected
- [ ] Performance improvement expected: [describe]
- [ ] Minor performance regression acceptable: [justify]

---

## Documentation

### Updated Documentation
- [ ] Code docstrings updated
- [ ] MIGRATION_PROGRESS.md updated
- [ ] README.md updated (if needed)
- [ ] Migration plan notes added

### Code Comments
- [ ] Added comments explaining async conversion
- [ ] Documented any tricky parts
- [ ] Removed obsolete comments

---

## Checklist

### Before Creating PR
- [ ] Code follows project style guide
- [ ] All tests pass locally
- [ ] Coverage hasn't decreased
- [ ] Commit message follows format
- [ ] Branch name follows convention: `async-pr-[XX]-[description]`

### Code Quality
- [ ] No unnecessary changes (stay focused on async conversion)
- [ ] Error handling preserved or improved
- [ ] Logging statements preserved
- [ ] No debug code left in

### Testing
- [ ] Unit tests pass: `PYTHONPATH=src python -m pytest tests/unit/ -v`
- [ ] Fuzz tests pass: `PYTHONPATH=src python -m pytest tests/fuzz/ -v`
- [ ] Integration tests pass (if applicable)
- [ ] Manual testing completed

### Review Ready
- [ ] Self-reviewed all changes
- [ ] Tested rollback procedure
- [ ] PR description complete
- [ ] Ready for peer review

---

## Review Notes

### Key Areas to Review
1. [Area 1]: [Why it needs attention]
2. [Area 2]: [Why it needs attention]

### Questions for Reviewers
1. [Question 1]?
2. [Question 2]?

---

## Post-Merge Tasks

After this PR merges:

- [ ] Update MIGRATION_PROGRESS.md stats
- [ ] Close related issues (if any)
- [ ] Start next PR: #[X]
- [ ] Tag release (if milestone reached)

---

## Additional Notes

[Any other context, decisions made, issues encountered, etc.]

---

## Metrics

- **Generators Converted:** [N] / 150 total
- **Overall Progress:** [X]% complete
- **PRs Merged:** [M] / 28 total
- **Phase Progress:** [X] / [Y] PRs in this phase

---

## Screenshots / Output (if applicable)

[Add any relevant terminal output, logs, or screenshots]

---

**Ready for Review:** [Yes/No]
**Merge After:** [Date/PR number/Condition]
