# ExaBGP Testing Coverage Progress

## Current Status (as of 2025-11-08)

### ✅ Completed Work

#### EVPN (Ethernet VPN) - **92-98% Coverage**
- **Files**: `tests/test_evpn.py` (47 tests)
- **Coverage Improvements**:
  - `mac.py`: 27% → 92% (+65%)
  - `multicast.py`: 36% → 94% (+58%)
  - `prefix.py`: 29% → 98% (+69%)
  - `segment.py`: 38% → 96% (+58%)
  - `ethernetad.py`: → 98%

- **Bug Fixes**:
  1. MAC packing: Fixed missing MPLS label when IP present (RFC 7432 compliance)
  2. MAC equality: Fixed case-sensitive comparison issue

- **Test Coverage**:
  - All 5 EVPN route types (EthernetAD, MAC, Multicast, EthernetSegment, Prefix)
  - IPv4 and IPv6 support
  - Pack/unpack roundtrips
  - Equality, hashing, JSON serialization
  - Error handling for invalid inputs
  - Multiple MPLS labels
  - ADD-PATH support

**Branch**: `claude/continue-test-011CUvmMDebRj7XRxN1TyctH`
**Commit**: `4f8fbc1 - Add comprehensive EVPN tests and fix bugs (92-98% coverage)`

---

## 🎯 Next Steps (Priority Order)

### 1. MUP (Mobile User Plane) - Current: 22-48% Coverage
**Location**: `src/exabgp/bgp/message/update/nlri/mup/`

**Files to Test**:
- `dsd.py` - Direct Segment Discovery (41% coverage)
- `isd.py` - Indirect Segment Discovery (36% coverage)
- `t1st.py` - Type 1 Session Transformed (22% coverage) ⚠️ PRIORITY
- `t2st.py` - Type 2 Session Transformed (29% coverage)
- `nlri.py` - MUP NLRI base (52% coverage)

**Approach**:
- Create `tests/test_mup.py`
- Test all MUP route types with pack/unpack
- IPv4/IPv6 support
- Error handling for invalid formats
- Target: 90%+ coverage

### 2. MVPN (Multicast VPN) - Current: 30-54% Coverage
**Location**: `src/exabgp/bgp/message/update/nlri/mvpn/`

**Files to Test**:
- `sharedjoin.py` - Shared Tree Join (30% coverage) ⚠️ PRIORITY
- `sourcead.py` - Source Active Discovery (31% coverage) ⚠️ PRIORITY
- `sourcejoin.py` - Source Tree Join (30% coverage) ⚠️ PRIORITY
- `nlri.py` - MVPN NLRI base (54% coverage)

**Approach**:
- Create `tests/test_mvpn.py`
- Test all MVPN route types
- Multicast group handling
- Source/shared tree scenarios
- Target: 90%+ coverage

### 3. BGP-LS (Link-State)
**Location**: Check `src/exabgp/bgp/message/update/nlri/bgpls/`

**Files to Assess**:
- Review existing coverage
- Identify gaps
- Create comprehensive tests

**Approach**:
- First assess current coverage
- Create `tests/test_bgpls.py` if needed
- Focus on TLV encoding/decoding
- Target: 90%+ coverage

### 4. Flowspec - Current: 64% Coverage
**Location**: `src/exabgp/bgp/message/update/nlri/flow.py`

**Current State**: 64% coverage (421 statements, 151 missed)

**Approach**:
- Review existing `tests/flow_test.py`
- Identify uncovered branches
- Add tests for edge cases
- Target: 85%+ coverage

---

## 🔧 Testing Pattern Established

Based on EVPN work, follow this pattern for all modules:

```python
# 1. Import all necessary classes
from exabgp.bgp.message.update.nlri.MODULE import *
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.update.nlri.nlri import Action

# 2. Test each route type class
class TestRouteType:
    def test_creation(self):
        """Test basic object creation"""

    def test_pack_unpack_ipv4(self):
        """Test pack/unpack with IPv4"""
        route = RouteType(...)
        packed = route.pack_nlri()
        unpacked, leftover = NLRI.unpack_nlri(AFI, SAFI, packed, Action.UNSET, None)
        # Assert unpacked matches original

    def test_pack_unpack_ipv6(self):
        """Test pack/unpack with IPv6"""

    def test_equality(self):
        """Test equality comparison"""

    def test_hash_consistency(self):
        """Test hash computation"""

    def test_invalid_input(self):
        """Test error handling"""
        with pytest.raises(Notify):
            # Invalid input

    def test_json(self):
        """Test JSON serialization"""

    def test_string_representation(self):
        """Test __str__ method"""
```

---

## 📊 Overall Test Suite Status

**Total Tests**: 356 passing (30 deselected fuzz tests)
**Overall Coverage**: 32% → Target: 50%+

**Major Gaps**:
- Configuration parsing (0-20% coverage)
- Reactor/networking (0-40% coverage)
- CLI tools (0% coverage)
- Yang/data validation (0% coverage)

**Focus Areas** (BGP protocol core):
- ✅ EVPN: 92-98%
- 🔄 MUP: 22-48% → Target 90%+
- 🔄 MVPN: 30-54% → Target 90%+
- 🔄 BGP-LS: TBD
- 🔄 Flowspec: 64% → Target 85%+
- Path attributes: 70-90% (good)
- Communities: 85%+ (good)
- Route Refresh: 95%+ (excellent)

---

## 🚀 How to Resume

1. **Check out the latest branch**:
   ```bash
   git checkout claude/continue-test-011CUvmMDebRj7XRxN1TyctH
   git pull origin claude/continue-test-011CUvmMDebRj7XRxN1TyctH
   ```

2. **Install test dependencies** (if needed):
   ```bash
   pip install -e .
   pip install pytest pytest-cov hypothesis pytest-benchmark pytest-xdist pytest-timeout psutil
   ```

3. **Run existing tests**:
   ```bash
   # All non-fuzz tests
   python -m pytest tests/ -m "not fuzz" -v

   # Coverage for specific module (e.g., EVPN)
   python -m pytest tests/ --cov=src/exabgp/bgp/message/update/nlri/evpn --cov-report=term-missing

   # Full coverage report
   python -m pytest tests/ -m "not fuzz" --cov=exabgp --cov-report=term-missing | tail -150
   ```

4. **Start next module** (MUP recommended):
   ```bash
   # Create new test file
   touch tests/test_mup.py

   # Review MUP source files
   ls -la src/exabgp/bgp/message/update/nlri/mup/

   # Start with one route type, follow EVPN pattern
   ```

5. **Commit pattern**:
   ```bash
   git add tests/test_mup.py
   git commit -m "Add comprehensive MUP tests (XX% coverage improvement)"
   git push -u origin claude/continue-test-011CUvmMDebRj7XRxN1TyctH
   ```

---

## 📝 Notes

- **Bug Discovery**: Testing revealed 2 bugs in EVPN MAC handling - expect similar discoveries
- **Test Time**: EVPN tests (47 tests) run in ~1 second
- **Coverage Tool**: Using pytest-cov with term-missing for line-by-line analysis
- **RFC Compliance**: Tests validate RFC compliance (e.g., RFC 7432 for EVPN)

---

## 🔗 References

- Previous work: See commit history on `claude/continue-test-011CUvmMDebRj7XRxN1TyctH`
- Test patterns: `tests/test_evpn.py` (comprehensive example)
- Existing tests: Review `tests/nlri_tests.py` for older patterns
