# ExaBGP Documentation Writing Guide

**Purpose:** Instructions for AI agents (Sonnet/Haiku) to add high-quality docstrings to ExaBGP codebase.

**Goal:** Achieve 80%+ class/method docstring coverage with consistent, useful documentation.

---

## 🎯 Core Principles

1. **Write for the reader** - Assume reader knows Python but not ExaBGP internals
2. **Focus on WHY, not WHAT** - Code shows what; docs explain why and context
3. **Be concise** - 1-3 sentences for simple functions, more for complex ones
4. **Use present tense** - "Returns the value" not "Will return the value"
5. **Follow Google style** - We use Google-style docstrings (not NumPy/Sphinx)

---

## 📝 Docstring Format (Google Style)

### Basic Structure

```python
def function_name(param1: type1, param2: type2) -> return_type:
    """One-line summary (imperative mood, ends with period).

    Optional longer description providing context, explaining the purpose,
    edge cases, or important behavior. Use multiple paragraphs if needed.

    Args:
        param1: Description of param1 (no type needed, already in signature).
        param2: Description of param2. Can be multi-line if needed,
            indent continuation lines.

    Returns:
        Description of return value. Explain structure for complex types.

    Raises:
        ValueError: When and why this exception is raised.
        KeyError: Another exception condition.

    Note:
        Optional notes about edge cases, performance, or usage.

    Example:
        >>> function_name(10, "test")
        42
    """
    pass
```

### Quick Reference

| Element | When to Include | Format |
|---------|----------------|---------|
| Summary | **Always** | One line, imperative mood, period at end |
| Description | Complex functions | After blank line, multiple paragraphs OK |
| Args | Functions with parameters | `param_name: Description` |
| Returns | Functions that return values | Description of return value |
| Raises | Functions that raise exceptions | `ExceptionType: Condition` |
| Note | Edge cases, warnings | Optional section |
| Example | Public APIs, complex usage | Doctest format optional |

---

## 🏗️ What to Document

### Priority 1: PUBLIC APIs (Must Document)

**Classes:**
- All public classes (not starting with `_`)
- Purpose and responsibility
- Key attributes/properties
- Usage examples for complex classes

**Public Methods:**
- All methods without leading `_`
- What they do and why they exist
- Parameters and return values
- Exceptions they raise

**Module-Level:**
- Top of file docstring explaining module purpose
- What the module provides
- Key classes/functions it exports

### Priority 2: INTERNAL APIs (Should Document)

**Private Methods:**
- Methods starting with `_`
- Brief one-liner is usually sufficient
- Explain purpose if non-obvious

**Complex Functions:**
- Any function >20 lines
- Any function with >3 parameters
- Any function with complex logic

### Priority 3: OBVIOUS CODE (Optional)

**Skip or Keep Brief:**
- Simple getters/setters
- `__init__` if only assigns parameters
- One-line utility functions
- Magic methods with standard behavior

---

## ✍️ Writing Style Guide

### Summary Line (First Line)

✅ **GOOD:**
```python
def pack(self, negotiated: Negotiated) -> bytes:
    """Serialize the BGP UPDATE message to wire format.
```

❌ **BAD:**
```python
def pack(self, negotiated: Negotiated) -> bytes:
    """This function packs the message.  # Too vague
    """This method will pack...  # Future tense
    """Packs the message  # Missing period
```

**Rules:**
- Start with verb in imperative mood (Calculate, Parse, Send, Create)
- Be specific about what it does
- Keep under 80 characters if possible
- Always end with period

### Args Section

✅ **GOOD:**
```python
Args:
    negotiated: The negotiated capabilities from BGP OPEN exchange,
        used to determine which optional attributes to include.
    direction: Direction of message flow (IN or OUT). Affects
        attribute ordering and path attribute processing.
```

❌ **BAD:**
```python
Args:
    negotiated: Negotiated object  # Too vague
    direction: The direction  # Doesn't explain what/why
    data (bytes): The data  # Don't repeat type from signature
```

**Rules:**
- Explain purpose and usage, not just type
- Don't repeat information from type hints
- Explain what values are valid (if constrained)
- Multi-line descriptions indent 4 spaces

### Returns Section

✅ **GOOD:**
```python
Returns:
    Packed bytes in BGP wire format, starting with marker (16 x 0xFF),
    followed by length, type, and message-specific data.
```

❌ **BAD:**
```python
Returns:
    bytes  # Already in signature
    The return value  # Too vague
```

**Rules:**
- Describe structure/format for complex types
- Explain meaning, not just type
- For `None` returns, state when/why
- For tuples, describe each element

### Raises Section

✅ **GOOD:**
```python
Raises:
    NotificationSent: When BGP error condition detected. The peer
        will be sent a NOTIFICATION and connection torn down.
    ValueError: If message length exceeds 4096 bytes maximum.
```

