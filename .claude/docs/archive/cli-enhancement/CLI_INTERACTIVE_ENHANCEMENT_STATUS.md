# CLI Interactive Enhancement - Status & Resume Guide

**Date Started:** 2025-11-20
**Status:** Core implementation complete, optional features pending
**Branch:** main (working directly)

---

## 🎯 Project Goal

Transform ExaBGP's CLI interactive mode from basic readline completion to an intelligent, context-aware TUI with:
- Dynamic command discovery (no hardcoded lists)
- Neighbor IP auto-completion
- AFI/SAFI value completion
- Route specification hints
- Neighbor filter completion
- Wiki documentation generator
- **Constraint:** Standard library only (no external deps)

---

## ✅ Completed Work (2025-11-20)

### Phase 1: Command Registry & Metadata System

**File:** `src/exabgp/reactor/api/command/registry.py` (~290 lines)

**What it does:**
- `CommandRegistry` class introspects `Command.callback` to discover all registered commands
- `CommandMetadata` dataclass stores structured command info (syntax, options, category)
- Provides helper methods:
  - `get_all_commands()` - all 35+ command names
  - `get_base_commands()` - first word of each command
  - `get_subcommands(prefix)` - commands starting with prefix
  - `build_command_tree()` - hierarchical tree for completion
  - `get_afi_values()`, `get_safi_values()`, `get_neighbor_filters()`, `get_route_keywords()`

**Key insight:** Commands are stored in `Command.callback['text']` dict. By iterating this at runtime, we auto-discover all commands without hardcoding.

**Categories defined:**
```python
CATEGORIES = {
    'show neighbor': 'show',
    'announce route': 'announce',
    'withdraw route': 'withdraw',
    'flush adj-rib out': 'rib',
    'teardown': 'control',
    # ... etc
}
```

### Phase 2: Shared Shortcut Expansion

**File:** `src/exabgp/application/shortcuts.py` (~160 lines)

**What it does:**
- `CommandShortcuts` class with context-aware expansion logic
- Main methods:
  - `expand_shortcuts(command_str)` - expands full command string
  - `expand_token_list(tokens)` - expands list of tokens
  - `get_expansion(token, pos, previous)` - single token expansion
  - `get_possible_expansions(...)` - all possible expansions (for ambiguity)

**Shortcuts supported:**
- Single-letter: `h`→help, `s`→show, `a`→announce, `w`→withdraw, etc.
- Context-aware: `a` can mean announce, attributes, or adj-rib depending on context
- Multi-letter: `rr`→route-refresh
- Typo correction: `neighbour`/`neigbor`→neighbor

**Before/After:**
```python
# BEFORE: Duplicated in 3 places (cmdline, cmdline_interactive, cmdline_batch)
# Each had ~40 lines of identical shortcut logic

# AFTER: Single shared module
from exabgp.application.shortcuts import CommandShortcuts
sending = CommandShortcuts.expand_shortcuts(command_str)
```

**Files refactored:**
- `src/exabgp/application/cli.py` - all 3 entry points now use shared module
- ~120 lines of duplicated code eliminated

### Phase 3: Enhanced Command Completer

**File:** `src/exabgp/application/cli_interactive.py` (modified)

**Changes to CommandCompleter class:**

1. **Dynamic command tree** (lines 81-88):
   ```python
   self.registry = CommandRegistry()
   self.command_tree = self.registry.build_command_tree()
   self.base_commands = self.registry.get_base_commands()
   ```

2. **New completion methods:**
   - `_complete_neighbor_command()` - neighbor-targeted commands
   - `_complete_neighbor_filters()` - local-ip, local-as, peer-as, etc.
   - `_complete_afi_safi()` - AFI/SAFI for eor/route-refresh
   - `_complete_route_spec()` - route keywords (next-hop, community, etc.)
   - `_is_ip_address()` - detects IPv4/IPv6 in tokens

3. **Enhanced neighbor IP fetching** (lines 268-316):
   - Tries `show neighbor json` to get live neighbor IPs
   - Caches for 30 seconds (configurable)
   - Parses JSON response for 'peer-address' or 'remote-addr' fields
   - Falls back gracefully if ExaBGP not running

4. **Shortcut expansion integration:**
   ```python
   expanded_tokens = CommandShortcuts.expand_token_list(tokens.copy())
   ```
   Now uses shared module instead of hardcoded dict

**Command tree structure:**
```python
{
    'show': {
        'neighbor': {
            '__options__': ['summary', 'extensive', 'configuration', 'json']
        },
        'adj-rib': {
            'in': {'__options__': ['extensive', 'json']},
            'out': {'__options__': ['extensive', 'json']}
        }
    },
    # ... dynamically generated from registry
}
```

