---
description: Review and improve documentation (docstrings and comments) in a file
---

# Documentation Review Command

**Instructions:** Review and improve all documentation in the specified file(s) following ExaBGP documentation standards.

---

## Step 1: Read Documentation Standards

📖 Read `.claude/DOCUMENTATION_WRITING_GUIDE.md` to understand:
- Google-style docstring format
- What to document (public APIs, complex functions)
- ExaBGP-specific terminology and conventions
- Common mistakes to avoid

---

## Step 2: Analyze Current Documentation

For the specified file, identify:

**Missing Documentation:**
- [ ] Classes without docstrings
- [ ] Public methods without docstrings
- [ ] Complex private methods (>20 lines) without docs
- [ ] Module docstring missing or inadequate

**Inadequate Documentation:**
- [ ] Vague summaries ("Does the thing")
- [ ] Missing Args/Returns/Raises sections
- [ ] Type information repeated from signature
- [ ] Implementation details instead of purpose
- [ ] Outdated information

**Good Documentation:**
- [ ] Note what's already well-documented (don't change)
- [ ] Identify patterns to replicate

---

## Step 3: Understand Context Before Writing

For each undocumented/poorly documented item:

1. **Read the code** - Understand what it does
2. **Check usage** - Grep for where it's called
3. **Check tests** - Look at test files for usage examples
4. **Check RFCs** - Look for RFC references in comments
5. **Check related code** - See how similar functions are documented

**Do NOT** write generic documentation without understanding purpose.

---

## Step 4: Improve Documentation

### Module Docstring (if missing/inadequate)

Add at top of file:
```python
"""Brief description of module purpose.

Longer description explaining what this module provides, key classes/functions,
and relevant RFCs. Explain how it fits in ExaBGP architecture.

Key classes:
    ClassName: What it does
    AnotherClass: What it does

Related RFCs:
    RFC XXXX - Description
"""
```

### Class Docstrings

For each class without adequate docstring:
```python
class ClassName:
    """One-line summary of class responsibility.

    Longer description of purpose, behavior, and usage. Explain
    how it fits in the system architecture.

    Attributes:
        attr_name: Description of important class/instance attributes.

    Example:
        >>> obj = ClassName(param)
        >>> obj.method()
        result
    """
```

### Method Docstrings

For each method without adequate docstring:
```python
def method_name(self, param1: Type1, param2: Type2) -> ReturnType:
    """One-line summary in imperative mood.

    Optional longer description for complex methods. Explain WHY this
    method exists and important behavior/edge cases.

    Args:
        param1: Purpose and meaning (not just type).
        param2: Purpose and meaning. Explain valid values/constraints.

    Returns:
        Description of return value. Explain structure for complex types.

    Raises:
        ExceptionType: When and why this is raised.

    Note:
        Important notes about performance, thread safety, or usage.
    """
```

### Inline Comments

Improve inline comments:
- **Remove obvious comments** - `x = x + 1  # increment x` → remove
- **Keep complex logic comments** - Explain WHY, not WHAT
- **Add RFC references** - Link to spec sections
- **Explain non-obvious decisions** - "Using MD5 for speed, not security"

---

## Step 5: Apply ExaBGP Standards

Ensure documentation follows ExaBGP conventions:

### Use Correct Terminology

| Instead of... | Use... |
|---------------|--------|
| "message" | "BGP UPDATE message" (be specific) |
| "data" | "wire format bytes" or "packed bytes" |
| "send" | "transmit to peer" or "encode to wire format" |
| "route announcement" | "NLRI" |
| "deleted routes" | "withdrawn routes" |

### Include Domain Context

For BGP protocol code:
- Include RFC references with section numbers
- Mention AFI/SAFI codes where relevant
- Explain wire format structure
- Note which BGP error codes are sent

For configuration parsing:
- Show example config syntax
- List required vs optional fields
- Explain validation performed

For reactor code:
- Mention event loop context
- Note performance constraints (non-blocking)
- Explain error handling strategy

### Handle Unused Parameters

