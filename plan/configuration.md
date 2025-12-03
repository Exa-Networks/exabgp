# ExaBGP Configuration System Improvement Plan

**Generated:** 2025-11-25
**Last Updated:** 2025-12-03
**Status:** Phases 1-3 Complete, Phase 4 In Progress

---

## Executive Summary

This document tracks improvements to ExaBGP's configuration system for better self-documentation and external tool integration.

### ✅ Completion Status

**Phases 1-4: COMPLETE** (as of 2025-12-03)
- ✅ Phase 1: Schema Foundation - Schema types, validators, "did you mean?" suggestions
- ✅ Phase 2: Schema Export - JSON Schema generation via `exabgp schema export`
- ✅ Phase 3: Self-Documentation - Example generation via `exabgp configuration example`
- ✅ Phase 4: Validation Enhancement
  - ✅ 4.1: Multi-error collection (`Error.enable_collection()`)
  - ✅ 4.2: Cross-reference validation (`CrossReferenceValidator`)
  - ✅ 4.3: Centralized constraints (`constraints.py` with all BGP limits)

**Phase 5: FUTURE**
- ⏳ IDE Integration (VS Code extension - optional)

---

## Current State Assessment

### Architecture Overview

The configuration system uses a **hierarchical section-based parser** with a decorator registration pattern:

```
Configuration (configuration.py)
  └── _structure dict defines hierarchy
      ├── process → ParseProcess
      ├── template → neighbor → ParseNeighbor
      └── neighbor → ParseNeighbor
          ├── family → ParseFamily
          ├── capability → ParseCapability
          ├── static → ParseStatic → route → ParseStaticRoute
          ├── flow → ParseFlow → route → ParseFlowRoute
          ├── l2vpn → ParseL2VPN
          └── announce → ParseAnnounce (ip, vpn, flow, etc.)
```

### Existing Self-Documentation Features

| Feature | Location | Status |
|---------|----------|--------|
| `syntax` class var | 10 Section classes | Partial - inconsistent |
| `definition` list | 6 Section classes | Partial - manual sync |
| `known` dict | All Sections | Complete - auto-generated |
| `default` dict | Most Sections | Complete |
| Error messages | Parser functions | Inconsistent quality |

### YANG Infrastructure

| Component | Location | Status |
|-----------|----------|--------|
| YANG Model | `data/exabgp.yang` | Incomplete (482 lines) |
| YANG Parser | `src/exabgp/conf/yang/` | Disabled (commented) |
| IETF Models | `data/models/` | Present (4 files) |
| OpenConfig Models | `data/models/` | Present (4 files) |

**Missing from YANG model:** FlowSpec, EVPN, BGP-LS, MUP, operational, capabilities, add-path, template

---

## Identified Issues

### 1. Self-Documentation Gaps

| Issue | Impact | Example |
|-------|--------|---------|
| No "did you mean?" suggestions | High | `peer-adress` gives generic error |
| Inconsistent error messages | Medium | Some show options, most don't |
| No inline help discovery | High | Users must read source code |
| No example generation | Medium | No way to generate valid configs |
| No deprecation warnings | Low | Old syntax silently accepted |

### 2. Schema/Integration Gaps

| Issue | Impact | Example |
|-------|--------|---------|
| No JSON Schema export | High | IDEs can't validate configs |
| Incomplete YANG model | High | External tools can't consume |
| No OpenAPI spec | Medium | API undocumented formally |
| No config export | Medium | Can't convert to JSON/YAML |

### 3. Validation Gaps

| Issue | Impact | Example |
|-------|--------|---------|
| Single error only | High | Must iterate to find all issues |
| No cross-reference validation | Medium | Invalid process refs not caught early |
| Scattered constraints | Low | Constants defined inline |
| No dry-run mode | Low | Must load to validate |

---

## Recommended Improvements

### Phase 1: Foundation (HIGH Priority)

#### 1.1 Schema Extraction Infrastructure

**New package:** `src/exabgp/schema/`

Create introspection layer to extract metadata from all Section classes:

