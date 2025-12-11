# Configuration and Neighbor from_settings() Pattern

**Status:** ✅ Completed
**Created:** 2025-12-10
**Updated:** 2025-12-11

## Goal

Enable programmatic construction of `Configuration` and `Neighbor` objects using the `from_settings()` factory pattern, without requiring config file parsing. This enables:
- Building neighbors programmatically via code
- Testing neighbor configurations without config files
- API-driven neighbor/configuration creation
- Simpler unit testing

## Existing Pattern Reference

The codebase uses `from_settings()` pattern for NLRI classes:
- `VPLSSettings`, `INETSettings`, `FlowSettings` in `src/exabgp/bgp/message/update/nlri/settings.py`
- Pattern: Settings dataclass with `validate()` returning `''` if valid, error message if invalid
- Factory: `Class.from_settings(settings)` validates and creates immutable instance

---

## Implementation Plan

### Phase 1: SessionSettings and Session.from_settings()

**New file:** `src/exabgp/bgp/neighbor/settings.py`

```python
@dataclass
class SessionSettings:
    """Settings for deferred Session construction."""
    peer_address: IP | None = None          # Required
    local_as: ASN | None = None             # Required
    peer_as: ASN | None = None              # Required
    local_address: IP | None = None         # Optional (auto-discovery if None)
    router_id: RouterID | None = None       # Optional (derived from local_address)
    md5_password: str = ''
    md5_base64: bool = False
    connect: int = 0
    listen: int = 0
    passive: bool = False
    source_interface: str = ''
    outgoing_ttl: int | None = None
    incoming_ttl: int | None = None

    def validate(self) -> str:
        """Returns '' if valid, error message if invalid."""
        if self.peer_address is None:
            return 'session peer-address missing'
        if self.local_as is None:
            return 'session local-as missing'
        if self.peer_as is None:
            return 'session peer-as missing'
        if self.listen > 0 and self.local_address is None:
            return 'session local-address required when listen is set'
        return ''
```

**Modify:** `src/exabgp/bgp/neighbor/session.py`
- Add `from_settings(cls, settings: SessionSettings) -> Session` classmethod
- Calls `settings.validate()`, raises `ValueError` if invalid
- Creates Session with all fields, calls `session.infer()`

**Tests (TDD):** `tests/unit/test_session_settings.py`
- `test_validate_missing_peer_address` - returns error
- `test_validate_missing_local_as` - returns error
- `test_validate_complete_settings` - returns ''
- `test_from_settings_creates_valid_session` - factory works
- `test_from_settings_raises_on_invalid` - ValueError raised
- `test_from_settings_calls_infer` - router_id derived

---

### Phase 2: NeighborSettings and Neighbor.from_settings()

**Add to:** `src/exabgp/bgp/neighbor/settings.py`

```python
@dataclass
class NeighborSettings:
    """Settings for deferred Neighbor construction."""
    session: SessionSettings = field(default_factory=SessionSettings)

    # BGP policy (optional with defaults)
    description: str = ''
    hold_time: int = 180
    rate_limit: int = 0
    host_name: str = ''
    domain_name: str = ''
    group_updates: bool = True
    auto_flush: bool = True
    adj_rib_in: bool = True
    adj_rib_out: bool = True
    manual_eor: bool = False

    # Capability
    capability: NeighborCapability = field(default_factory=NeighborCapability)

    # Families
    families: list[tuple[AFI, SAFI]] = field(default_factory=list)
    nexthops: list[tuple[AFI, SAFI, AFI]] = field(default_factory=list)
    addpaths: list[tuple[AFI, SAFI]] = field(default_factory=list)

    # Routes and API (optional)
    routes: list[Route] = field(default_factory=list)
    api: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> str:
        """Validates session + hold_time range (0 or 3-65535)."""
        error = self.session.validate()
        if error:
            return error
        if self.hold_time < 0 or self.hold_time > 65535:
            return 'neighbor hold-time must be 0-65535'
        if self.hold_time > 0 and self.hold_time < 3:
            return 'neighbor hold-time must be 0 (disabled) or >= 3'
        return ''
```

**Modify:** `src/exabgp/bgp/neighbor/neighbor.py`
- Add `from_settings(cls, settings: NeighborSettings) -> Neighbor` classmethod
- Creates Session via `Session.from_settings(settings.session)`
- Sets BGP policy attributes, capability
- Adds families, routes, calls `neighbor.infer()`, initializes RIB

**Tests (TDD):** `tests/unit/test_neighbor_settings.py`
- `test_validate_session_error_propagates` - nested validation
- `test_validate_hold_time_range` - 0 or 3-65535
- `test_from_settings_creates_valid_neighbor` - factory works
- `test_from_settings_with_families` - families added correctly
- `test_from_settings_initializes_rib` - RIB enabled

---

### Phase 3: ConfigurationSettings and Configuration.from_settings()

