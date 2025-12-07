# Plan: NLRI Immutability Refactoring

**Status:** Planning
**Priority:** 🔴 High
**Goal:** Enable NLRI immutability by removing all mutation after construction

---

## Overview

Currently, NLRI objects are mutated after creation in configuration parsing:
1. **VPLS:** `make_empty()` creates empty NLRI, fields assigned via `assign()`
2. **Static routes:** `from_cidr()` creates NLRI, then `labels`, `rd`, `path_info`, `nexthop` mutated directly

This blocks the packed-bytes-first pattern which requires immutability.

**Solution:** Deferred construction - collect all values during parsing, create NLRI once at the end.

---

## Current Mutation Points

### 1. RouteBuilderValidator (validator.py:1141)
```python
# nlri-set action
route.nlri.assign(field_name, value)
```
**Used by:** VPLS, FlowSpec attribute commands

### 2. TypeSelectorValidator (validator.py:1272)
```python
# nlri-set action
route.nlri.assign(field_name, value)
```
**Used by:** MUP, MVPN routes

### 3. Static route parsing (static/__init__.py)
```python
# Direct mutation
nlri.labels = label(tokeniser)
nlri.rd = route_distinguisher(tokeniser)
nlri.path_info = path_information(tokeniser)
nlri.nexthop = nexthop

# Via assign()
nlri.assign(field_name, value)
```
**Used by:** All IP/Label/VPN routes in static config

### 4. Scope.nlri_assign (core/scope.py:116)
```python
self.get_route().nlri.assign(command, data)
```
**Used by:** Legacy configuration sections

---

## Refactoring Phases

### Phase 1: Infrastructure
Add deferred construction support without breaking existing code.

#### 1.1 Add `required_fields` to RouteBuilder schema
```python
@dataclass
class RouteBuilder(Container):
    nlri_factory: Callable[..., Any] | None = None
    required_fields: set[str] = field(default_factory=set)  # NEW
```

#### 1.2 Create Settings classes for each NLRI type

Each NLRI type gets a dataclass that validates fields during collection:

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass
class VPLSSettings:
    """Settings for VPLS NLRI construction. Validates during assignment."""

    rd: RouteDistinguisher | None = None
    endpoint: int | None = None
    base: int | None = None
    offset: int | None = None
    size: int | None = None
    nexthop: IP = field(default_factory=lambda: IP.NoNextHop)
    action: Action = Action.ANNOUNCE

    def set(self, name: str, value: Any) -> None:
        """Set field with validation."""
        if name == 'endpoint':
            if not isinstance(value, int) or value < 0 or value > 65535:
                raise ValueError(f'endpoint must be 0-65535, got {value}')
        elif name == 'base':
            if not isinstance(value, int) or value < 0 or value > 0xFFFFF:
                raise ValueError(f'base must be 0-1048575, got {value}')
        # ... more validation
        setattr(self, name, value)

    def validate(self) -> str:
        """Return error message if invalid, empty string if valid."""
        if self.rd is None:
            return 'vpls nlri route-distinguisher missing'
        if self.endpoint is None:
            return 'vpls nlri endpoint missing'
        if self.base is None:
            return 'vpls nlri base missing'
        if self.offset is None:
            return 'vpls nlri offset missing'
        if self.size is None:
            return 'vpls nlri size missing'
        if self.base > (0xFFFFF - self.size):
            return 'vpls nlri size inconsistency'
        return ''


@dataclass
class INETSettings:
    """Settings for INET/Label/IPVPN NLRI construction."""

    cidr: CIDR | None = None
    afi: AFI | None = None
    safi: SAFI | None = None
    action: Action = Action.ANNOUNCE
    nexthop: IP = field(default_factory=lambda: IP.NoNextHop)
    path_info: PathInfo = field(default_factory=lambda: PathInfo.DISABLED)
    labels: Labels | None = None  # Label/IPVPN only
    rd: RouteDistinguisher | None = None  # IPVPN only

    def set(self, name: str, value: Any) -> None:
        """Set field with validation."""
        setattr(self, name, value)

    def validate(self) -> str:
        """Return error message if invalid, empty string if valid."""
        if self.cidr is None:
            return 'route prefix missing'
        if self.afi is None:
            return 'route afi missing'
        if self.safi is None:
            return 'route safi missing'
        return ''


