# CLI Implementation Architecture

Internal architecture and design of the ExaBGP interactive CLI.

**For developers modifying the CLI.**

**See also:**
- `CLI_COMMANDS.md` - Complete command reference
- `CLI_SHORTCUTS.md` - Shortcut reference
- `UNIX_SOCKET_API.md` - Unix socket API protocol

---

## File Structure

**Main entry point:** `src/exabgp/application/cli.py` (583 lines) - InteractiveCLI class

**CLI module:** `src/exabgp/cli/` (4,176 total lines)
| File | Lines | Purpose |
|------|-------|---------|
| `persistent_connection.py` | 678 | Socket lifecycle, health monitoring |
| `completer.py` | 1,426 | Tab completion with auto-expansion |
| `formatter.py` | 458 | Output formatting (JSON/text) |
| `history.py` | 420 | Command history management |
| `command_schema.py` | 350 | Command schema definitions |
| `schema_bridge.py` | 407 | Registry ↔ schema bridge |
| `fuzzy.py` | 359 | Fuzzy command matching |
| `colors.py` | 59 | ANSI color helpers |

**Supporting files:**
- `src/exabgp/application/shortcuts.py` - Command shortcut expansion
- `src/exabgp/reactor/api/command/registry.py` - Command introspection
- `src/exabgp/reactor/api/command/command.py` - Command registration
- `src/exabgp/application/unixsocket.py` - Socket discovery

---

## Architecture Overview

### Four Core Classes

```
PersistentSocketConnection
  ↓ manages socket lifecycle
InteractiveCLI
  ↓ uses for command execution
CommandCompleter
  ↓ provides tab completion
OutputFormatter
  ↓ formats responses
```

### Execution Flow

```
User input (REPL)
  → readline (TAB pressed)
     → CommandCompleter.complete()
        → Shortcut expansion
        → Context analysis
        → Registry lookup
        → Return matches + metadata
  → Command execution
     → Shortcut expansion
     → CLI-to-API transformation
     → Send to socket
     → Wait for response
     → Format output
     → Display to user
```

---

## Class: PersistentSocketConnection

**File:** `src/exabgp/cli/persistent_connection.py` (678 lines)

**Purpose:** Manage Unix socket connection with automatic reconnection and health monitoring.

### Responsibilities

1. **Socket lifecycle** - Connect, disconnect, reconnect
2. **Health monitoring** - Background ping thread
3. **Single-client enforcement** - UUID-based exclusivity
4. **Background reader** - Non-blocking response reception
5. **Automatic reconnection** - Max 5 attempts, 2-second delay

### Key Methods

#### `__init__(socket_path=None)`

Initialize connection manager.

**Parameters:**
- `socket_path` (optional) - Path to Unix socket (auto-discovers if None)

**Auto-discovery:**
1. Checks `EXABGP_SOCKET` environment variable
2. Searches `/run/exabgp/*.sock`
3. Searches `/var/run/exabgp/*.sock`
4. Searches `$HOME/run/exabgp/*.sock`

**Implementation:** `src/exabgp/application/unixsocket.py:get_socket_path()`

---

#### `connect()`

Establish socket connection.

**Returns:** `True` on success, `False` on failure

**Process:**
1. Create `socket.AF_UNIX` socket
2. Set 5-second timeout
3. Connect to socket path
4. Start reader thread
5. Start health monitor thread
6. Enforce single-client (send initial ping)

**Threads started:**
- `_reader_thread()` - Reads responses continuously
- `_health_monitor_thread()` - Sends periodic pings

---

#### `disconnect()`

Gracefully close connection.

**Process:**
1. Set `_stopping = True`
2. Send `bye` command
3. Wait for threads to exit (5-second timeout)
4. Close socket
5. Clear response queue

---

#### `send_command(command, timeout=5.0)`

Send command and wait for response.

**Parameters:**
- `command` - Command string (without newline)
- `timeout` - Response timeout in seconds (default: 5.0)

**Returns:** Response string or `None` on timeout

**Process:**
1. Acquire send lock (thread-safe)
2. Send `command + '\n'` to socket
3. Wait for response in queue (blocking with timeout)
4. Return response or `None`

**Thread-safe:** Uses `threading.Lock()` for send operations

---

#### `_reader_thread()`

Background thread that continuously reads from socket.

**Purpose:** Non-blocking response reception

