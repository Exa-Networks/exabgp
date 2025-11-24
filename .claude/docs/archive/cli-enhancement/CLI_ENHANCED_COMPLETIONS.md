# CLI Enhanced Completions - One Per Line with Descriptions

**Date:** 2025-11-20
**Status:** ✅ Complete

## Summary

Enhanced CLI tab completion to display ALL options one per line with descriptive information:
- Commands show their purpose/explanation
- Neighbor IPs show AS number and state
- Options show what they do
- Keywords show their meaning

## Implementation Details

### 1. Display Format Change

**Before (compact columns):**
```
show      shutdown  silence-ack
neighbor  route     eor
```

**After (one per line with descriptions):**
```
show         Display information about neighbors, routes, or configuration
shutdown     Gracefully shutdown neighbor connection
silence-ack  Control silence acknowledgments
neighbor     Target specific neighbor by IP
route        Route specification parameter
eor          Send End-of-RIB marker
```

### 2. Neighbor IP Descriptions

**Example:**
```
10.0.0.1     (neighbor, AS65000, ESTABLISHED)
10.0.0.2     (neighbor, AS65001, IDLE)
10.0.0.3     (neighbor, AS65002, ACTIVE)
```

### 3. Color Coding

- **Yellow** - Commands (show, announce, etc.)
- **Cyan** - Neighbor IPs
- **Green** - Options and keywords
- **Dim** - Descriptions (secondary text)

### 4. Code Changes

#### src/exabgp/application/cli.py

**Display logic (`_display_matches_and_redraw`):**
- Removed compact column layout fallback
- Always display one item per line
- Color code by item type (command/neighbor/option/keyword)
- Show descriptions next to each item

**Completion metadata (`_get_completions` and helpers):**
- Base commands: Use `registry.get_command_description()`
- Subcommands: Build full command path for lookup
- Options: Use `registry.get_option_description()`
- Neighbor IPs: Fetch AS and state from `show neighbor json`
- AFI/SAFI: Add contextual descriptions
- Route keywords: Add explanatory descriptions

#### src/exabgp/reactor/api/command/registry.py

**New method (`get_command_description`):**
- Looks up command description from metadata
- Provides fallback descriptions for base commands
- Supports full command paths (e.g., "show neighbor")

**Enhanced option descriptions (`OPTION_DESCRIPTIONS`):**
- Added 12 new option descriptions
- Covers common BGP terms (ipv4, ipv6, unicast, vpn, etc.)
- Explains technical terms (MED, AS path, local-preference)

## Features

### Comprehensive Descriptions

Every completion type gets a description:

1. **Commands:**
   - Base commands: "Display information...", "Announce a route..."
   - Subcommands: From registry metadata or default descriptions

2. **Neighbor IPs:**
   - Format: `(neighbor, AS{number}, {state})`
   - Fetched via `show neighbor json` with caching
   - Fallback: `(neighbor)` if data unavailable

3. **Options:**
   - `summary` → "Brief neighbor status"
   - `extensive` → "Detailed neighbor information"
   - `json` → "JSON-formatted output"
   - `in` → "Adj-RIB-In (received routes)"

4. **AFI/SAFI:**
   - AFI: "Address Family Identifier"
   - SAFI: "SAFI for {afi}" (context-aware)

5. **Keywords:**
   - Route parameters: "Route specification parameter"
   - Filters: Uses option descriptions

### Visual Hierarchy

```
command      Description in normal weight
  ↑               ↑
Yellow          Dim (secondary)

10.0.0.1     (neighbor, AS65000, ESTABLISHED)
  ↑               ↑
Cyan            Dim

option       Brief description
  ↑               ↑
Green           Dim
```

### Context-Aware

Descriptions adapt to context:
- "n" after "show" → `neighbor` with description
- Same commands in different contexts get appropriate descriptions
- Full command paths resolved for accurate descriptions

## Testing

