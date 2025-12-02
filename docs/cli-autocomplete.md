# CLI Auto-Complete Features

Enhanced auto-complete for the ExaBGP interactive CLI with schema integration, fuzzy matching, and context help.

## Features

### 1. Fuzzy Matching

Complete commands with partial, non-consecutive characters.

**Examples:**
```bash
ExaBGP> sn<TAB>
show neighbor

ExaBGP> ar<TAB>
announce route

ExaBGP> shw<TAB>
show      shutdown
```

**How it works:**
- Query characters must appear in order but don't need to be consecutive
- Exact prefix matches have highest priority
- Subsequence matches ranked by compactness and frequency

**Performance:** <0.2ms P99 latency for 200 candidates

### 2. Schema-Driven Value Validation

Auto-complete validates values using configuration schema types.

**Value Types Supported:**
- IP addresses (IPv4/IPv6)
- AS numbers (2-byte/4-byte)
- Ports (1-65535)
- Communities (standard/extended/large)
- BGP attributes (origin, MED, local-pref)
- Route distinguishers/targets
- And 30+ more types

**Example:**
```bash
ExaBGP> announce route 999.999.999.999<TAB>
ERROR: Invalid IP prefix
Format: <ip>/<prefix> (e.g., 192.0.2.0/24)
```

### 3. Context Help

Press `?` to see syntax hints and examples.

**Example:**
```bash
ExaBGP> announce route 10.0.0.0/24 next-hop ?
  next-hop              Next-hop IP address or "self"
           Syntax: <next-hop>
           Example: 192.0.2.1

  as-path               AS path as list of AS numbers
           Syntax: <as-path>
           Example: [65000]

  origin                BGP origin attribute
           Syntax: IGP|EGP|INCOMPLETE
           Example: igp
```

### 4. Smart Command Ranking

Frequently used commands rank higher in completion results (Phase 5 - when implemented).

**Note:** Command history tracking is planned for future implementation.

---

## Configuration

### Environment Variables

**Fuzzy Matching:**
```bash
# Disable fuzzy matching (exact prefix only)
export exabgp_cli_fuzzy_matching=false

# Enable fuzzy matching (default)
export exabgp_cli_fuzzy_matching=true
```

**Schema Validation:**
```bash
# Disable schema validation
export exabgp_cli_schema_validation=false

# Enable schema validation (default)
export exabgp_cli_schema_validation=true
```

**Command History (Future):**
```bash
# Disable command history tracking
export exabgp_cli_history=false
```

---

## Implementation Details

### Architecture

**Components:**
1. **FuzzyMatcher** (`src/exabgp/cli/fuzzy.py`)
   - Subsequence matching algorithm (O(n) per candidate)
   - Scoring based on: exact prefix, compactness, frequency
   - Limit: Top 10 results

2. **ValueTypeCompletionEngine** (`src/exabgp/cli/schema_bridge.py`)
   - Bridges configuration schema with CLI completion
   - Uses validators from `schema.py` for type checking
   - LRU cache (100 entries) for validation results

3. **CommandCompleter** (`src/exabgp/cli/completer.py`)
   - Integrates fuzzy matching + schema validation
   - Context-aware completion (shortcuts, neighbor IPs, AFI/SAFI)
   - Enhanced display with syntax hints and examples

4. **CLI Command Schema** (`src/exabgp/cli/command_schema.py`)
   - Maps runtime commands to value types
   - Provides descriptions, examples, and validation rules
   - Separate from configuration file schema

### Performance Targets

**Latency Budget:** <100ms total (P99)

**Measured Performance:**
- Fuzzy matching: 0.17ms P99 (200 candidates)
- Schema validation: <10ms (with caching)
- Display rendering: <10ms
- **Total typical:** <30ms

**Optimizations:**
- Validator caching (per ValueType)
- Validation result caching (LRU, 100 entries)
- Early exit on exact matches
- Limit fuzzy results to top 10

---

## Usage Tips

### Quick Navigation

**Use fuzzy matching for speed:**
```bash
sn          → show neighbor
sne         → show neighbor extensive
snj         → show neighbor json
ar          → announce route
wr          → withdraw route
```

### Get Help Inline

**Press `?` after any command:**
```bash
show neighbor ?
announce route 10.0.0.0/24 ?
teardown ?
```

### Validate Before Executing

**See errors during completion:**
```bash
announce route 999.999.999.999<TAB>
# Shows validation error immediately
```

### Exact Match Preference

**Exact prefix always wins:**
```bash
s<TAB>      → show (not shutdown)
sh<TAB>     → show shutdown (both exact)
sho<TAB>    → show (only exact match)
```