**Process:**
1. Loop while not stopping
2. Select on socket (0.1s timeout)
3. Read available data
4. Split on `\n`, buffer incomplete lines
5. Put complete lines in response queue
6. Detect disconnection, trigger reconnect

**Exit conditions:**
- `_stopping = True`
- Socket closed/error

---

#### `_health_monitor_thread()`

Background thread that sends periodic health checks.

**Purpose:** Detect daemon restarts, maintain connection

**Process:**
1. Loop while not stopping
2. Sleep 10 seconds
3. Send `ping {uuid} {timestamp}`
4. Wait for `pong` response (5-second timeout)
5. If no response, mark as unhealthy
6. Trigger reconnection if needed

**Ping format:**
```
ping 550e8400-e29b-41d4-a716-446655440000 1732412345
```

**Pong format:**
```
pong {uuid} {server_timestamp}
```

---

#### `_reconnect()`

Attempt automatic reconnection.

**Parameters:** Max 5 attempts, 2-second delay between attempts

**Process:**
1. Close existing socket
2. Wait 2 seconds
3. Attempt connection
4. If successful, restart threads
5. If all attempts fail, exit CLI

---

### Threading Model

```
Main thread (REPL)
  │
  ├─ Reader thread
  │    └─ Continuously reads from socket
  │    └─ Puts responses in queue
  │
  └─ Health monitor thread
       └─ Sends periodic pings
       └─ Triggers reconnection on failure
```

**Synchronization:**
- `threading.Lock()` - Send operations
- `queue.Queue()` - Response passing
- `threading.Event()` - Shutdown signaling

---

## Class: CommandCompleter

**File:** `src/exabgp/cli/completer.py` (1,426 lines)

**Purpose:** Context-aware tab completion with auto-expansion.

### Responsibilities

1. **Tab completion** - Readline integration
2. **Context analysis** - Determine what to complete
3. **Auto-expansion** - Expand unambiguous prefixes
4. **Metadata display** - Show descriptions for completions
5. **Neighbor IP caching** - Fetch live neighbor list

### Key Methods

#### `__init__(socket_conn)`

Initialize completer.

**Parameters:**
- `socket_conn` - PersistentSocketConnection instance

**Setup:**
1. Create CommandRegistry for introspection
2. Build command tree from registry
3. Initialize neighbor cache (5-minute TTL)
4. Set up platform-specific readline (GNU vs libedit)

---

#### `complete(text, state)`

Readline completion callback.

**Parameters:**
- `text` - Current word being completed
- `state` - Match index (0 for first match, 1 for second, etc.)

**Returns:** `state`-th match or `None` if no more matches

**Process:**
1. On `state == 0`:
   - Get full line from readline
   - Parse into tokens
   - Expand shortcuts
   - Try auto-expansion
   - Get completions for current context
   - Store matches
2. On `state > 0`:
   - Return next match from stored list

**Auto-expansion:**
- If token has exactly 1 completion, expand it inline
- Uses `rl_replace_line()` via ctypes (platform-specific)

---

#### `_get_completions(line, text)`

Get completions for current context.

**Parameters:**
- `line` - Full command line
- `text` - Current word being completed

**Returns:** List of `(value, description, type)` tuples

**Context detection:**
1. Parse line into tokens
2. Expand shortcuts
3. Check position in command
4. Determine context (base command, subcommand, option, neighbor, etc.)
5. Return appropriate completions

**Completion types:**
- `command` - Base commands (show, announce, etc.)
- `subcommand` - Multi-word commands (show neighbor, announce route)
- `option` - Command options (summary, extensive, json)
- `neighbor` - Neighbor IP addresses (live from daemon)
- `keyword` - AFI/SAFI, route attributes, filters

---

#### `_complete_neighbor_command(tokens)`

Complete neighbor-targeted commands.

**Example:** `neighbor 192.168.1.1 <TAB>` → show, teardown, announce, withdraw

**Returns:** List of commands that work with neighbor selectors

---

#### `_complete_neighbor_filters(tokens)`

Complete neighbor selector qualifiers.

**Example:** `show neighbor <TAB>` → IPs, local-ip, peer-as, router-id, summary, extensive

**Returns:** Neighbor IPs (live) + selector keywords + show options

---

#### `_complete_afi_safi(tokens)`

Complete AFI/SAFI values.

**Example:**
- `announce eor <TAB>` → ipv4, ipv6
- `announce eor ipv4 <TAB>` → unicast, multicast, mpls-vpn