❌ **BAD:**
```python
Raises:
    Exception: When error occurs  # Too vague
    NotificationSent  # Missing description
```

**Rules:**
- List exception type and trigger condition
- Explain consequences (connection closed, retry, etc.)
- Only document exceptions raised by THIS function
- Don't document exceptions that propagate unchanged

---

## 📚 ExaBGP-Specific Guidelines

### BGP Protocol Documentation

When documenting BGP message handling:

```python
def unpack_nlri(cls, afi: AFI, safi: SAFI, data: bytes) -> 'NLRI':
    """Parse NLRI from BGP UPDATE message.

    Extracts Network Layer Reachability Information from the wire format
    according to RFC 4271 and address-family-specific extensions.

    Args:
        afi: Address Family Identifier (IPv4=1, IPv6=2, BGP-LS=16388).
        safi: Subsequent Address Family Identifier (unicast=1, multicast=2).
        data: Raw bytes from UPDATE message, starting at NLRI offset.

    Returns:
        Parsed NLRI instance with prefix, length, and path_info populated.

    Raises:
        Notification: When NLRI format is invalid per RFC 4271 Section 6.3.
            Sends UPDATE Message Error (code 3) to peer.
    """
```

**Include:**
- RFC references (RFC 4271 Section 6.3)
- AFI/SAFI codes with common values
- Wire format details (byte offsets, structure)
- BGP error codes if NOTIFICATION sent

### Configuration Parsing

When documenting parsers:

```python
def _parse_neighbor(self, scope: ParsedSection) -> None:
    """Parse 'neighbor' configuration block.

    Processes neighbor definition including IP, AS number, capabilities,
    timers, and session parameters. Creates Neighbor instance and registers
    with configuration.

    Args:
        scope: Current parser scope containing tokenized configuration lines.
            Assumes scope.location points to 'neighbor' keyword.

    Raises:
        ConfigurationError: When required fields missing (IP, AS) or
            invalid values provided (AS out of range, invalid IP format).
    """
```

**Include:**
- Expected config file syntax
- Required vs optional parameters
- Validation performed
- State changes (what gets created/registered)

### Reactor/Event Loop

When documenting reactor code:

```python
def _async_reader_callback(self, process_name: str, fd: int) -> None:
    """Handle async read events from API process stdout/stderr.

    Called by event loop when data available on process file descriptor.
    Reads available data, buffers partial lines, and dispatches complete
    lines to message handlers.

    Args:
        process_name: Name of API process (from config 'run' directive).
        fd: File descriptor number for stdout or stderr pipe.

    Note:
        This is called in reactor event loop. Keep processing minimal.
        Do NOT perform blocking operations or raise exceptions.
        Connection errors are handled via _handle_problem().
    """
```

**Include:**
- Event/callback context (when called)
- Performance notes (non-blocking, minimal work)
- Error handling strategy
- Thread/concurrency context

### Unused Parameters

ExaBGP has MANY methods with unused `negotiated` parameters (stable API):

```python
def pack(self, negotiated: Negotiated) -> bytes:
    """Serialize route to BGP UPDATE format.

    Args:
        negotiated: BGP capabilities (unused for this NLRI type, but
            required by pack() interface for consistency).

    Returns:
        Packed NLRI bytes ready for inclusion in UPDATE message.
    """
```

**Rules:**
- Document unused params as "(unused for...)"
- Explain WHY it exists (interface consistency, future use)
- Don't apologize or say it's bad design

---

## 🔧 Practical Examples

### Example 1: Simple Function

**Before:**
```python
def calculate_hash(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()
```

**After:**
```python
def calculate_hash(data: bytes) -> str:
    """Calculate MD5 hash for message deduplication.

    Used to detect duplicate BGP UPDATEs from same peer. Not for security.

    Args:
        data: Raw message bytes to hash.

    Returns:
        32-character hexadecimal MD5 digest.
    """
    return hashlib.md5(data).hexdigest()
```

### Example 2: Complex Class

**Before:**
```python
class Attributes:
    cache: ClassVar[dict[str, Attributes]] = {}

    def __init__(self):
        self._attributes = {}
```

**After:**
```python
class Attributes:
    """Collection of BGP path attributes for a route.

    Represents all attributes in a BGP UPDATE message (ORIGIN, AS_PATH,
    NEXT_HOP, MED, etc.). Attributes are cached globally to reduce memory
    when multiple routes share identical attributes.

    Attributes are immutable after creation to enable safe caching.

    Attributes:
        cache: Class-level cache of Attributes instances keyed by wire format.
            Shared across all routes to reduce memory usage.
    """

    cache: ClassVar[dict[str, Attributes]] = {}

    def __init__(self):
        """Initialize empty attribute collection.

        Note:
            Prefer using Attributes.unpack() or cached constructors over
            direct instantiation.
        """
        self._attributes = {}
```

