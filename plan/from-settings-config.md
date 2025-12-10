# Configuration and Neighbor from_settings Pattern

**Status:** 📋 Planning
**Created:** 2025-12-10
**Updated:** 2025-12-10

## Goal

Enable programmatic construction of Configuration and Neighbor objects using the `from_settings` pattern, without requiring config file parsing. This allows:
- Building neighbors programmatically via code
- Testing neighbor configurations without config files
- API-driven neighbor/configuration creation
- Simpler unit testing

## Background

The codebase already uses the `from_settings` pattern for NLRI classes:
- `VPLSSettings` → `VPLS.from_settings(settings)`
- `INETSettings` → `INET.from_settings(settings)`
- `FlowSettings` → `Flow.from_settings(settings)`

This pattern provides:
1. A mutable Settings dataclass to collect configuration values
2. A `validate()` method to check completeness
3. A `from_settings()` factory method on the target class
4. Immutable target objects created from validated settings

## Progress

### Phase 1: NeighborSettings and Neighbor.from_settings()

- [ ] Create `NeighborSettings` dataclass in `src/exabgp/bgp/neighbor/settings.py`
- [ ] Add `validate()` method with required field checks
- [ ] Add `Neighbor.from_settings(settings)` factory method
- [ ] Write unit tests for NeighborSettings validation
- [ ] Write unit tests for Neighbor.from_settings()

### Phase 2: SessionSettings for Session component

- [ ] Create `SessionSettings` dataclass (Session-related config)
- [ ] Add `Session.from_settings(settings)` factory method
- [ ] Update NeighborSettings to use SessionSettings
- [ ] Write unit tests

### Phase 3: CapabilitySettings for NeighborCapability

- [ ] Create `CapabilitySettings` dataclass
- [ ] Add `NeighborCapability.from_settings(settings)` factory method
- [ ] Update NeighborSettings to use CapabilitySettings
- [ ] Write unit tests

### Phase 4: ConfigurationSettings (optional)

- [ ] Create `ConfigurationSettings` dataclass
- [ ] Add `Configuration.from_settings(settings)` factory method
- [ ] This would create a Configuration with pre-built neighbors
- [ ] Write unit tests

## Files to Create

| File | Purpose |
|------|---------|
| `src/exabgp/bgp/neighbor/settings.py` | NeighborSettings, SessionSettings, CapabilitySettings |
| `tests/unit/neighbor/test_neighbor_settings.py` | Unit tests for settings |

## Files to Modify

| File | Change |
|------|--------|
| `src/exabgp/bgp/neighbor/neighbor.py` | Add `from_settings()` classmethod |
| `src/exabgp/bgp/neighbor/session.py` | Add `from_settings()` classmethod |
| `src/exabgp/bgp/neighbor/capability.py` | Add `from_settings()` classmethod |
| `src/exabgp/configuration/configuration.py` | Add `from_settings()` classmethod (Phase 4) |

## NeighborSettings Design

```python
@dataclass
class SessionSettings:
    """Settings for Session (connection-related) configuration."""
    peer_address: IP | None = None
    local_address: IP | None = None
    local_as: ASN | None = None
    peer_as: ASN | None = None
    router_id: RouterID | None = None
    passive: bool = False
    listen: int = 0
    connect: int = 0
    source_interface: str = ''
    md5_password: str = ''
    md5_base64: bool | None = None
    md5_ip: str = ''
    incoming_ttl: int | None = None
    outgoing_ttl: int | None = None
    auto_discovery: bool = False

    def validate(self) -> str:
        """Return error message or empty string if valid."""
        if self.peer_address is None:
            return 'peer-address is required'
        # local_address can be None if auto_discovery is True
        if self.local_address is None and not self.auto_discovery:
            return 'local-address is required (or enable auto-discovery)'
        if self.local_as is None:
            return 'local-as is required'
        if self.peer_as is None:
            return 'peer-as is required'
        if self.router_id is None:
            return 'router-id is required'
        return ''


@dataclass
class CapabilitySettings:
    """Settings for BGP capabilities."""
    asn4: bool = True
    route_refresh: bool = False
    graceful_restart_time: int = 0  # 0 = disabled
    software_version: bool = False
    nexthop: bool = False
    add_path: int = 0  # AddPath mode
    multi_session: bool = False
    operational: bool = False
    aigp: bool = False

    def validate(self) -> str:
        """Return error message or empty string if valid."""
        return ''


@dataclass
class NeighborSettings:
    """Settings for building a Neighbor programmatically."""
    # Session config
    session: SessionSettings | None = None

    # BGP policy configuration
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

    # Capabilities
    capability: CapabilitySettings | None = None

    # Families (AFI, SAFI tuples)
    families: list[tuple[AFI, SAFI]] = field(default_factory=list)

    # Nexthop mappings (AFI, SAFI, nexthop AFI)
    nexthops: list[tuple[AFI, SAFI, AFI]] = field(default_factory=list)

    # ADD-PATH families
    addpaths: list[tuple[AFI, SAFI]] = field(default_factory=list)

    # Routes to announce
    routes: list[Route] = field(default_factory=list)

    # API configuration
    api: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> str:
        """Return error message or empty string if valid."""
        if self.session is None:
            return 'session settings are required'
        error = self.session.validate()
        if error:
            return error
        if not self.families:
            return 'at least one address family is required'
        return ''
```

## Usage Example

```python
from exabgp.bgp.neighbor.settings import NeighborSettings, SessionSettings
from exabgp.bgp.neighbor.neighbor import Neighbor
from exabgp.protocol.family import AFI, SAFI
from exabgp.protocol.ip import IP

# Build session settings
session = SessionSettings()
session.peer_address = IP.from_string('192.168.1.1')
session.local_address = IP.from_string('192.168.1.2')
session.local_as = ASN(65000)
session.peer_as = ASN(65001)
session.router_id = RouterID.from_string('192.168.1.2')

# Build neighbor settings
settings = NeighborSettings()
settings.session = session
settings.hold_time = 90
settings.families = [(AFI.ipv4, SAFI.unicast)]

# Create neighbor from settings
neighbor = Neighbor.from_settings(settings)

# Now neighbor is ready to use
```

## Test Plan

### Unit Tests (TDD - write tests first)

1. **test_session_settings.py**
   - `test_create_empty_settings` - defaults work
   - `test_validate_missing_peer_address` - error on missing
   - `test_validate_missing_local_as` - error on missing
   - `test_validate_complete_settings` - empty string on valid
   - `test_auto_discovery_no_local_address` - valid when auto_discovery=True

2. **test_neighbor_settings.py**
   - `test_create_empty_settings` - defaults work
   - `test_validate_missing_session` - error on missing
   - `test_validate_missing_families` - error on missing
   - `test_validate_complete_settings` - empty string on valid

3. **test_neighbor_from_settings.py**
   - `test_from_settings_creates_valid_neighbor` - basic creation
   - `test_from_settings_preserves_families` - families set correctly
   - `test_from_settings_preserves_session` - session config correct
   - `test_from_settings_raises_on_invalid` - ValueError on bad settings

## Dependencies

- Existing `from_settings` pattern in NLRI classes (reference implementation)
- Neighbor, Session, NeighborCapability classes
- Protocol types (IP, ASN, AFI, SAFI)

## Notes

- Follow TDD: write tests first, then implement
- Keep settings mutable, target objects should behave as before
- Session already has an `infer()` method - may need to call it from `from_settings()`
- Consider whether to support routes in settings or add them separately

---

**Resume Point:** Start with Phase 1 - create tests for NeighborSettings first