```python
# src/exabgp/schema/extractor.py
@dataclass
class CommandSchema:
    name: str
    parser_func: str
    type_hint: str  # inferred from parser function name
    default: Any
    required: bool
    choices: Optional[List[str]]
    description: str
    constraints: Optional[str]

@dataclass
class SectionSchema:
    name: str
    syntax: str
    definition: List[str]
    commands: Dict[str, CommandSchema]
    subsections: List[str]
```

**Files to create:**
- `src/exabgp/schema/__init__.py`
- `src/exabgp/schema/extractor.py`
- `src/exabgp/schema/types.py` (parser → type mappings)

#### 1.2 Enhanced Error Messages

**Modify:** `src/exabgp/configuration/core/section.py`

Add "did you mean?" suggestions using Levenshtein distance:

```python
# New helper in section.py or new file core/suggest.py
def find_similar(target: str, candidates: List[str], max_distance: int = 2) -> List[str]:
    """Find similar strings using edit distance."""
    ...

# Modified parse() method (lines 63-67)
if identifier not in self.known:
    simple_options = sorted([k for k in self.known if isinstance(k, str)])
    suggestions = find_similar(command, simple_options)

    msg = f"unknown command '{command}'"
    if suggestions:
        msg += f"\n  Did you mean: {', '.join(suggestions)}?"
    msg += f"\n  Valid options: {', '.join(simple_options)}"

    return self.error.set(msg)
```

**Files to modify:**
- `src/exabgp/configuration/core/section.py`
- `src/exabgp/configuration/core/error.py` (optional: structured errors)

#### 1.3 Improve Parser Error Messages

Apply consistent pattern across all parser functions:

```python
# Pattern: Always show valid alternatives
raise ValueError(
    f'"{value}" is invalid for {field}\n'
    f'  Valid options: {", ".join(valid_options)}\n'
    f'  Constraints: {constraints}'
)
```

**Files to modify:**
- `src/exabgp/configuration/parser.py` (8 functions)
- `src/exabgp/configuration/neighbor/parser.py` (12 functions)
- `src/exabgp/configuration/static/parser.py` (25+ functions)
- `src/exabgp/configuration/capability.py`
- `src/exabgp/configuration/flow/parser.py`

---

### Phase 2: Schema Export (HIGH Priority)

#### 2.1 JSON Schema Generation

**New file:** `src/exabgp/schema/jsonschema.py`

Generate JSON Schema draft-2020-12 from extracted Section metadata:

```python
def generate_json_schema() -> dict:
    """Generate JSON Schema from configuration structure."""
    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://github.com/exa-networks/exabgp/schema/config.json",
        "title": "ExaBGP Configuration",
        "type": "object",
        "properties": {...},
        "$defs": {...}  # Reusable components
    }
    return schema
```

#### 2.2 CLI Export Command

**Modify:** `src/exabgp/application/run.py`

```bash
# New commands
./sbin/exabgp --export-schema json > schema.json
./sbin/exabgp --export-schema yaml > schema.yaml
./sbin/exabgp --export-schema yang > exabgp.yang
```

#### 2.3 Complete YANG Model

**Modify:** `data/exabgp.yang`

Add missing definitions:
- `container capability` - All BGP capabilities
- `container flow` - FlowSpec with match/then
- `list evpn` - EVPN route types
- `container bgp-ls` - BGP-LS
- `container operational` - Operational messages
- `container template` - Reusable neighbor templates

---

### Phase 3: Self-Documentation Enhancement (MEDIUM Priority)

#### 3.1 Command Documentation System

**New file:** `src/exabgp/configuration/core/doc.py`

```python
@dataclass
class CommandDoc:
    name: str
    description: str
    syntax: str
    value_type: str
    default: Optional[str]
    examples: List[str]
    constraints: Optional[str]
    deprecated: bool
    deprecated_message: Optional[str]

def documented(description, syntax, value_type='string', **kwargs):
    """Decorator to attach documentation to parser functions."""
    def decorator(func):
        func._doc = CommandDoc(name=func.__name__, ...)
        return func
    return decorator
```

#### 3.2 Help System

