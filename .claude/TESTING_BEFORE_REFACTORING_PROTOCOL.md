# Testing Before Refactoring Protocol

**MANDATORY:** Read this before ANY code modification. This is not optional.

---

## Core Principles

### 1. Never refactor without tests

**Never refactor code without first ensuring adequate test coverage.**

Refactoring without tests is like performing surgery without monitoring vital signs - you won't know if you've killed the patient until it's too late.

### 2. Understand the specification first

**Before modifying BGP/protocol code, read the relevant RFC.**

If the wire format or protocol behavior is not documented in the `__init__.py` or module docstring, you MUST:
1. Identify the relevant RFC(s)
2. Read the packet format section
3. Understand the field layouts and semantics
4. Document what you learned in the code

This applies to:
- NLRI types (wire format, field sizes, encoding)
- Attributes (type codes, flags, encoding)
- Capabilities (negotiation, parameters)
- Messages (OPEN, UPDATE, NOTIFICATION, KEEPALIVE)

---

## The Protocol: RFC-Test-Verify-Refactor-Verify

### Step 0: Check RFC Documentation

Before touching any protocol code:

```bash
# Check if wire format is documented in the module
head -100 src/exabgp/bgp/message/update/nlri/<module>.py
grep -n "RFC\|wire format\|Wire format\|packet format" src/exabgp/bgp/message/update/nlri/<module>.py
```

**If NOT documented:**
1. Look up the RFC using `.claude/exabgp/BGP_CONCEPTS_TO_CODE_MAP.md`
2. Use WebSearch to find the RFC packet format section
3. Document the wire format in the code BEFORE making changes

**Common RFCs:**
| Feature | RFC | ExaBGP Location |
|---------|-----|-----------------|
| BGP-4 base | RFC 4271 | `bgp/message/*.py`, `bgp/fsm.py` |
| MP-BGP (AFI/SAFI) | RFC 4760 | `nlri/*.py`, `attribute/mprnlri.py` |
| VPLS | RFC 4761, RFC 4762 | `nlri/vpls.py` |
| EVPN | RFC 7432 | `nlri/evpn/` |
| FlowSpec | RFC 5575, RFC 8955 | `nlri/flow.py` |
| BGP-LS | RFC 7752 | `nlri/bgpls/` |
| Add-Path | RFC 7911 | `capability/addpath.py` |
| Large Communities | RFC 8092 | `attribute/community/large.py` |
| MVPN | RFC 6514 | `nlri/mvpn/` |
| RTC (Route Target Constraint) | RFC 4684 | `nlri/rtc.py` |
| MUP (Mobile User Plane) | draft-ietf-dmm-srv6-mobile-uplane | `nlri/mup/` |
| Route Refresh | RFC 2918 | `message/refresh.py` |
| Graceful Restart | RFC 4724 | `capability/graceful.py` |
| 4-byte ASN | RFC 6793 | `capability/asn4.py` |
| Extended Communities | RFC 4360 | `attribute/community/extended/` |
| PMSI Tunnel | RFC 6514 | `attribute/pmsi.py` |
| AIGP | RFC 7311 | `attribute/aigp.py` |
| SRv6 | RFC 9252 | `nlri/bgpls/srv6sid.py` |
| Segment Routing | RFC 8669 | `attribute/sr/` |
| IP VPN (VPNv4/v6) | RFC 4364 | `nlri/ipvpn.py` |

**Example wire format documentation:**

**Example 1: VPLS NLRI**
```python
"""VPLS NLRI (RFC 4761 Section 3.2.2)

Wire format (19 bytes total):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |           Length (2)          |    Route Distinguisher (8)    |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    ... RD continued ...                       |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |          VE ID (2)            |      Label Block Offset (2)   |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |      Label Block Size (2)     |       Label Base (3)          |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

Byte offsets (including 2-byte length prefix):
  [0:2]   - Length (always 17 for VPLS)
  [2:10]  - Route Distinguisher
  [10:12] - VE ID (endpoint)
  [12:14] - Label Block Offset
  [14:16] - Label Block Size
  [16:19] - Label Base (20 bits) + flags (4 bits)
"""
```

**Example 2: EVPN MAC/IP Advertisement (Route Type 2)**
```python
"""EVPN MAC/IP Advertisement Route (RFC 7432 Section 7.2)

Wire format (variable length, 33+ bytes):
    0                   1                   2                   3
    0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | Route Type(1) |    Length(1)  |  Route Distinguisher (8)      |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    ... RD continued ...                       |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |          Ethernet Segment Identifier (10 bytes)               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    ... ESI continued ...                      |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    Ethernet Tag ID (4)                        |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | MAC Addr Len  |           MAC Address (6 bytes)               |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |                    ... MAC continued ...                      |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   | IP Addr Len   |           IP Address (0, 4, or 16 bytes)      |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
   |           MPLS Label 1 (3)    |    MPLS Label 2 (0 or 3)      |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

Byte offsets:
  [0]     - Route Type (always 2)
  [1]     - Length of following fields
  [2:10]  - Route Distinguisher
  [10:20] - Ethernet Segment Identifier
  [20:24] - Ethernet Tag ID
  [24]    - MAC Address Length (always 48 = 6 bytes)
  [25:31] - MAC Address
  [31]    - IP Address Length (0, 32, or 128 bits)
  [32:N]  - IP Address (if present)
  [N:N+3] - MPLS Label 1
  [N+3:]  - MPLS Label 2 (optional, for IP-VRF)
"""
```