@dataclass
class FlowSettings:
    """Settings for FlowSpec NLRI construction."""

    afi: AFI | None = None
    safi: SAFI | None = None
    action: Action = Action.ANNOUNCE
    rules: list[Any] = field(default_factory=list)

    def add_rule(self, rule: Any) -> None:
        """Add a FlowSpec rule."""
        self.rules.append(rule)

    def validate(self) -> str:
        if self.afi is None:
            return 'flowspec afi missing'
        if not self.rules:
            return 'flowspec has no rules'
        return ''
```

#### 1.3 Add factory @classmethod to NLRI classes

Factory methods take Settings objects and are @classmethods of the NLRI class:

**VPLS:**
```python
@classmethod
def from_settings(cls, settings: VPLSSettings) -> 'VPLS':
    """Create VPLS NLRI from validated settings.

    Args:
        settings: VPLSSettings with all required fields set

    Returns:
        Immutable VPLS NLRI instance

    Raises:
        ValueError: If settings validation fails
    """
    error = settings.validate()
    if error:
        raise ValueError(error)

    packed = (
        b'\x00\x11'
        + settings.rd.pack_rd()
        + pack('!HHH', settings.endpoint, settings.offset, settings.size)
        + pack('!L', (settings.base << 4) | 0x1)[1:]
    )
    instance = cls(packed)
    instance.action = settings.action
    instance.nexthop = settings.nexthop
    return instance
```

**INET:**
```python
@classmethod
def from_settings(cls, settings: INETSettings) -> 'INET':
    """Create INET NLRI from validated settings."""
    error = settings.validate()
    if error:
        raise ValueError(error)

    # Build packed bytes from settings
    instance = cls.from_cidr(
        settings.cidr,
        settings.afi,
        settings.safi,
        settings.action,
        settings.path_info,
    )
    instance.nexthop = settings.nexthop
    return instance
```

**Label/IPVPN** - similar pattern, handling labels/rd fields.

**Flow:**
```python
@classmethod
def from_settings(cls, settings: FlowSettings) -> 'Flow':
    """Create FlowSpec NLRI from validated settings."""
    error = settings.validate()
    if error:
        raise ValueError(error)

    instance = cls(settings.afi, settings.safi, settings.action)
    for rule in settings.rules:
        instance._add_rule(rule)
    instance._finalize()  # Compute packed bytes
    return instance
```

---

### Phase 2: RouteBuilderValidator Refactoring

#### 2.1 Update RouteBuilder schema to include settings_class

```python
@dataclass
class RouteBuilder(Container):
    nlri_class: type | None = None  # The NLRI class (has from_settings)
    settings_class: type | None = None  # The Settings dataclass
    prefix_parser: Callable[..., Any] | None = None
    assign: dict[str, str] = field(default_factory=dict)
```

#### 2.2 Update validate() to use Settings class

```python
def validate(self, tokeniser: 'Tokeniser') -> list[Any]:
    if self.schema.settings_class is None:
        raise ValueError('No settings class configured')
    if self.schema.nlri_class is None:
        raise ValueError('No NLRI class configured')

    # Create settings instance
    settings = self.schema.settings_class()
    settings.action = self.action_type
    attributes = AttributeCollection()

    # Parse prefix if present
    if self.schema.prefix_parser:
        ipmask = self.schema.prefix_parser(tokeniser)
        settings.cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)
        settings.afi = self.afi
        settings.safi = self.safi

    # Parse all tokens - collect into settings
    while True:
        command = tokeniser()
        if not command:
            break

        child = self.schema.children.get(command)
        if child is None:
            raise ValueError(f"Unknown command '{command}'")

        value = child.get_validator().validate(tokeniser)

        if child.action == 'nlri-set':
            field_name = self.schema.assign.get(command, command)
            settings.set(field_name, value)  # Validates during set
        elif child.action == 'nlri-add':
            settings.add_rule(value)  # For FlowSpec
        elif child.action == 'attribute-add':
            attributes.add(value)
        elif child.action == 'nexthop-and-attribute':
            ip, attr = value
            if ip:
                settings.nexthop = ip
            if attr:
                attributes.add(attr)

    # Create NLRI from validated settings
    nlri = self.schema.nlri_class.from_settings(settings)

    return [Route(nlri, attributes)]