**Modify:** `src/exabgp/configuration/core/section.py`

```python
@classmethod
def get_help(cls, command: str = None) -> str:
    """Get help text for section or specific command."""
    ...

@classmethod
def list_commands(cls) -> List[str]:
    """List all available commands."""
    ...

@classmethod
def generate_example(cls, minimal: bool = True) -> str:
    """Generate example configuration."""
    ...
```

#### 3.3 CLI Help Integration

**Modify:** `src/exabgp/application/validate.py`

```bash
./sbin/exabgp configuration validate --help-config              # List all sections
./sbin/exabgp configuration validate --help-config neighbor     # Show neighbor help
./sbin/exabgp configuration validate --help-config neighbor.hold-time  # Specific command
./sbin/exabgp configuration validate --example neighbor         # Generate example
```

---

### Phase 4: Validation Enhancement (MEDIUM Priority)

#### 4.1 Multi-Error Collection

**Modify:** `src/exabgp/configuration/core/error.py`

```python
class Error:
    _collect_mode: bool = False
    _errors: List[ValidationError] = []
    _max_errors: int = 10

    def enable_collection(self, max_errors: int = 10):
        """Enable multi-error collection mode."""
        ...

    def get_all_errors(self) -> List[ValidationError]:
        """Return all collected errors."""
        ...
```

#### 4.2 Cross-Reference Validation

**New file:** `src/exabgp/configuration/validators.py`

```python
class CrossReferenceValidator:
    """Validate that all references resolve."""

    def register_process(self, name: str, line: int): ...
    def register_template(self, name: str, line: int): ...
    def reference_process(self, name: str, line: int): ...
    def validate(self) -> List[ValidationError]: ...
```

#### 4.3 Centralized Constraints

**New file:** `src/exabgp/configuration/constraints.py`

```python
# BGP Protocol Constraints (RFC 4271)
HOLD_TIME_MIN = 3
HOLD_TIME_MAX = 65535
TTL_MIN = 0
TTL_MAX = 255
ASN_MAX = 4294967295
PORT_MIN = 1
PORT_MAX = 65535

# String Constraints
MD5_PASSWORD_MAX_LENGTH = 80
HOSTNAME_MAX_LENGTH = 255

@dataclass
class NumericConstraint:
    min_val: int
    max_val: int

    def validate(self, value: int) -> bool: ...
    def error_message(self, field: str, value: int) -> str: ...
```

---

### Phase 5: IDE Integration (LOW Priority)

#### 5.1 VS Code Extension

**New directory:** `tools/vscode-exabgp/`

- `package.json` - Extension manifest
- `syntaxes/exabgp.tmLanguage.json` - Syntax highlighting
- `snippets/exabgp.json` - Code snippets
- Uses JSON Schema for validation

#### 5.2 Language Server (Future)

**New package:** `src/exabgp/lsp/`

- Auto-completion from Section metadata
- Real-time validation
- Hover documentation

---

## Implementation Priority Matrix

| Phase | Component | Priority | Effort | Impact |
|-------|-----------|----------|--------|--------|
| 1.1 | Schema extractor | HIGH | 8h | Foundation |
| 1.2 | "Did you mean?" | HIGH | 4h | High UX |
| 1.3 | Error messages | HIGH | 8h | High UX |
| 2.1 | JSON Schema | HIGH | 8h | Tool integration |
| 2.2 | CLI export | HIGH | 4h | Usability |
| 2.3 | Complete YANG | MEDIUM | 16h | Standards |
| 3.1 | Command docs | MEDIUM | 8h | Self-doc |
| 3.2 | Help system | MEDIUM | 6h | Self-doc |
| 3.3 | CLI help | MEDIUM | 4h | Usability |
| 4.1 | Multi-error | MEDIUM | 8h | UX |
| 4.2 | Cross-ref validation | MEDIUM | 6h | Correctness |
| 4.3 | Constraints | LOW | 4h | Consistency |
| 5.1 | VS Code ext | LOW | 16h | IDE support |
| 5.2 | LSP server | LOW | 40h | Advanced IDE |