**Returns:** Context-aware AFI or SAFI values

---

#### `_complete_route_spec(tokens)`

Complete route specification keywords.

**Example:** `announce route 10.0.0.0/24 <TAB>` → next-hop, as-path, community, etc.

**Returns:** Route attribute keywords

---

#### `_fetch_neighbor_ips()`

Fetch live neighbor IPs from daemon.

**Process:**
1. Check cache (5-minute TTL)
2. If expired, send `show neighbor json`
3. Parse JSON response
4. Extract `peer-address` or `remote-addr` fields
5. Cache results
6. Return list of IPs with AS and state metadata

**Returns:** List of `(ip, "neighbor, AS{asn}, {state}")` tuples

**Caching:** 5-minute TTL to avoid repeated socket calls

---

#### `_try_auto_expand_tokens(tokens, current_word)`

Auto-expand unambiguous token prefixes.

**Parameters:**
- `tokens` - List of tokens in line
- `current_word` - Word being completed

**Returns:** `(expanded_tokens, expansions_made)`

**Logic:**
1. For each token, check if it has exactly 1 completion
2. If yes, expand to full word
3. If no or multiple, keep original
4. Return expanded tokens + count

**Example:**
```python
tokens = ["s", "n", "s"]
→ (["show", "neighbor", "summary"], 3)
```

---

#### `_try_replace_line(new_line)`

Replace readline buffer with expanded line.

**Platform-specific:** Uses ctypes to access `rl_replace_line()`

**Libraries:**
- macOS: `/usr/lib/libedit.dylib`
- Linux: `libreadline.so`

**Process:**
1. Load readline library via ctypes
2. Get `rl_replace_line` function
3. Get `rl_forced_update_display` function
4. Call `rl_replace_line(new_line, 0)`
5. Call `rl_forced_update_display()`

**Fallback:** If library not found, silently skip (normal completion)

---

### Completion Metadata

Each completion has:
- **value** - Completion text
- **description** - Human-readable explanation
- **type** - `command`, `option`, `neighbor`, `keyword`

**Display format (one per line):**
```
show         Display information about neighbors, routes, or configuration
neighbor     Target specific neighbor by IP
10.0.0.1     (neighbor, AS65000, ESTABLISHED)
```

**Color coding:**
- Yellow - Commands
- Cyan - Neighbor IPs
- Green - Options/keywords
- Dim - Descriptions

---

### Command Tree Structure