---

## Troubleshooting

### Completion Not Working

**Check readline library:**
```bash
python3 -c "import readline; print(readline.__doc__)"
```

Expected: `libedit` (macOS) or `GNU readline` (Linux)

### Slow Completion

**Check candidates count:**
- 200 candidates: ~0.2ms
- 1000+ candidates: May exceed target

**Solution:** Filter candidates before fuzzy matching

### No Context Help

**Verify schema integration:**
```bash
./sbin/exabgp schema export neighbor
```

Should output JSON schema. If empty, schema not loaded.

### Fuzzy Matching Too Aggressive

**Disable fuzzy matching:**
```bash
export exabgp_cli_fuzzy_matching=false
```

---

## Testing

### Unit Tests

```bash
# Test fuzzy matching
uv run pytest tests/unit/cli/test_fuzzy.py

# Test schema bridge
uv run pytest tests/unit/cli/test_schema_bridge.py

# Test completer integration
uv run pytest tests/unit/test_completer.py
```

### Performance Benchmark

```bash
# Run fuzzy matching benchmark
uv run python src/exabgp/cli/fuzzy.py

# Expected output:
# P99: <0.2ms for 200 candidates
```

### Manual Testing

```bash
# Start interactive CLI
./sbin/exabgp cli

# Test fuzzy matching
ExaBGP> sn<TAB>

# Test context help
ExaBGP> announce route 10.0.0.0/24 ?

# Test validation
ExaBGP> announce route invalid<TAB>
```

---

## Development

### Adding New Command Schema

**File:** `src/exabgp/cli/command_schema.py`

```python
CLI_COMMAND_SCHEMA['your-command'] = CLICommandSpec(
    name='your-command',
    description='What the command does',
    arguments={
        'arg1': CLIValueSpec(
            value_type=ValueType.IP_ADDRESS,
            description='IP address argument',
            examples=['192.0.2.1', '2001:db8::1'],
            required=True,
        ),
    },
    options={
        'option1': CLIValueSpec(
            value_type=ValueType.ASN,
            description='Optional AS number',
            examples=['65000'],
            required=False,
        ),
    },
)
```

### Adding New Value Type

**File:** `src/exabgp/configuration/schema.py`

```python
class ValueType(Enum):
    YOUR_TYPE = 'your-type'
```

**File:** `src/exabgp/configuration/validator.py`

```python
class YourTypeValidator(Validator):
    def _parse(self, value: str) -> YourType:
        # Validation logic
        pass
```

### Modifying Fuzzy Matching

**File:** `src/exabgp/cli/fuzzy.py`

**Scoring formula:**
```python
score = 0
if exact_prefix: score += 100        # Highest priority
score += matched_chars * 10          # Subsequence quality
score -= gaps                        # Compactness penalty
score += min(50, frequency * 5)      # Usage bonus (future)
```

---

## Compatibility

**Python:** 3.10+ required
**Platforms:** macOS (libedit), Linux (GNU readline)
**Terminal:** Any ANSI-compatible terminal

**Graceful Degradation:**
- No readline: Completion disabled
- No schema: Basic completion without validation
- Fuzzy disabled: Exact prefix matching only

---

## Future Enhancements

### Phase 5: Command History & Smart Ranking

**Planned features:**
- Track command usage frequency
- Rank by: frequency + recency + success rate
- Privacy: Never store actual IP addresses
- Storage: `~/.local/state/exabgp/cli_history.json` (XDG compliant)
- Opt-out: `exabgp_cli_history=false`

**Expected:**
- Frequently used commands appear first
- Ranking combines fuzzy score + usage statistics
- 90-day automatic cleanup

---

## References

**Related Documentation:**
- `.claude/exabgp/CLI_COMMANDS.md` - Complete command reference
- `.claude/exabgp/CLI_SHORTCUTS.md` - Shortcut reference
- `.claude/exabgp/CLI_IMPLEMENTATION.md` - Internal architecture

**Schema Documentation:**
- `src/exabgp/configuration/schema.py` - ValueType definitions
- `src/exabgp/configuration/validator.py` - Validator implementations
- `src/exabgp/cli/command_schema.py` - CLI command schemas

**Source Files:**
- `src/exabgp/cli/fuzzy.py` - Fuzzy matching engine
- `src/exabgp/cli/schema_bridge.py` - Schema integration
- `src/exabgp/cli/completer.py` - Main completer
- `src/exabgp/application/cli.py` - CLI REPL loop

---

**Last Updated:** 2025-12-02
**Version:** Phase 4 Complete (Phases 1-4 implemented, Phase 5-6 in progress)