**Example 3: Simple NLRI (IPv4 prefix)**
```python
"""IPv4 Unicast NLRI (RFC 4271 Section 4.3)

Wire format (1-5 bytes):
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-...-+-+-+-+-+-+-+-+-+-+-+
   |   Length (1)  |       Prefix (variable, 0-4 bytes)           |
   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-...-+-+-+-+-+-+-+-+-+-+-+

Length field: prefix length in bits (0-32)
Prefix bytes: ceil(length / 8) bytes, containing the prefix

Examples:
  10.0.0.0/8  -> 08 0a           (1 byte prefix)
  10.0.0.0/24 -> 18 0a 00 00     (3 bytes prefix)
  0.0.0.0/0   -> 00              (0 bytes prefix - default route)
"""
```

### Step 1: Identify What You're Changing

Before touching any code, answer:
- What file(s) will I modify?
- What functions/classes/methods will change?
- What is the public interface (inputs → outputs)?

### Step 2: Find Existing Tests

```bash
# Search for test files
ls tests/unit/test_*.py | xargs grep -l "ClassName\|function_name"

# Search for test functions
grep -rn "def test_.*classname\|def test_.*function" tests/

# Check functional tests
./qa/bin/functional encoding --list | grep -i "feature_name"
```

**Ask yourself:**
- Do tests exist for this code?
- Do they cover the public interface?
- Do they cover edge cases?
- What is the current pass/fail status?

### Step 3: Run Existing Tests FIRST

```bash
# Run specific tests
env exabgp_log_enable=false uv run pytest tests/unit/test_<name>.py -v

# Run and record baseline
env exabgp_log_enable=false uv run pytest tests/unit/test_<name>.py -v 2>&1 | tee /tmp/baseline.txt
```

**Document the baseline:**
- How many tests pass?
- How many tests exist?
- Any skipped tests? Why?

### Step 4: Assess Test Coverage

**If tests exist but coverage is poor:**
- Add tests for uncovered paths BEFORE refactoring
- Each public method needs at least one test
- Each branch/condition needs coverage

**If no tests exist:**
- STOP. Write tests first.
- Tests document current behavior (even if buggy)
- This protects against unintended changes

### Step 5: Write Missing Tests BEFORE Refactoring

```python
# Test template for NLRI classes
class TestClassName:
    def test_create_basic(self):
        """Test basic creation with typical values."""

    def test_pack_unpack_roundtrip(self):
        """Pack then unpack preserves all data."""

    def test_pack_format(self):
        """Verify wire format structure."""

    def test_unpack_known_data(self):
        """Unpack known wire bytes produces expected values."""

    def test_json_output(self):
        """JSON serialization format."""

    def test_str_representation(self):
        """String representation."""

    def test_edge_cases(self):
        """Boundary conditions, empty values, max values."""
```

### Step 6: Verify New Tests Pass

```bash
# New tests must pass with CURRENT code
env exabgp_log_enable=false uv run pytest tests/unit/test_<name>.py -v
```

If new tests fail with current code, you've found a bug - document it, decide whether to fix it as part of this work or separately.

### Step 7: NOW Refactor

Only after steps 1-6 are complete, begin refactoring.

Make small, incremental changes. Run tests after each change:
```bash
env exabgp_log_enable=false uv run pytest tests/unit/test_<name>.py -v
```

### Step 8: Verify All Tests Still Pass

```bash
# Full test suite
./qa/bin/test_everything
```

Compare with baseline from Step 3. Same tests should pass.

---

## Checklist Template

Copy this for each refactoring task:

```markdown
## Pre-Refactoring Checklist: [Feature/File Name]

### 0. RFC/Specification (for protocol code)
- [ ] Is wire format documented in the code? Yes/No
- [ ] If No: RFC identified: ___
- [ ] If No: Wire format documented in code: Yes/No
- [ ] Byte offsets verified against RFC: Yes/No

### 1. Scope
- [ ] Files to modify: ___
- [ ] Functions/classes affected: ___
- [ ] Public interface documented: ___

### 2. Existing Tests
- [ ] Test files found: ___
- [ ] Test count: ___
- [ ] Baseline recorded: ___ passing / ___ total

### 3. Coverage Assessment
- [ ] All public methods have tests: Yes/No
- [ ] Edge cases covered: Yes/No
- [ ] Missing coverage: ___

### 4. Tests Added (if needed)
- [ ] test___ added
- [ ] test___ added
- [ ] New tests pass with current code: Yes/No

### 5. Ready to Refactor
- [ ] All prerequisites complete
- [ ] Baseline established
- [ ] Incremental approach planned

### 6. Post-Refactoring
- [ ] All original tests pass
- [ ] All new tests pass
- [ ] ./qa/bin/test_everything passes
```