Many ExaBGP methods have unused `negotiated` parameters (stable API):
```python
def pack(self, negotiated: Negotiated) -> bytes:
    """Serialize route to wire format.

    Args:
        negotiated: BGP capabilities (unused for this NLRI type, but
            required by pack() interface for consistency).
```

**Always explain** unused params as "(unused for X, but required for Y)".

---

## Step 6: Quality Check

Before submitting changes, verify:

**Completeness:**
- [ ] All public classes have docstrings
- [ ] All public methods have docstrings
- [ ] Complex private methods (>20 lines) have docstrings
- [ ] Module has docstring

**Quality:**
- [ ] Summary lines use imperative mood with period
- [ ] Args section for all parameters
- [ ] Returns section for non-None returns
- [ ] Raises section for exceptions
- [ ] No type information repeated from signature
- [ ] No obvious statements
- [ ] No implementation details in docstrings
- [ ] Consistent ExaBGP terminology

**Correctness:**
- [ ] Documentation matches actual behavior
- [ ] Parameter names match signature
- [ ] Exceptions listed are actually raised
- [ ] RFC references are correct

---

## Step 7: Present Changes

Show the user:

1. **Summary of changes:**
   ```
   📊 Documentation improvements for <filename>:
   - Added module docstring
   - Added docstrings to X classes
   - Added docstrings to Y methods
   - Improved Z existing docstrings
   - Removed N obvious inline comments
   ```

2. **Key improvements made:**
   - List most significant additions (complex classes/methods)
   - Note any assumptions or questions

3. **Coverage stats:**
   ```
   Before: X% classes, Y% methods documented
   After:  A% classes, B% methods documented
   ```

---

## Special Cases

### When Documentation is Already Good

If class/method already has good documentation:
- **Don't change it** just to reword
- Only fix if actually incorrect or inadequate
- Note in summary: "X items already well-documented"

### When Behavior is Unclear

If you cannot determine what code does:
- Add placeholder: `# TODO: Document - unclear purpose`
- Add to summary: "3 items need clarification"
- Ask user for context

### When Code Looks Wrong

If code appears to have bugs while reviewing:
- Note in summary: "Potential issues found (not fixed):"
- Don't fix bugs during documentation review
- Stay focused on documentation task

---

## Example Usage

User runs:
```
/review-docs src/exabgp/reactor/peer.py
```

You should:
1. Read DOCUMENTATION_WRITING_GUIDE.md
2. Analyze peer.py for missing/inadequate docs
3. Add module docstring if missing
4. Add class docstrings (Peer class, etc.)
5. Add method docstrings (prioritize public methods)
6. Improve inline comments
7. Use Edit tool to make changes
8. Present summary of improvements

---

## Output Format

After making changes, show:

```
✅ Documentation Review Complete: src/exabgp/reactor/peer.py

📊 Changes Made:
- Added module docstring explaining FSM implementation
- Added Peer class docstring
- Added docstrings to 15 public methods
- Improved 8 existing docstrings (added Args/Returns/Raises)
- Removed 12 obvious inline comments
- Added RFC 4271 references

📈 Coverage:
Before: 0% classes (0/5), 42% methods (21/50)
After:  100% classes (5/5), 84% methods (42/50)

🔍 Items Needing Clarification:
- _handle_notification() behavior when code=6 (unclear from code)
- _respawn_logic exact timing (no comments)

✨ Key Improvements:
1. Peer._main() - Added comprehensive docstring explaining FSM states
2. Peer._establish() - Added Raises section with all BGP error codes
3. Peer.run() - Added Note about generator vs async modes
```

---

## Remember

- **Quality over quantity** - Better to document 10 things well than 50 poorly
- **Context matters** - Understand before writing
- **Follow the guide** - .claude/DOCUMENTATION_WRITING_GUIDE.md is your reference
- **Be consistent** - Match existing good documentation style
- **Stay focused** - This is documentation review, not code refactoring

---

**Version:** 1.0
**Last Updated:** 2025-12-01