### Example 3: State Machine Method

**Before:**
```python
def _read_open(self):
    # ... 50 lines of code ...
```

**After:**
```python
def _read_open(self):
    """Read and validate BGP OPEN message from peer.

    Part of BGP FSM state transition from OpenSent to OpenConfirm.
    Validates peer's AS number, BGP identifier, hold time, and capabilities.
    Negotiates final capability set used for session.

    Raises:
        NotificationSent: When OPEN validation fails (RFC 4271 Section 6.2):
            - Unsupported version (code 2, subcode 1)
            - Bad peer AS (code 2, subcode 2)
            - Bad BGP identifier (code 2, subcode 3)
            - Unsupported capability (code 2, subcode 7)

    Note:
        This is a generator function. Yields to reactor between I/O operations.
        Use _read_open_async() for async/await reactor mode.
    """
    # ... 50 lines of code ...
```

---

## 🎨 Module-Level Documentation

Every file should start with module docstring:

```python
"""BGP UPDATE message parsing and generation.

This module handles BGP UPDATE messages (RFC 4271 Section 4.3), which
advertise and withdraw routes. UPDATE messages contain:
  - Withdrawn routes (prefixes being removed)
  - Path attributes (ORIGIN, AS_PATH, NEXT_HOP, etc.)
  - NLRI (Network Layer Reachability Information - new routes)

Key classes:
    Update: The UPDATE message itself
    Attributes: Collection of path attributes
    NLRI: Route prefix and associated data

The Update class handles both traditional UPDATE (RFC 4271) and
MP-BGP UPDATE (RFC 4760) with multiple address families.
"""

from __future__ import annotations
# ... rest of imports
```

**Include:**
- What the module provides
- Key RFCs implemented
- Main classes/functions
- Related modules

---

## ⚠️ Common Mistakes to Avoid

### ❌ Don't Repeat Type Information

**BAD:**
```python
def pack(self, negotiated: Negotiated) -> bytes:
    """Pack the message.

    Args:
        negotiated (Negotiated): A Negotiated object.

    Returns:
        bytes: The packed bytes.
    """
```

**GOOD:**
```python
def pack(self, negotiated: Negotiated) -> bytes:
    """Serialize message to BGP wire format.

    Args:
        negotiated: Capability negotiation results from OPEN exchange.

    Returns:
        Message bytes with header (marker, length, type) and payload.
    """
```

### ❌ Don't State the Obvious

**BAD:**
```python
def get_afi(self) -> AFI:
    """Get the AFI.

    Returns:
        The AFI.
    """
    return self.afi
```

**GOOD (if documenting at all):**
```python
def get_afi(self) -> AFI:
    """Address Family Identifier for this route."""
    return self.afi
```

Or just skip the docstring for simple getters.

### ❌ Don't Write Implementation Details

**BAD:**
```python
def parse(self, data: bytes) -> Route:
    """Parse route from data.

    First we check the length, then we extract the prefix by slicing
    bytes 0-4, then we check if bit 7 is set, and if so we...
    """
```

**GOOD:**
```python
def parse(self, data: bytes) -> Route:
    """Parse route from BGP UPDATE NLRI bytes.

    Extracts prefix, length, and optional path identifier according to
    RFC 4271 Section 4.3 and RFC 7911 (ADD-PATH).

    Args:
        data: NLRI bytes starting at prefix length field.

    Returns:
        Route with populated prefix and path_info.

    Raises:
        Notification: When prefix length invalid or data truncated.
    """
```

Implementation details (bit checking, slicing) belong in code comments, not docstrings.

### ❌ Don't Apologize or Complain

**BAD:**
```python
def hack_for_legacy_peers(self, data: bytes) -> bytes:
    """Terrible hack to support broken BGP implementations.

    TODO: Remove this when we drop support for vendor X.
    This is really ugly but necessary because...
    """
```

**GOOD:**
```python
def hack_for_legacy_peers(self, data: bytes) -> bytes:
    """Apply compatibility transformations for non-RFC-compliant peers.

    Some BGP implementations incorrectly encode attribute X (violates
    RFC 4271 Section Y). This adjusts the encoding to work with those peers.

    Args:
        data: Standard RFC-compliant attribute bytes.

    Returns:
        Adjusted bytes compatible with legacy implementations.
    """
```

TODOs belong in code comments or GitHub issues, not docstrings.

---

## 🚀 Workflow for Adding Docstrings

### Step 1: Identify Files Needing Docs

**Priority Order:**
1. `src/exabgp/reactor/` - Reactor core (loop.py, peer.py, protocol.py)
2. `src/exabgp/bgp/message/` - BGP messages
3. `src/exabgp/configuration/` - Configuration parsing
4. `src/exabgp/application/` - CLI and entry points
5. `src/exabgp/bgp/message/update/attribute/` - Attributes
6. `src/exabgp/bgp/message/update/nlri/` - NLRI types