```

#### 2.3 Update VPLS schema

```python
class AnnounceVPLS(ParseAnnounce):
    schema = RouteBuilder(
        description='VPLS route announcement',
        nlri_class=VPLS,
        settings_class=VPLSSettings,
        prefix_parser=None,  # VPLS has no prefix
        assign={
            'rd': 'rd',
            'endpoint': 'endpoint',
            'offset': 'offset',
            'size': 'size',
            'base': 'base',
        },
        children={...},
    )
```

---

### Phase 3: Static Route Refactoring

#### 3.1 Update route() function to use Settings

```python
@ParseStatic.register('route', 'append-route')
def route(tokeniser: Any) -> list[Route]:
    nlri_action = Action.ANNOUNCE if tokeniser.announce else Action.WITHDRAW
    ipmask = prefix(tokeniser)

    # Create settings and populate initial values
    settings = INETSettings()
    settings.cidr = CIDR.make_cidr(ipmask.pack_ip(), ipmask.mask)
    settings.afi = IP.toafi(ipmask.top())
    settings.action = nlri_action
    attributes = AttributeCollection()

    # Determine NLRI class from tokens
    has_rd = 'rd' in tokeniser.tokens or 'route-distinguisher' in tokeniser.tokens
    has_label = 'label' in tokeniser.tokens

    if has_rd:
        nlri_class = IPVPN
        settings.safi = SAFI.mpls_vpn
        check = AnnounceVPN.check
    elif has_label:
        nlri_class = Label
        settings.safi = SAFI.nlri_mpls
        check = AnnounceLabel.check
    else:
        nlri_class = INET
        settings.safi = IP.tosafi(ipmask.top())
        check = AnnouncePath.check

    # Parse all tokens - collect into settings
    while True:
        command = tokeniser()
        if not command:
            break

        if command == 'label':
            settings.labels = label(tokeniser)
        elif command in ('rd', 'route-distinguisher'):
            settings.rd = route_distinguisher(tokeniser)
        elif command == 'path-information':
            settings.path_info = path_information(tokeniser)
        else:
            cmd_action = ParseStatic.action.get(command, '')
            if cmd_action == 'attribute-add':
                attributes.add(ParseStatic.known[command](tokeniser))
            elif cmd_action == 'nexthop-and-attribute':
                nexthop, attr = ParseStatic.known[command](tokeniser)
                settings.nexthop = nexthop
                attributes.add(attr)

    # Create NLRI from validated settings
    nlri = nlri_class.from_settings(settings)
    static_route = Route(nlri, attributes)

    if not check(static_route, nlri.afi):
        raise ValueError('invalid route')

    return list(ParseStatic.split(static_route))
```

---

### Phase 4: TypeSelectorValidator Refactoring

Similar to RouteBuilderValidator - collect values, create at end.

---

### Phase 5: Remove Mutation Support

After all parsers use deferred construction:

#### 5.1 Remove from NLRI classes
- Remove `assign()` method from base NLRI
- Remove `make_empty()` from VPLS
- Remove builder mode storage (`_rd`, `_endpoint`, etc.)
- Remove property setters
- Simplify property getters (no conditionals)

#### 5.2 Remove from Scope
- Remove `nlri_assign()` method
- Update any remaining callers

#### 5.3 Update `_pack_nlri_simple()`
```python
def _pack_nlri_simple(self) -> Buffer:
    return self._packed  # Just return stored bytes
```

---

## Implementation Order

```
Phase 1: Infrastructure (non-breaking)
├── 1.1 Add required_fields to RouteBuilder
├── 1.2 Create NLRIBuilder helper (optional)
└── 1.3 Add make_xxx() factory methods to NLRI classes

Phase 2: RouteBuilderValidator
├── 2.1 Update validate() to collect-then-create
├── 2.2 Update VPLS schema to use make_vpls
├── 2.3 Update FlowSpec schema
└── 2.4 Test VPLS and FlowSpec

Phase 3: Static Routes
├── 3.1 Add make_inet/make_label/make_ipvpn factories
├── 3.2 Update route() function
├── 3.3 Update attributes() function
└── 3.4 Test static routes