### Phase 4: Wiki Documentation Generator

**File:** `sbin/exabgp-doc-generator` (~250 lines, executable)

**What it does:**
- Queries `CommandRegistry` for all command metadata
- Generates documentation in markdown, JSON, or text format
- Can check if docs are up-to-date (for CI)

**Usage:**
```bash
# Generate markdown docs
./sbin/exabgp-doc-generator --output-dir docs/wiki/commands

# Generate JSON (for programmatic use)
./sbin/exabgp-doc-generator --format json

# Check mode (for CI)
./sbin/exabgp-doc-generator --check
```

**Output structure:**
```
docs/wiki/commands/
├── README.md                 # Overview with all commands
├── show-commands.md          # Show category
├── announce-commands.md      # Announce category
├── withdraw-commands.md      # Withdraw category
├── control-commands.md       # Control category
└── rib-commands.md          # RIB category
```

---

## 🧪 Testing Performed

### Linting
```bash
ruff format src/exabgp/application/{cli.py,shortcuts.py,cli_interactive.py} \
             src/exabgp/reactor/api/command/registry.py
ruff check src/exabgp/application/{cli.py,shortcuts.py,cli_interactive.py} \
           src/exabgp/reactor/api/command/registry.py
```
**Result:** ✅ All checks passed

### Unit Tests
```bash
env exabgp_log_enable=false pytest ./tests/unit/ -q
```
**Result:** ✅ 1424/1424 passed in 4.38s

### Manual Testing
- Doc generator works: `./sbin/exabgp-doc-generator --format json`
- Shortcut expansion tested via imports (no runtime errors)
- Command registry introspection verified (discovers all commands)

### NOT Tested (requires running ExaBGP instance)
- Interactive REPL with live completion
- Neighbor IP fetching from running ExaBGP
- Full command execution flow

---

## 📋 Files Changed Summary

### New Files (4)
1. `src/exabgp/reactor/api/command/registry.py` - Command introspection
2. `src/exabgp/application/shortcuts.py` - Shared shortcut expansion
3. `sbin/exabgp-doc-generator` - Documentation generator
4. `.claude/CLI_INTERACTIVE_ENHANCEMENT_STATUS.md` - This file

### Modified Files (2)
1. `src/exabgp/application/cli.py`
   - Import: `from exabgp.application.shortcuts import CommandShortcuts`
   - Removed: Import of `IPv4` (no longer needed)
   - Lines 279-281: One-shot command uses `CommandShortcuts.expand_shortcuts()`
   - Lines 333-335: Interactive send_command uses `CommandShortcuts.expand_shortcuts()`
   - Lines 402-403: Batch mode uses `CommandShortcuts.expand_shortcuts()`

2. `src/exabgp/application/cli_interactive.py`
   - Imports: Added `json`, `re`, `CommandShortcuts`, `CommandRegistry`
   - Lines 81-93: CommandCompleter.__init__() uses registry
   - Lines 124-266: Completely rewritten _get_completions() with context awareness
   - Lines 268-316: Enhanced _get_neighbor_ips() with JSON parsing and caching

---

## 🚧 Pending Work (Optional)

### High Priority (Recommended)
1. **Unit tests** - Test the new modules
   - `tests/unit/test_shortcuts.py` - Test all shortcut expansions
   - `tests/unit/test_command_registry.py` - Test registry introspection
   - `tests/unit/test_completer.py` - Test completion logic

2. **Integration testing** - Test with running ExaBGP
   - Start ExaBGP with test config
   - Launch interactive mode
   - Verify neighbor IP completion works
   - Verify AFI/SAFI completion works

3. **Documentation**
   - Add docstrings to command handlers (in `src/exabgp/reactor/api/command/*.py`)
   - Generate wiki docs: `./sbin/exabgp-doc-generator --output-dir docs/wiki/commands`
   - Update main docs to mention new completion features

### Medium Priority (Nice to Have)
4. **Syntax validation on Enter**
   - Add validation before sending command
   - Show colored feedback: ✓ valid (green) or ✗ invalid (red)
   - Let user send anyway (server validates too)

5. **Enhanced error messages**
   - If completion fails to fetch neighbor IPs, show helpful hint
   - Better error messages for invalid shortcuts

6. **Completion display formatting**
   - Color-code completion suggestions by type:
     - Commands: blue
     - Neighbor IPs: green
     - Parameters: yellow
   - Show inline help after TAB press