**Built from CommandRegistry introspection:**

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
    'announce': {
        'route': {'__options__': [...]},
        'eor': {'__options__': [...]},
        'route-refresh': {'__options__': [...]}
    },
    # ... dynamically generated
}
```

**Advantages:**
- No hardcoded command lists
- Auto-discovers new commands
- Always in sync with registry

---

## Class: OutputFormatter

**File:** `src/exabgp/cli/formatter.py` (458 lines)

**Purpose:** Format API responses for display.

### Responsibilities

1. **JSON pretty-printing** - Indent and colorize JSON
2. **JSON-to-text conversion** - Convert JSON to readable tables
3. **ANSI color support** - Detect and apply colors
4. **Prompt formatting** - Display CLI prompt

### Key Methods

#### `format_command_output(output, display_mode='text')`

Format command output based on display mode.

**Parameters:**
- `output` - Raw output from API
- `display_mode` - `'json'` or `'text'`

**Returns:** Formatted string

**Process:**
1. Detect if output is JSON (starts with `{` or `[`)
2. If `display_mode == 'json'`:
   - Pretty-print JSON with 2-space indent
   - Colorize if terminal supports it
3. If `display_mode == 'text'`:
   - If JSON, convert to text tables
   - Otherwise, return as-is
4. Return formatted output

---

#### `_json_to_text_table(json_data)`

Convert JSON to human-readable tables.

**Parameters:**
- `json_data` - Parsed JSON (dict or list)

**Returns:** Formatted text string

**Examples:**

**Neighbor summary (list of dicts):**
```json
[
  {"peer": "192.168.1.1", "as": 65000, "state": "established"},
  {"peer": "10.0.0.1", "as": 65001, "state": "idle"}
]
```
↓
```
Peer           AS      State
192.168.1.1    65000   established
10.0.0.1       65001   idle
```

**Single neighbor (dict):**
```json
{
  "peer": "192.168.1.1",
  "local-as": 65000,
  "peer-as": 65001,
  "state": "established",
  "uptime": "3 days"
}
```
↓
```
peer:      192.168.1.1
local-as:  65000
peer-as:   65001
state:     established
uptime:    3 days
```

---

#### `get_prompt()`

Generate CLI prompt string.

**Returns:** Formatted prompt (e.g., `"ExaBGP> "`)

**Colorization:** Green prompt if terminal supports ANSI colors

---

### Color Support Detection

**Method:** `_supports_color()`

**Checks:**
1. `NO_COLOR` environment variable not set
2. `stdout.isatty()` is True (not redirected)
3. `TERM` is not `'dumb'`

**Returns:** `True` if colors supported

---

## Class: InteractiveCLI

**File:** `src/exabgp/application/cli.py` (583 lines)

**Purpose:** Main REPL loop and command execution.

### Responsibilities

1. **REPL loop** - Read-Eval-Print loop
2. **Command execution** - Send commands to API
3. **Display mode management** - Track json/text mode
4. **Built-in commands** - exit, quit, clear, history, set
5. **Error handling** - Graceful degradation

### Key Methods

#### `__init__(socket_path=None)`

Initialize CLI.

**Process:**
1. Create PersistentSocketConnection
2. Connect to socket
3. Create CommandCompleter
4. Create OutputFormatter
5. Initialize display settings
6. Set up readline (history, completion)

**Settings:**
- `encoding_mode` - API response format (`'json'` or `'text'`)
- `display_mode` - CLI display format (`'text'` or `'json'`)

**Defaults:**
- `encoding_mode = 'json'`
- `display_mode = 'text'` (auto-converts JSON to tables)

---

#### `run()`

Main REPL loop.

**Process:**
1. Display welcome message
2. Loop:
   - Show prompt
   - Read line from readline
   - Strip whitespace
   - Skip empty lines
   - Handle built-in commands
   - Execute command
   - Display output
3. Handle Ctrl+C gracefully (KeyboardInterrupt)
4. Handle Ctrl+D gracefully (EOFError)
5. Cleanup on exit

**Exit conditions:**
- `exit` or `quit` command
- Ctrl+D (EOF)
- Connection lost

---

#### `_execute_command(command)`

Execute command and display output.

**Parameters:**
- `command` - Command string (after shortcut expansion)

**Process:**
1. Check for display mode override (`json` or `text` prefix)
2. Expand shortcuts
3. Transform CLI-to-API syntax
4. Send to socket
5. Wait for response
6. Format output
7. Display to user

**Display mode override:**
```bash
json show neighbor     # Display as JSON (overrides setting)
text show neighbor     # Display as text (overrides setting)
```

---

#### `_handle_builtin_command(command)`

Handle built-in CLI commands.

**Returns:** `True` if command handled, `False` otherwise

**Built-in commands:**

1. **`exit` / `quit`** - Exit CLI
   ```python
   return True  # Signals REPL to exit
   ```

2. **`clear`** - Clear screen
   ```python
   os.system('clear' if os.name != 'nt' else 'cls')
   ```

3. **`history [count]`** - Show command history
   ```python
   readline.get_current_history_length()
   readline.get_history_item(i)
   ```

4. **`set encoding json|text`** - Set API encoding
   ```python
   self.encoding_mode = value
   ```

5. **`set display json|text`** - Set display format
   ```python
   self.display_mode = value
   ```

---

### Readline Configuration

**File:** `~/.exabgp_history`

**History:**
- Loaded on startup
- Saved on exit
- Max 1000 lines

**Completion:**
- TAB key triggers `CommandCompleter.complete()`
- macOS libedit: Shows completions on single TAB
- GNU readline: Shows completions on second TAB

**Key bindings:**
- TAB - Complete
- Ctrl+R - Reverse search
- Ctrl+C - Cancel input
- Ctrl+D - Exit
- Up/Down - History navigation

---

## Command Execution Flow

### Full Pipeline

```
1. User types: "s n s<TAB>"
   ↓
2. CommandCompleter.complete() called
   ↓
3. Expand shortcuts: "show neighbor summary"
   ↓
4. Check for single completion → Yes (summary)
   ↓
5. Auto-expand inline
   ↓
6. User sees: "show neighbor summary"
   ↓
7. User presses Enter
   ↓
8. InteractiveCLI._execute_command()
   ↓
9. Expand shortcuts again (idempotent)
   ↓
10. Transform CLI-to-API syntax (no change needed)
   ↓
11. Send to socket: "show neighbor summary\n"
   ↓
12. PersistentSocketConnection.send_command()
   ↓
13. Wait for response in queue
   ↓
14. Response received (JSON)
   ↓
15. OutputFormatter.format_command_output()
   ↓
16. Convert JSON to text table
   ↓
17. Display to user
```

---

## Shortcut Expansion

**File:** `src/exabgp/application/shortcuts.py`

### CommandShortcuts Class

#### `expand_shortcuts(command_str)`

Expand shortcuts in full command string.

**Parameters:**
- `command_str` - Command with shortcuts (e.g., `"s n s"`)

**Returns:** Expanded command (e.g., `"show neighbor summary"`)

**Process:**
1. Split into tokens
2. Expand each token with context
3. Join back into string

---

#### `expand_token_list(tokens)`

Expand shortcuts in token list.

**Parameters:**
- `tokens` - List of tokens (e.g., `["s", "n", "s"]`)

**Returns:** Expanded tokens (e.g., `["show", "neighbor", "summary"]`)

**Process:**
1. Iterate tokens with position
2. For each, call `get_expansion()`
3. Return expanded list

---

#### `get_expansion(token, position, previous_tokens)`

Get expansion for single token in context.

**Parameters:**
- `token` - Token to expand
- `position` - Position in command (0 = first)
- `previous_tokens` - Tokens that came before

**Returns:** Expanded token or original if no match

**Context rules:**
1. Check position (first token has special rules)
2. Check previous tokens (what came before)
3. Match against shortcut table
4. Apply first matching rule
5. Return expansion or original

**Example:**
```python
get_expansion("a", 0, [])
→ "announce"

get_expansion("a", 1, ["show"])
→ "adj-rib"

get_expansion("a", 1, ["announce"])
→ "attributes"
```

---

### CLI-to-API Transformation

**Also in:** `src/exabgp/application/shortcuts.py`

#### `transform_cli_to_api(command_str)`

Transform CLI-friendly syntax to API syntax.

**IMPORTANT:** Only `show` commands are transformed. All other commands use neighbor-first syntax natively.

**Transformations (show commands only):**

| CLI Syntax (transformed) | API Syntax (also accepted) |
|--------------------------|----------------------------|
| `neighbor <ip> show ...` | `show neighbor <ip> ...` |
| `neighbor <ip> adj-rib in show` | `show adj-rib in <ip>` |
| `adj-rib in show` | `show adj-rib in` |

**Standard API syntax (no transformation):**
- `neighbor <ip> announce route ...` - neighbor-first (NOT transformed)
- `neighbor <ip> withdraw route ...` - neighbor-first (NOT transformed)
- `neighbor <ip> teardown` - neighbor-first (NOT transformed)
- `neighbor <ip> announce eor ...` - neighbor-first (NOT transformed)

**Implementation:** Pattern matching and reordering for `show` commands only

---

## Command Registry

**File:** `src/exabgp/reactor/api/command/registry.py`

### CommandRegistry Class

**Purpose:** Introspect registered commands for tab completion.

#### `get_all_commands()`

Get all registered command names.

**Returns:** List of command strings (e.g., `["show neighbor", "announce route", ...]`)

**Source:** `Command.callback['text']` dict

---

#### `build_command_tree()`

Build hierarchical command tree.

**Returns:** Nested dict representing command structure

**Example:**
```python
{
    'show': {
        'neighbor': {...},
        'adj-rib': {...}
    }
}
```

---

#### `get_afi_values()`, `get_safi_values()`, etc.

Get completion values for specific contexts.

**Returns:** Lists of valid values

---

### CommandMetadata

**Data class** storing command information:
- `name` - Command name
- `syntax` - Syntax string
- `description` - Human-readable description
- `options` - List of options
- `category` - Command category

---

## Extension Points

### Adding New Commands

**Process:**
1. Register command in `src/exabgp/reactor/api/command/*.py`:
   ```python
   @Command.register('my-command', neighbor=True, json_support=True)
   def my_command(self, reactor, service, command):
       # Implementation
       pass
   ```

2. CommandRegistry auto-discovers via introspection
3. Tab completion works automatically
4. Add shortcut (optional) in `shortcuts.py`

---

### Adding Shortcuts

**File:** `src/exabgp/application/shortcuts.py`

**Process:**
1. Add to `SHORTCUTS` dict:
   ```python
   SHORTCUTS = {
       'x': [
           {
               'expansion': 'my-command',
               'matcher': lambda tokens, pos, prev: pos == 0
           }
       ]
   }
   ```

2. Define matcher function (context rules)
3. Shortcut works in CLI immediately

---

### Adding Completion Metadata

**File:** `src/exabgp/reactor/api/command/registry.py`

**Process:**
1. Add to `OPTION_DESCRIPTIONS`:
   ```python
   OPTION_DESCRIPTIONS = {
       'my-option': 'Description of my option'
   }
   ```

2. Description shows in tab completion automatically

---

## Threading Considerations

### Thread-Safe Components

1. **Socket send** - Protected by `threading.Lock()`
2. **Response queue** - `queue.Queue()` is thread-safe
3. **Completion state** - Single-threaded (readline callback)

### Race Conditions (None)

- Reader thread only writes to queue
- Main thread only reads from queue
- Health monitor uses separate ping/pong flow
- No shared mutable state between threads

---

## Error Handling

### Connection Errors

- **Socket not found** - Print error, exit
- **Connection refused** - Retry up to 5 times
- **Connection lost** - Auto-reconnect
- **Daemon restart** - Health monitor detects, reconnects

### Command Errors

- **Invalid command** - API returns error message, displayed to user
- **Timeout** - Return "Command timed out (5 seconds)"
- **Empty response** - Return empty string (no error)

### Graceful Degradation

- **No color support** - Fall back to plain text
- **rl_replace_line unavailable** - Fall back to normal completion
- **Neighbor fetch fails** - Return empty list (no IPs in completion)

---

## Performance Considerations

### Caching

1. **Neighbor IPs** - 5-minute TTL cache
2. **Command tree** - Built once at startup
3. **Readline history** - Loaded once, saved on exit

### Optimization

1. **Background reader** - Non-blocking I/O
2. **Short timeouts** - 5 seconds for commands
3. **Minimal parsing** - Token-based, no regex in hot path

### Scalability

- **Single CLI instance** - One connection per daemon
- **Command history** - Limited to 1000 lines
- **Response queue** - Unbounded (but fast consumption)

---

## Platform Differences

### macOS (libedit)

- Library: `/usr/lib/libedit.dylib`
- Behavior: Shows completions on first TAB
- Quirk: May show all matches at once

### Linux (GNU readline)

- Library: `libreadline.so`
- Behavior: Needs second TAB to show completions
- Standard: Matches bash behavior

### Windows

- **Not supported** - Unix sockets not available
- **Alternative** - Use WSL or TCP socket (future)

---

## Testing

### Unit Tests

**File:** `tests/unit/test_cli_completion.py`

**Coverage:**
- Shortcut expansion (various contexts)
- Auto-expansion logic
- Completion metadata
- Context detection

### Functional Tests

**Manual testing required:**
- Tab completion in REPL
- Auto-expansion behavior
- Display mode switching
- Connection resilience
- Thread cleanup

---

## Implementation Notes

### Design Decisions

1. **Single-client enforcement** - Prevents command conflicts
   - Uses UUID in ping/pong
   - Daemon rejects second client

2. **Background health monitoring** - Detects daemon restarts
   - 10-second ping interval
   - Non-intrusive (background thread)

3. **Context-aware shortcuts** - Same letter, different meaning
   - `a` → `announce`, `attributes`, or `adj-rib`
   - Reduces typing significantly

4. **Auto-expansion** - Unambiguous prefixes expand automatically
   - `sho<TAB>` → `show`
   - Improves efficiency

5. **Dual display modes** - JSON vs text tables
   - JSON: Machine-readable
   - Text: Human-friendly
   - Preserves JSON structure while improving UX

6. **CLI-to-API transformations** - Accept intuitive syntax
   - `neighbor <ip> show` → `show neighbor <ip>`
   - Improves UX without changing API

### Known Limitations

1. **Platform-specific completion** - macOS vs Linux differ
2. **ctypes dependency** - Required for auto-expansion
3. **Single daemon** - Cannot connect to multiple daemons
4. **Unix sockets only** - No TCP socket support (yet)

---

## See Also

- **CLI_COMMANDS.md** - Complete command reference
- **CLI_SHORTCUTS.md** - Shortcut reference
- **UNIX_SOCKET_API.md** - Socket API protocol
- **`.claude/exabgp/NEIGHBOR_SELECTOR_SYNTAX.md`** - Neighbor selection

---

**Updated:** 2025-12-19