Phase 4: TypeSelectorValidator
├── 4.1 Update validate() for MUP/MVPN
└── 4.2 Test MUP and MVPN routes

Phase 5: Remove Mutation (breaking)
├── 5.1 Remove assign() from NLRI
├── 5.2 Remove make_empty() from VPLS
├── 5.3 Remove builder mode storage
├── 5.4 Simplify properties
└── 5.5 Final testing
```

---

## Files to Modify

### Phase 1
- `src/exabgp/configuration/schema.py` - Add required_fields
- `src/exabgp/bgp/message/update/nlri/vpls.py` - Add make_vpls kwargs
- `src/exabgp/bgp/message/update/nlri/inet.py` - Add make_inet
- `src/exabgp/bgp/message/update/nlri/label.py` - Add make_label
- `src/exabgp/bgp/message/update/nlri/ipvpn.py` - Add make_ipvpn
- `src/exabgp/bgp/message/update/nlri/flow.py` - Add make_flow

### Phase 2
- `src/exabgp/configuration/validator.py` - RouteBuilderValidator
- `src/exabgp/configuration/announce/vpls.py` - Use make_vpls
- `src/exabgp/configuration/l2vpn/vpls.py` - Use make_vpls
- `src/exabgp/configuration/announce/flow.py` - Use make_flow

### Phase 3
- `src/exabgp/configuration/static/__init__.py` - route(), attributes()
- `src/exabgp/configuration/static/route.py` - ParseStaticRoute

### Phase 4
- `src/exabgp/configuration/validator.py` - TypeSelectorValidator

### Phase 5
- `src/exabgp/bgp/message/update/nlri/nlri.py` - Remove assign()
- `src/exabgp/bgp/message/update/nlri/vpls.py` - Remove builder mode
- `src/exabgp/configuration/core/scope.py` - Remove nlri_assign()

---

## Testing Strategy

**CRITICAL:** Follow `.claude/TESTING_BEFORE_REFACTORING_PROTOCOL.md`

### Before Each Phase

0. **Verify RFC documentation exists**
   ```bash
   # Check if wire format is documented
   grep -n "RFC\|wire format\|Wire format" src/exabgp/bgp/message/update/nlri/<module>.py
   ```
   If NOT documented: Read RFC, add wire format diagram to code BEFORE changes.

1. **Identify affected code** - list files, functions, classes
2. **Find existing tests:**
   ```bash
   grep -rn "test.*VPLS\|test.*vpls" tests/
   grep -rn "test.*RouteBuilder" tests/
   grep -rn "test.*static.*route" tests/
   ```
3. **Run and record baseline:**
   ```bash
   env exabgp_log_enable=false uv run pytest tests/unit/test_vpls.py -v 2>&1 | tee /tmp/baseline.txt
   ```
4. **Assess coverage** - add tests if needed BEFORE refactoring
5. **Verify new tests pass** with current code

### After Each Phase

```bash
# Unit tests
env exabgp_log_enable=false uv run pytest tests/unit/ -v

# Functional tests
./qa/bin/functional encoding
./qa/bin/functional decoding