### Low Priority (Future Enhancements)
7. **Syntax highlighting as you type**
   - Would require `curses` or `prompt_toolkit` (not standard library)
   - Probably not worth the dependency

8. **Multi-line editing**
   - Support for complex announce commands spanning multiple lines
   - Would need curses

9. **History search improvements**
   - Filter history by command type
   - Timestamp metadata in history file
   - Already works: Ctrl+R reverse search (readline built-in)

---

## 🔧 How to Resume Work

### If Adding Unit Tests

1. **Create test file:**
   ```bash
   touch tests/unit/test_shortcuts.py
   ```

2. **Test structure:**
   ```python
   from exabgp.application.shortcuts import CommandShortcuts

   def test_basic_shortcuts():
       assert CommandShortcuts.expand_shortcuts('s n') == 'show neighbor'
       assert CommandShortcuts.expand_shortcuts('a r') == 'announce route'

   def test_context_aware():
       # 'a' after 'show' should expand to 'adj-rib'
       tokens = ['show', 'a']
       expanded = CommandShortcuts.expand_token_list(tokens)
       assert expanded == ['show', 'adj-rib']
   ```

3. **Run tests:**
   ```bash
   env exabgp_log_enable=false pytest tests/unit/test_shortcuts.py -v
   ```

### If Testing Interactive Mode

1. **Start ExaBGP with test config:**
   ```bash
   ./sbin/exabgp ./etc/exabgp/api-rib.conf
   ```

2. **In another terminal, start interactive CLI:**
   ```bash
   ./sbin/clii
   ```

3. **Test completion scenarios:**
   - Type `show n<TAB>` - should complete to `neighbor`
   - Type `show neighbor <TAB>` - should show neighbor IPs + options
   - Type `announce eor <TAB>` - should show AFI values
   - Type `announce eor ipv4 <TAB>` - should show SAFI values

4. **Test shortcuts:**
   - Type `s n summary` - should expand to `show neighbor summary`
   - Type `a e ipv4 unicast` - should expand to `announce eor ipv4 unicast`

### If Adding Syntax Validation

1. **Add to InteractiveCLI.run() method** (around line 470):
   ```python
   def run(self):
       while True:
           try:
               user_input = input(prompt)

               # NEW: Validate before sending
               if self._validate_syntax(user_input):
                   print(formatter.format_success("Valid command"))
               else:
                   print(formatter.format_warning("Invalid syntax (sending anyway)"))

               response = self.send_command(user_input)
               # ... rest of code
   ```

2. **Add validation method:**
   ```python
   def _validate_syntax(self, command: str) -> bool:
       """Validate command syntax using registry"""
       expanded = CommandShortcuts.expand_shortcuts(command)
       tokens = expanded.split()

       # Check if command exists
       for cmd_name in self.completer.registry.get_all_commands():
           if expanded.startswith(cmd_name):
               return True

       return False
   ```

### If Generating Wiki Docs

1. **Generate docs:**
   ```bash
   ./sbin/exabgp-doc-generator --output-dir docs/wiki/commands
   ```

2. **Review output:**
   ```bash
   ls -la docs/wiki/commands/
   cat docs/wiki/commands/README.md
   ```

3. **Add to git:**
   ```bash
   git add docs/wiki/commands/
   git commit -m "docs: Add auto-generated command reference"
   ```

---

## 🐛 Known Issues & Considerations

### Issue 1: Neighbor IP Completion Requires Running ExaBGP
**Problem:** `_get_neighbor_ips()` calls `send_command('show neighbor json')`, which only works if ExaBGP is running.

**Workaround:** Method fails gracefully, returns empty list.

**Future fix:** Could provide a callback function at initialization to fetch neighbors externally.

### Issue 2: AFI/SAFI Values Hardcoded in Registry
**Problem:** AFI/SAFI values are hardcoded in `CommandRegistry.AFI_NAMES` and `CommandRegistry.SAFI_NAMES`.

**Current approach:** Values pulled from `exabgp.protocol.family` module documentation.

**Future fix:** Could dynamically introspect `AFI.codes` and `SAFI.codes` dicts.

### Issue 3: Route Keywords Not Comprehensive
**Problem:** `CommandRegistry.ROUTE_KEYWORDS` may not include all valid route parameters.

**Current list:** Common keywords from announce/withdraw handlers.

**Future fix:** Parse route specification from `ParseStaticRoute` to get complete list.

### Issue 4: No Validation Before Sending
**Problem:** User can type invalid command, CLI sends it, server rejects it.

**Current behavior:** Works fine (server validates), but wastes round-trip.