---

## Red Flags - STOP If You See These

1. **No tests exist** → Write tests first
2. **Tests are failing** → Fix tests or code first, don't add more breakage
3. **"I'll add tests later"** → No. Tests come BEFORE refactoring.
4. **"It's a simple change"** → Simple changes break things. Test anyway.
5. **"Tests are slow"** → Run them anyway. Faster than debugging production.
6. **Wire format not documented** → Read RFC, document in code BEFORE changing
7. **Byte offsets unclear** → Draw the packet diagram, verify against RFC

---

## Why This Matters

| Without Tests First | With Tests First |
|---------------------|------------------|
| "It works on my machine" | Reproducible verification |
| Silent behavior changes | Immediate regression detection |
| Hours debugging | Minutes to identify issues |
| Fear of refactoring | Confidence to improve |
| Technical debt grows | Technical debt shrinks |

---

## Integration with Existing Protocols

This protocol integrates with:
- `ESSENTIAL_PROTOCOLS.md` - Verification before claiming
- `MANDATORY_REFACTORING_PROTOCOL.md` - Safe refactoring practices
- `CI_TESTING.md` - Full test suite requirements

**The order is:**
1. Read ESSENTIAL_PROTOCOLS.md (always)
2. Read TESTING_BEFORE_REFACTORING_PROTOCOL.md (this file)
3. Execute the checklist
4. Then proceed with refactoring

---

## Source-to-Test Mapping

Quick reference for finding tests for specific source modules:

| Source Module | Test File(s) | Notes |
|--------------|--------------|-------|
| `nlri/inet.py` | `test_inet.py` | IPv4/IPv6 unicast |
| `nlri/ipvpn.py` | `test_ipvpn.py` | VPNv4/VPNv6 |
| `nlri/vpls.py` | `test_vpls.py`, `test_l2vpn.py` | L2VPN VPLS |
| `nlri/evpn/` | `test_evpn.py` | All EVPN route types |
| `nlri/flow.py` | `test_flow.py`, `test_flowspec.py` | FlowSpec |
| `nlri/bgpls/` | `test_bgpls.py`, `test_bgpls_*.py` | BGP-LS |
| `nlri/mvpn/` | `test_mvpn.py` | Multicast VPN |
| `nlri/mup/` | `test_mup.py` | Mobile User Plane |
| `nlri/rtc.py` | `test_rtc.py` | Route Target Constraint |
| `nlri/label.py` | `test_label.py` | MPLS labels |
| `attribute/aspath.py` | `test_aspath.py` | AS_PATH |
| `attribute/community/` | `test_communities.py` | All community types |
| `attribute/*.py` | `test_attributes.py`, `test_path_attributes.py` | General attributes |
| `attribute/sr/` | `test_sr_attributes.py` | Segment Routing |
| `message/open/` | `test_open.py`, `test_open_capabilities.py` | OPEN message |
| `message/update/` | `test_update_message.py` | UPDATE message |
| `message/notification.py` | `test_notification.py`, `test_notification_comprehensive.py` | NOTIFICATION |
| `message/keepalive.py` | `test_keepalive.py` | KEEPALIVE |
| `message/refresh.py` | `test_route_refresh.py` | ROUTE-REFRESH |
| `bgp/fsm.py` | `test_fsm_comprehensive.py` | State machine |
| `reactor/peer.py` | `test_peer_state_machine.py` | Peer handling |
| `reactor/api/` | `test_reactor_api_*.py` | API commands |
| `rib/` | `test_rib_*.py` | RIB operations |
| `configuration/` | `configuration/test_*.py` | Config parsing |
| `cli/` | `cli/test_*.py`, `test_cli_*.py` | CLI |

---

## Measuring Test Coverage

Use pytest-cov to measure actual test coverage:

```bash
# Coverage for a specific module
env exabgp_log_enable=false uv run pytest tests/unit/test_vpls.py -v \
    --cov=src/exabgp/bgp/message/update/nlri/vpls \
    --cov-report=term-missing

# Coverage for entire NLRI package
env exabgp_log_enable=false uv run pytest tests/unit/ -v \
    --cov=src/exabgp/bgp/message/update/nlri \
    --cov-report=term-missing

# Generate HTML coverage report
env exabgp_log_enable=false uv run pytest tests/unit/ -v \
    --cov=src/exabgp/bgp/message/update/nlri \
    --cov-report=html
# Open htmlcov/index.html in browser
```

**Coverage thresholds:**
- Critical protocol code (pack/unpack): aim for 90%+
- Public methods: 100% coverage required
- Edge cases: explicitly test boundary conditions

---

## Quick Reference

```bash
# Find tests for a file
grep -rn "test.*ClassName" tests/

# Run specific tests with verbose output
env exabgp_log_enable=false uv run pytest tests/unit/test_X.py -v

# Run tests matching a pattern
env exabgp_log_enable=false uv run pytest tests/unit/ -k "vpls" -v

# Full suite (required before declaring success)
./qa/bin/test_everything
```

---

**Remember:** The best time to write tests is before you need them. The second best time is now.

---

**Updated:** 2025-12-07