# Full suite
./qa/bin/test_everything
```

### Test Coverage Requirements

Before refactoring each component, ensure tests exist for:

**VPLS:**
- [ ] `test_vpls.py` covers `make_vpls()`, `make_empty()`, pack/unpack
- [ ] Configuration parsing tests exist

**RouteBuilderValidator:**
- [ ] Tests for `nlri-set` action
- [ ] Tests for `nlri-add` action (FlowSpec)
- [ ] Tests for `nexthop-and-attribute` action

**Static Routes:**
- [ ] Tests for route with labels
- [ ] Tests for route with rd
- [ ] Tests for route with path-information
- [ ] Tests for INET/Label/IPVPN type selection

**TypeSelectorValidator:**
- [ ] Tests for MUP routes
- [ ] Tests for MVPN routes

---

## Rollback Strategy

Each phase is independently deployable:
- Phase 1: Pure additions, no behavior change
- Phase 2-4: Can keep old code path with feature flag
- Phase 5: Point of no return - ensure full test coverage first

---

## Success Criteria

1. All configuration parsing works without NLRI mutation
2. `assign()` method removed from NLRI base class
3. `make_empty()` removed from all NLRI classes
4. All properties are simple returns (no conditionals)
5. `_pack_nlri_simple()` just returns `self._packed`
6. All tests pass

---

## Progress Log

### 2025-12-07 - Phase 1.2/1.3 Partial: VPLSSettings and from_settings()

**Completed:**
- ✅ Created `VPLSSettings` dataclass in `src/exabgp/bgp/message/update/nlri/settings.py`
  - Validation during assignment (`set()` method)
  - Final validation before NLRI creation (`validate()` method)
- ✅ Added `VPLS.from_settings()` factory method in `src/exabgp/bgp/message/update/nlri/vpls.py`
  - Validates settings
  - Delegates to `make_vpls()` for packed bytes creation
- ✅ Created 18 unit tests in `tests/unit/test_nlri_settings.py`
- ✅ All tests pass (11 suites, 42.6s)

**Files added:**
- `src/exabgp/bgp/message/update/nlri/settings.py` - VPLSSettings dataclass
- `tests/unit/test_nlri_settings.py` - 18 tests for Settings and from_settings()

**Files modified:**
- `src/exabgp/bgp/message/update/nlri/vpls.py` - Added from_settings() method

**Resume Point:**
- ~~Phase 1 continues: Add INETSettings, FlowSettings dataclasses~~
- ~~Then add from_settings() to INET, Label, IPVPN, Flow classes~~

### 2025-12-07 - Phase 1.2/1.3 Continued: INETSettings and INET.from_settings()

**Completed:**
- ✅ Created `INETSettings` dataclass in `src/exabgp/bgp/message/update/nlri/settings.py`
  - Handles INET, Label, and IPVPN (with optional labels/rd fields)
  - Validation during assignment (`set()` method)
  - Final validation before NLRI creation (`validate()` method)
- ✅ Added `INET.from_settings()` factory method in `src/exabgp/bgp/message/update/nlri/inet.py`
  - Validates settings
  - Delegates to `from_cidr()` for instance creation
- ✅ Created 14 additional unit tests for INETSettings/INET.from_settings()
- ✅ All tests pass (11 suites, 42.9s)

**Files modified:**
- `src/exabgp/bgp/message/update/nlri/settings.py` - Added INETSettings dataclass
- `src/exabgp/bgp/message/update/nlri/inet.py` - Added from_settings() method
- `tests/unit/test_nlri_settings.py` - Added 14 tests (32 total)

**Resume Point:**
- ~~Phase 1 continues: Add FlowSettings dataclass~~
- ~~Add from_settings() to Label, IPVPN, Flow classes~~
- ~~Consider if Label/IPVPN need their own Settings classes or can reuse INETSettings~~

### 2025-12-07 - Phase 1.3 Continued: Label and IPVPN from_settings()

**Completed:**
- ✅ Added `Label.from_settings()` factory method in `src/exabgp/bgp/message/update/nlri/label.py`
  - Reuses `INETSettings` dataclass (with labels field)
  - Sets labels from settings after instance creation
- ✅ Added `IPVPN.from_settings()` factory method in `src/exabgp/bgp/message/update/nlri/ipvpn.py`
  - Reuses `INETSettings` dataclass (with labels + rd fields)
  - Sets both labels and rd from settings after instance creation
- ✅ Created 8 additional unit tests for Label/IPVPN from_settings()
- ✅ All tests pass (11 suites, 43.0s)

**Files modified:**
- `src/exabgp/bgp/message/update/nlri/label.py` - Added from_settings() method
- `src/exabgp/bgp/message/update/nlri/ipvpn.py` - Added from_settings() method
- `tests/unit/test_nlri_settings.py` - Added 8 tests (40 total)

**Phase 1 Summary:**

| Component | Settings Class | from_settings() | Tests |
|-----------|---------------|-----------------|-------|
| VPLS | VPLSSettings ✅ | VPLS.from_settings() ✅ | 18 |
| INET | INETSettings ✅ | INET.from_settings() ✅ | 14 |
| Label | (reuses INETSettings) | Label.from_settings() ✅ | 4 |
| IPVPN | (reuses INETSettings) | IPVPN.from_settings() ✅ | 4 |
| Flow | FlowSettings ✅ | Flow.from_settings() ✅ | 7 |

**Phase 1 COMPLETE!**

### 2025-12-07 - Phase 1.4: FlowSettings and Flow.from_settings()

**Completed:**
- ✅ Created `FlowSettings` dataclass in `src/exabgp/bgp/message/update/nlri/settings.py`
- ✅ Added `Flow.from_settings()` factory method in `src/exabgp/bgp/message/update/nlri/flow.py`
  - Sets rules from settings
  - Marks packed as stale for recomputation
- ✅ Created 7 additional unit tests including wire format verification
  - `test_from_settings_pack_matches_expected` - verifies single rule packing
  - `test_from_settings_pack_multiple_rules` - verifies complex multi-rule packing
- ✅ All tests pass (11 suites, 46.3s)

**Files modified:**
- `src/exabgp/bgp/message/update/nlri/settings.py` - Added FlowSettings dataclass
- `src/exabgp/bgp/message/update/nlri/flow.py` - Added from_settings() method
- `tests/unit/test_nlri_settings.py` - Added 7 tests (52 total)

**Resume Point:**
- ~~Phase 1 COMPLETE - all Settings classes and from_settings() methods implemented~~
- ~~Next: Phase 2 - Update RouteBuilderValidator to use Settings pattern~~

### 2025-12-07 - Phase 2: RouteBuilderValidator Refactoring

**Completed:**
- ✅ Added `nlri_class` and `settings_class` fields to `RouteBuilder` dataclass in `schema.py`
  - Supports two modes: legacy (nlri_factory) and settings (nlri_class + settings_class)
- ✅ Updated `RouteBuilderValidator` in `validator.py` with new `_validate_with_settings()` method
  - Creates Settings instance at start
  - Collects values via `settings.set()` for `nlri-set` action
  - Creates immutable NLRI via `from_settings()` at end
  - Legacy path preserved in `_validate_legacy()` for backwards compatibility
- ✅ Updated `AnnounceVPLS.schema` to use settings mode:
  - `nlri_class=VPLS`
  - `settings_class=VPLSSettings`
  - Removed `nlri_factory=_vpls_factory`
- ✅ All tests pass (11 suites, 44.4s)

**Files modified:**
- `src/exabgp/configuration/schema.py` - Added nlri_class, settings_class fields to RouteBuilder
- `src/exabgp/configuration/validator.py` - Added _validate_with_settings(), _apply_settings_action()
- `src/exabgp/configuration/announce/vpls.py` - Updated schema to use settings mode

**Phase 2 Summary:**

| Component | Status |
|-----------|--------|
| RouteBuilder schema | ✅ Updated with nlri_class, settings_class |
| RouteBuilderValidator | ✅ Supports both legacy and settings modes |
| VPLS announce config | ✅ Uses settings mode (no mutation) |

**Phase 2 COMPLETE!**

**Resume Point:**
- ~~Phase 3: Update other configuration parsers (static routes, FlowSpec, etc.)~~
- ~~Then Phase 4: TypeSelectorValidator for MUP/MVPN~~
- ~~Then Phase 5: Remove mutation support from NLRI classes~~

### 2025-12-07 - Phase 3: Static Route Refactoring

**Completed:**
- ✅ Updated `route()` function in `static/__init__.py` to use Settings pattern
  - Creates `INETSettings` at start with initial values
  - Collects values during parsing (labels, rd, path_info, nexthop)
  - Determines NLRI class (INET/Label/IPVPN) based on token look-ahead
  - Creates immutable NLRI via `from_settings()` at end
- ✅ Updated `attributes()` function in `static/__init__.py` to use Settings pattern
  - Creates template `INETSettings` with shared attributes
  - Copies template for each NLRI prefix in the loop
  - Creates immutable NLRI via `from_settings()` for each
- ✅ All tests pass (11 suites, 43.5s)

**Files modified:**
- `src/exabgp/configuration/static/__init__.py` - Updated route() and attributes() functions

**Phase 3 Summary:**

| Component | Status |
|-----------|--------|
| route() function | ✅ Uses INETSettings + from_settings() |
| attributes() function | ✅ Uses INETSettings + from_settings() |
| Static route parsing | ✅ No mutation after NLRI creation |

**Phase 3 COMPLETE!**

**Resume Point:**
- ~~Phase 4: TypeSelectorValidator for MUP/MVPN (if needed)~~
- Phase 5: Remove mutation support from NLRI classes

### 2025-12-07 - Phase 4: TypeSelectorValidator Cleanup

**Analysis:**
TypeSelectorValidator uses factory mode - factories create complete NLRIs directly.
This differs from RouteBuilder where NLRI is built incrementally.

Key findings:
- MUP factories (srv6_mup_isd, etc.) create fully-constructed NLRIs
- MVPN factories similarly create complete NLRIs
- MUP schema had broken `label` field with `nlri-set` action - MUP NLRI has no label slot
- Per draft-mpmz-bess-mup-safi: MPLS labels are carried via Extended Community, NOT in NLRI

**Completed:**
- ✅ Removed broken `label` field from MUP schema (was using `nlri-set` but MUP has no label)
- ✅ Added `settings_class` and `assign` fields to TypeSelectorBuilder (for future use)
- ✅ Updated TypeSelectorValidator to remove unsupported `nlri-set` action
- ✅ Added documentation to `mup/__init__.py` explaining MUP NLRI format and label handling
- ✅ All tests pass (11 suites, 43.7s)

**Files modified:**
- `src/exabgp/configuration/announce/mup.py` - Removed broken label field
- `src/exabgp/configuration/schema.py` - Added settings_class, assign to TypeSelectorBuilder
- `src/exabgp/configuration/validator.py` - Removed nlri-set from TypeSelectorValidator
- `src/exabgp/bgp/message/update/nlri/mup/__init__.py` - Added MUP format documentation

**Phase 4 Summary:**

| Component | Status | Notes |
|-----------|--------|-------|
| MUP schema | ✅ Fixed | Removed broken label nlri-set |
| TypeSelectorBuilder | ✅ Updated | Added settings_class for future |
| TypeSelectorValidator | ✅ Cleaned | No nlri-set support (factories create complete NLRIs) |
| MUP documentation | ✅ Added | NLRI format and label handling |

**Phase 4 COMPLETE!**

**Resume Point:**
- ~~Phase 5: Remove mutation support from NLRI classes~~

### 2025-12-07 - Phase 5: Deprecate Mutation (Partial)

**Analysis:**
Full removal of mutation requires updating many configuration paths:
- `l2vpn/vpls.py` Section parser still uses block syntax with `make_empty()` + `assign()`
- `announce/path.py`, `announce/vpn.py`, `announce/label.py` use `nlri-set` with legacy mode
- `static/route.py`, `flow/route.py` Section parsers use `nlri-set`

**Completed:**
- ✅ Updated `l2vpn/vpls.py` schema to use Settings mode (nlri_class + settings_class)
- ✅ Marked `VPLS.make_empty()` as DEPRECATED in docstring
- ✅ Marked `VPLS.assign()` as DEPRECATED in docstring
- ✅ All tests pass (11 suites, 43.5s)

**Files modified:**
- `src/exabgp/configuration/l2vpn/vpls.py` - Updated schema to use Settings mode
- `src/exabgp/bgp/message/update/nlri/vpls.py` - Added deprecation docs to make_empty() and assign()

**What Still Uses Mutation:**
1. Block syntax `vpls site5 { ... }` via `ParseVPLS.pre()` → `l2vpn/parser.py:vpls()` → `make_empty()`
2. Section parser `nlri-set` actions → `scope.nlri_assign()` → `assign()`
3. Legacy mode in RouteBuilderValidator (`_validate_legacy`)
4. Unit tests in `tests/unit/test_vpls.py` that test the legacy pattern

**Phase 5 Status: PARTIAL**

Full removal requires:
- Update `announce/path.py`, `announce/vpn.py`, `announce/label.py` to use Settings
- Update Section parser to use Settings when available
- Update `l2vpn/parser.py` to not create empty VPLS
- Update unit tests to use Settings pattern only

**Resume Point:**
- Continue Phase 5 in future: Update remaining schemas and remove mutation methods
- All current code paths work, mutation is documented as deprecated

---

**Updated:** 2025-12-07