### Step 2: Read Code Context

Before writing docstrings for a file:
1. Read the entire file to understand purpose
2. Check imports to understand dependencies
3. Look at class hierarchy (what it inherits)
4. Check where it's used (grep for class name)
5. Read related RFC sections if mentioned

### Step 3: Write Docstrings Top-Down

1. **Module docstring** first (file overview)
2. **Class docstrings** next (one per class)
3. **Public methods** (no leading `_`)
4. **Complex private methods** (>20 lines)
5. **Simple private methods** (one-liners)

### Step 4: Review Your Work

Before submitting:
- [ ] Every public class has docstring
- [ ] Every public method has docstring
- [ ] Args/Returns sections match signature
- [ ] No repeated type information
- [ ] No obvious statements
- [ ] RFC references where applicable
- [ ] Grammar/spelling correct
- [ ] Fits in 80 characters (summary line)

---

## 📋 ExaBGP Vocabulary

Use these terms consistently:

| Instead of... | Say... |
|---------------|--------|
| "message" (vague) | "BGP UPDATE message" or "NOTIFICATION message" |
| "data" | "wire format bytes" or "packed bytes" |
| "info" | "capabilities" or "attributes" or specific term |
| "send" (vague) | "transmit to peer" or "encode to wire format" |
| "get" | "parse from bytes" or "extract from message" |
| "make" | "construct" or "create" or "generate" |

**BGP-specific terms:**
- NLRI (not "route announcement")
- Withdrawn routes (not "deleted routes")
- Path attributes (not "route attributes")
- Capabilities (not "features")
- Negotiated (not "agreed" or "configured")
- Wire format (not "binary format" or "raw data")

---

## 🎓 Learning Resources

**While writing docs, refer to:**
1. **RFCs:**
   - RFC 4271 - BGP-4 base protocol
   - RFC 4760 - Multiprotocol BGP (MP-BGP)
   - RFC 7911 - ADD-PATH
   - Check code comments for RFC references

2. **Existing Good Examples:**
   - `src/exabgp/bgp/message/open/asn.py` - Well-documented
   - `src/exabgp/environment/env.py` - Fully typed and documented
   - `tests/unit/test_aspath.py` - Excellent test documentation

3. **ExaBGP Guides:**
   - `.claude/exabgp/BGP_CONCEPTS_TO_CODE_MAP.md`
   - `.claude/exabgp/REGISTRY_AND_EXTENSION_PATTERNS.md`
   - `.claude/exabgp/DATA_FLOW_GUIDE.md`

---

## ✅ Quality Checklist

Use this checklist for each file you document:

**Module Level:**
- [ ] File has module docstring at top
- [ ] Module docstring explains purpose (1-3 sentences)
- [ ] Key classes/functions mentioned
- [ ] RFC references if applicable

**Class Level:**
- [ ] Every public class has docstring
- [ ] Class docstring explains responsibility
- [ ] Complex classes have usage example
- [ ] Class attributes documented (if any)

**Method Level:**
- [ ] Every public method has docstring
- [ ] Summary line is imperative mood with period
- [ ] Args section for all parameters
- [ ] Returns section for non-None returns
- [ ] Raises section for exceptions
- [ ] Unused params explained as "(unused...)"

**Style:**
- [ ] No type information repeated from signature
- [ ] No obvious statements ("Returns the value")
- [ ] No implementation details (bit shifting, etc.)
- [ ] Consistent terminology (see vocabulary table)
- [ ] Grammar and spelling correct

---

## 💡 Pro Tips

1. **Start with "Why"**: Ask yourself "Why does this exist?" before writing

2. **Read Tests**: Test files often show how functions are used - great context

3. **Use Search**: Grep for function calls to see usage patterns

4. **Check Git History**: `git log -p filename` shows why code was added

5. **Ask Questions**: If unclear what something does, add `# TODO: Document` comment

6. **Batch Similar Files**: Document all NLRI files together, all attributes together, etc.

7. **Run Linters**: After adding docs, run `uv run ruff check` to catch issues

8. **Focus on Public API First**: Users read public method docs most often

---

## 🎯 Success Metrics

Your documentation is successful when:

1. **A new developer** can understand what a class does without reading code
2. **You** can remember what a function does 6 months later
3. **Code reviewers** don't ask "what does this do?"
4. **API users** can use methods without reading implementation
5. **Docstrings** provide value beyond what code/types already show

---

**Remember:** Good documentation explains WHY and CONTEXT. The code already shows WHAT and HOW.

**When in doubt:** Write for your future self who forgot everything about this code.

---

**Version:** 1.0
**Last Updated:** 2025-12-01
**Author:** Claude (based on ExaBGP audit)