**New file:** `src/exabgp/configuration/settings.py`

```python
@dataclass
class ConfigurationSettings:
    """Settings for programmatic Configuration creation."""
    neighbors: list[NeighborSettings] = field(default_factory=list)
    processes: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> str:
        """Validates all neighbor settings."""
        for i, neighbor_settings in enumerate(self.neighbors):
            error = neighbor_settings.validate()
            if error:
                return f'neighbor[{i}]: {error}'
        return ''
```

**Modify:** `src/exabgp/configuration/configuration.py`
- Add `from_settings(cls, settings: ConfigurationSettings) -> _Configuration` classmethod
- Creates each neighbor via `Neighbor.from_settings()`

**Tests (TDD):** `tests/unit/configuration/test_configuration_settings.py`
- `test_validate_neighbor_error_propagates` - nested validation
- `test_from_settings_creates_valid_configuration` - factory works
- `test_from_settings_with_multiple_neighbors` - multiple neighbors

---

## Files Summary

### New Files
| File | Purpose |
|------|---------|
| `src/exabgp/bgp/neighbor/settings.py` | SessionSettings, NeighborSettings |
| `src/exabgp/configuration/settings.py` | ConfigurationSettings |
| `tests/unit/test_session_settings.py` | Session settings tests |
| `tests/unit/test_neighbor_settings.py` | Neighbor settings tests |
| `tests/unit/configuration/test_configuration_settings.py` | Configuration settings tests |

### Files to Modify
| File | Change |
|------|--------|
| `src/exabgp/bgp/neighbor/session.py` | Add `from_settings()` classmethod |
| `src/exabgp/bgp/neighbor/neighbor.py` | Add `from_settings()` classmethod |
| `src/exabgp/configuration/configuration.py` | Add `from_settings()` classmethod |

---

## Usage Example

```python
from exabgp.bgp.neighbor.settings import SessionSettings, NeighborSettings
from exabgp.bgp.neighbor.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP
from exabgp.bgp.message.open.asn import ASN

# Build session
session = SessionSettings()
session.peer_address = IP.from_string('192.168.1.1')
session.local_address = IP.from_string('192.168.1.2')
session.local_as = ASN(65000)
session.peer_as = ASN(65001)

# Build neighbor
settings = NeighborSettings()
settings.session = session
settings.hold_time = 90
settings.families = [(AFI.ipv4, SAFI.unicast)]

# Create neighbor (validates and creates)
neighbor = Neighbor.from_settings(settings)
```

---

## Progress

### Phase 1: SessionSettings and Session.from_settings()
- [x] Write `tests/unit/test_session_settings.py` (TDD - tests fail first)
- [x] Create `src/exabgp/bgp/neighbor/settings.py` with `SessionSettings`
- [x] Add `Session.from_settings()` to `session.py`
- [x] Verify tests pass (23 tests)

### Phase 2: NeighborSettings and Neighbor.from_settings()
- [x] Write `tests/unit/test_neighbor_settings.py` (TDD - tests fail first)
- [x] Add `NeighborSettings` to `settings.py`
- [x] Add `Neighbor.from_settings()` to `neighbor.py`
- [x] Verify tests pass (26 tests)

### Phase 3: ConfigurationSettings and Configuration.from_settings()
- [x] Write `tests/unit/configuration/test_configuration_settings.py` (TDD)
- [x] Create `src/exabgp/configuration/settings.py` with `ConfigurationSettings`
- [x] Add `Configuration.from_settings()` to `configuration.py`
- [x] Verify tests pass (12 tests)

### Final
- [x] Run `./qa/bin/test_everything` - all 15 test suites pass

---

## Key Design Decisions

1. **Separate Settings files** - Following NLRI pattern, settings are in dedicated files
2. **Composition** - `NeighborSettings` contains `SessionSettings` (not flattened)
3. **Validation chain** - `NeighborSettings.validate()` calls `session.validate()`
4. **Empty defaults** - Families default to empty list (user must specify)
5. **Immutable after creation** - Objects created via `from_settings()` should not be mutated

---

## Critical Files Reference

| File | Purpose |
|------|---------|
| `src/exabgp/bgp/message/update/nlri/settings.py` | Pattern reference (VPLSSettings, INETSettings) |
| `src/exabgp/bgp/neighbor/session.py` | Session dataclass (has `infer()`, `missing()`) |
| `src/exabgp/bgp/neighbor/neighbor.py` | Neighbor class to extend |
| `src/exabgp/bgp/neighbor/capability.py` | NeighborCapability dataclass |
| `src/exabgp/configuration/neighbor/__init__.py` | `_post_neighbor()` reference for field mappings |
| `tests/unit/test_nlri_settings.py` | Test pattern reference |

---

## Resume Point

Start with Phase 1 - write tests for `SessionSettings` first (TDD approach).