✅ **All tests passing:**
- Linting: ruff clean
- Unit tests: 1644/1644
- Functional: 72/72 encoding tests (100%)

No new tests added (display is visual feature, tested manually)

## Benefits

1. **Self-documenting CLI** - Users see what options do without consulting docs
2. **Better neighbor identification** - See AS and state at a glance
3. **Reduced errors** - Clear descriptions prevent wrong option selection
4. **Faster workflow** - Don't need to look up what options mean
5. **Consistent format** - Every completion has context

## Technical Details

### Description Sources

1. **Commands:**
   - `CommandMetadata.description` from registry
   - Fallback: Hardcoded descriptions in `get_command_description()`

2. **Options:**
   - `OPTION_DESCRIPTIONS` dict in registry

3. **Neighbors:**
   - Live data from `show neighbor json` command
   - Cached for 5 minutes to avoid repeated socket calls

4. **AFI/SAFI:**
   - Generated descriptions based on type
   - Context-aware for SAFI values

### Performance

- **Neighbor data caching:** 5-minute TTL, prevents repeated socket calls
- **Single pass display:** No multiple rendering passes
- **Minimal overhead:** Description lookup is O(1) dict access

### Graceful Degradation

- If command description not found → No description shown
- If neighbor data unavailable → Fallback to `(neighbor)`
- If option description missing → No description shown
- Never crashes or blocks on missing data

## Files Modified

- `src/exabgp/application/cli.py` (+150 lines)
  - `_display_matches_and_redraw()` - Always one-per-line display
  - `_get_completions()` - Add descriptions for base commands
  - `_complete_neighbor_filters()` - Add descriptions for filters
  - `_complete_afi_safi()` - Add descriptions for AFI/SAFI
  - `_complete_route_spec()` - Add descriptions for route keywords
  - Subcommand loops - Build full paths for description lookup

- `src/exabgp/reactor/api/command/registry.py` (+24 lines)
  - `get_command_description()` - New method for command descriptions
  - `OPTION_DESCRIPTIONS` - Added 12 new option descriptions
  - Base command fallback descriptions

## Integration

Works seamlessly with existing features:
- Auto-expansion (expands tokens, then shows descriptions)
- JSON pretty-printing (commands that return JSON)
- Neighbor IP completion (now with AS and state info)
- Command shortcuts (expanded before description lookup)
- Color support (adapts to terminal capabilities)

## Examples

### Base Command Completion

```
ExaBGP> s<TAB>

show         Display information about neighbors, routes, or configuration
shutdown     Gracefully shutdown neighbor connection
silence-ack  Control silence acknowledgments
```

### Subcommand Completion

```
ExaBGP> show n<TAB>

neighbor     Target specific neighbor by IP
```

### Option Completion with Neighbors

```
ExaBGP> show neighbor <TAB>

summary          Brief neighbor status
extensive        Detailed neighbor information
configuration    Show neighbor configuration
json             JSON-formatted output
10.0.0.1         (neighbor, AS65000, ESTABLISHED)
10.0.0.2         (neighbor, AS65001, IDLE)
```

### AFI/SAFI Completion

```
ExaBGP> eor <TAB>

ipv4     Address Family Identifier
ipv6     Address Family Identifier

ExaBGP> eor ipv4 <TAB>

unicast      SAFI for ipv4
multicast    SAFI for ipv4
vpn          SAFI for ipv4
```

## Future Enhancements

1. **More detailed descriptions** - Add descriptions for all commands
2. **Dynamic neighbor info** - Show route counts, uptime
3. **Syntax hints** - Show expected parameter format
4. **Command examples** - Show usage examples inline
5. **Search/filter** - Type to filter long lists

## Related Documentation

- `.claude/CLI_AUTO_EXPANSION_IMPLEMENTATION.md` - Auto-expansion feature
- `src/exabgp/reactor/api/command/registry.py` - Command metadata
- `src/exabgp/application/cli.py` - CLI implementation