**Total Estimated Effort:** ~140 hours

---

## Critical Files Reference

### Must Read Before Implementation

1. **`src/exabgp/configuration/configuration.py`** (625 lines)
   - `_structure` dict (lines 174-348) - complete section hierarchy
   - `reload()` - error handling flow
   - `validate()` - post-parse validation

2. **`src/exabgp/configuration/core/section.py`** (113 lines)
   - `Section` base class with `known`, `action`, `default`, `assign`
   - `parse()` method - main parsing logic, error handling
   - `register()` decorator

3. **`src/exabgp/configuration/core/error.py`** (57 lines)
   - `Error` base class with `set()`, `throw()`, `clear()`
   - `ParsingError` and specialized subclasses

4. **`src/exabgp/configuration/neighbor/__init__.py`** (349 lines)
   - Complete Section example with all metadata
   - 24 commands, defaults, validation

5. **`src/exabgp/configuration/static/route.py`** (262 lines)
   - Good `definition` and `syntax` example
   - Pattern for documenting commands

6. **`data/exabgp.yang`** (482 lines)
   - Current incomplete YANG model
   - Structure to extend

7. **`src/exabgp/reactor/api/command/registry.py`**
   - Existing introspection patterns
   - `get_command_metadata()`, `build_command_tree()`

---

## New Files to Create

```
src/exabgp/schema/
├── __init__.py
├── extractor.py      # Schema extraction from Section classes
├── types.py          # Parser function → type mappings
├── jsonschema.py     # JSON Schema generation
├── yang_generator.py # YANG generation (optional)
└── export.py         # Config export to JSON/YAML

src/exabgp/configuration/core/
├── suggest.py        # Levenshtein distance, find_similar
├── doc.py            # CommandDoc, SectionDoc, @documented
└── validation.py     # ValidationError, ValidationResult

src/exabgp/configuration/
├── constraints.py    # Centralized numeric/string constraints
└── validators.py     # Cross-reference validator

tools/vscode-exabgp/  # VS Code extension (future)
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/exabgp/configuration/core/section.py` | Add suggestions, get_help(), generate_example() |
| `src/exabgp/configuration/core/error.py` | Add multi-error collection |
| `src/exabgp/configuration/parser.py` | Improve error messages |
| `src/exabgp/configuration/neighbor/parser.py` | Improve error messages |
| `src/exabgp/configuration/static/parser.py` | Improve error messages |
| `src/exabgp/configuration/capability.py` | Improve error messages |
| `src/exabgp/configuration/flow/parser.py` | Improve error messages |
| `src/exabgp/application/run.py` | Add --export-schema |
| `src/exabgp/application/validate.py` | Add --help-config, --example |
| `data/exabgp.yang` | Complete missing definitions |

---

## Testing Strategy

### Unit Tests

```
tests/unit/schema/
├── test_extractor.py    # Schema extraction
├── test_jsonschema.py   # JSON Schema generation
└── test_types.py        # Type inference

tests/unit/configuration/
├── test_suggest.py      # Levenshtein distance
├── test_validation.py   # Multi-error collection
└── test_constraints.py  # Constraint validation
```

### Integration Tests

- Valid configs with new help system
- Invalid configs with improved errors
- Schema validation against sample configs
- Cross-reference validation

### Regression

- All 72 functional tests must pass
- All existing unit tests must pass

---

## Backward Compatibility

| Change | Compatibility |
|--------|---------------|
| Error message format | Minor - more info, same start |
| New CLI options | Additive - no breakage |
| JSON Schema | New feature |
| YANG completion | Enhancement |
| Multi-error mode | Opt-in |

---

## Open Questions for User

1. **Scope Priority:** Focus on self-documentation first, or schema export first?

2. **YANG Model:** Complete the YANG model to match all features, or maintain a minimal "core" model?

3. **Multi-Error:** Should multi-error mode be default or opt-in via environment variable?

4. **IDE Integration:** Is VS Code extension a priority, or focus on JSON Schema only?

5. **Deprecation System:** Any specific deprecated options to document now?