**Future fix:** Add optional local validation before sending (see "If Adding Syntax Validation" above).

### Issue 5: Command Tree Doesn't Show All Valid Paths
**Problem:** Some commands accept neighbor prefix but tree doesn't show both paths.

**Example:** `announce route` vs `neighbor 1.2.3.4 announce route`

**Current approach:** Tree shows command without neighbor prefix, completion logic adds neighbor support.

**Future fix:** Could build dual trees or annotate nodes with "accepts neighbor prefix".

---

## 📚 Architecture Notes

### Why Two Modules (shortcuts + registry)?

**shortcuts.py:**
- Pure Python, no dependencies on ExaBGP internals
- Can be tested standalone
- Stateless transformation (command string → expanded string)

**registry.py:**
- Depends on `Command` class from `exabgp.reactor.api.command.command`
- Must be imported after ExaBGP modules loaded
- Stateful (caches metadata)

**Design decision:** Keep shortcut expansion separate for testability and reusability.

### Command Tree Structure

The tree uses a special `__options__` key for leaf nodes:
```python
{
    'show': {
        'neighbor': {
            '__options__': ['summary', 'extensive', 'json']
        }
    }
}
```

**Why `__options__`?**
- Distinguishes subcommands (dict keys) from options (list values)
- Allows nested commands like `show adj-rib in`
- `__options__` key unlikely to conflict with real command names

### Completion Algorithm

1. Expand shortcuts in typed tokens
2. Check for special contexts:
   - Neighbor-targeted command? → suggest IPs or filters
   - After `eor`/`route-refresh`? → suggest AFI/SAFI
   - After `route`/`ipv4`/`ipv6`? → suggest route keywords
3. Navigate command tree using expanded tokens
4. Return matches at current level

**Example flow:**
```
User types: "s n <TAB>"
1. tokens = ['s', 'n']
2. Expand: ['show', 'neighbor']
3. Navigate tree: root → show → neighbor
4. At leaf: return ['summary', 'extensive', 'configuration', 'json']
```

---

## 🔍 Debugging Tips

### Enable ExaBGP Logging
```bash
env exabgp_log_enable=true ./sbin/exabgp config.conf
```

### Test Shortcuts Manually
```python
from exabgp.application.shortcuts import CommandShortcuts

# Test expansion
print(CommandShortcuts.expand_shortcuts('s n summary'))
# Output: 'show neighbor summary'

# Test token list
tokens = ['a', 'r', '10.0.0.0/24']
print(CommandShortcuts.expand_token_list(tokens))
# Output: ['announce', 'route', '10.0.0.0/24']
```

### Test Registry Manually
```python
from exabgp.reactor.api.command.registry import CommandRegistry

registry = CommandRegistry()

# List all commands
print(registry.get_all_commands())

# Get metadata
metadata = registry.get_command_metadata('show neighbor')
print(f"Syntax: {metadata.syntax}")
print(f"Options: {metadata.options}")
```

### Test Completion Manually
```python
from exabgp.application.cli_interactive import CommandCompleter

# Mock send_command
def mock_send(cmd):
    return '[]'  # Empty neighbor list

completer = CommandCompleter(mock_send)

# Test completion
tokens = ['show', 'neighbor']
matches = completer._get_completions(tokens, '')
print(matches)
# Output: ['configuration', 'extensive', 'json', 'summary']
```

### Check Command Registration
```python
from exabgp.reactor.api.command.command import Command

# See all registered commands
print(Command.functions)

# Check specific command
print('show neighbor' in Command.callback['text'])
print(Command.callback['options'].get('show neighbor'))
```

---

## 📞 Contact & Resources

**Project constraints from user:**
- Standard library only (no external deps)
- Refactor code for DRY
- Dynamic discovery (no hardcoding)
- Wiki documentation generation
- Backward compatible

**Key decisions made:**
- Used readline (already in use) instead of prompt_toolkit
- Built registry by introspecting Command.callback (not parsing source)
- Cached neighbor IPs for 30s (balance between freshness and performance)
- Kept shortcut expansion separate from command registry (modularity)

**Related files to check:**
- `src/exabgp/reactor/api/command/command.py` - Command registration decorator
- `src/exabgp/reactor/api/command/announce.py` - Example command handlers
- `src/exabgp/protocol/family.py` - AFI/SAFI definitions
- `CLAUDE.md` - Main project instructions

---

**Status:** Ready for testing with live ExaBGP instance. Core implementation complete and tested.
**Next recommended step:** Create unit tests or test with running ExaBGP.
