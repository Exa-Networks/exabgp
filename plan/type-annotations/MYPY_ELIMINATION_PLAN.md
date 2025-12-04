# MyPy Full Compliance Plan

**Goal:** Achieve 100% mypy compliance with zero errors and zero type: ignore comments

**Date:** 2025-11-15
**Current Status:** 584 errors (updated after Phase 1)
**Baseline (from MYPY_STATUS.md):** 1,149 errors (reduced to 584 after Phase 1)

---

## ⚠️ CRITICAL PRINCIPLES - MUST FOLLOW

### 1. NEVER Use type: ignore Comments
- All errors MUST be fixed at the root cause
- No suppressions, no workarounds
- Fix the actual type issue

### 2. Avoid Optional When Possible
- **Most Preferred:** Create real objects in tests instead of Optional[Type]
- **Second Best:** Mock objects only when real objects are impractical
- **Last Resort:** Non-optional types with proper initialization
- **ONLY use Optional when:** The value genuinely can be None in production code
- **Example of what NOT to do:**
  ```python
  # BAD - Making parameter Optional just to avoid passing real object
  def unpack_message(data: bytes, negotiated: Optional[Negotiated] = None)

  # GOOD - Require the parameter, create real object in tests
  def unpack_message(data: bytes, negotiated: Negotiated)
  # In tests: test_negotiated = Negotiated(neighbor, Direction.IN)

  # ACCEPTABLE - Use mock only if real object is too complex/expensive
  # In tests: mock_negotiated = Mock(spec=Negotiated)
  ```

### 3. Testing Strategy (Preference Order)
1. **Best:** Create real objects - `Negotiated(neighbor, Direction.IN)`
2. **Good:** Use `Mock(spec=ClassName)` for test objects when real objects impractical
3. **Acceptable:** Use `MagicMock()` when dynamic attributes needed
- Real objects provide best type safety and test fidelity
- Mocks provide type safety without Optional
- Tests should reflect production usage patterns

---

## Executive Summary

**Total Effort Estimate:** 80-120 hours over 4-6 weeks
**Risk Level:** Medium (some architectural changes required)
**Breaking Changes:** Minimal (internal refactoring only)

**Progress Since Baseline:**
- ✅ Removed 698 type: ignore comments (previous phase)
- ✅ Fixed Any type annotations in BGP-LS and EVPN (10 files, 40 instances)
- ✅ Fixed peer: Any → peer: Peer in processes.py (4 instances)
- ✅ Fixed 5 unused-ignore warnings (this session)
- **Current: 505 errors (56% reduction from 1,149)**

---

## Current Error Distribution

| Rank | Error Code | Count | % of Total | Difficulty |
|------|------------|-------|------------|------------|
| 1 | attr-defined | 156 | 31% | Medium |
| 2 | misc | 139 | 28% | Hard |
| 3 | assignment | 109 | 22% | Easy-Medium |
| 4 | override | 50 | 10% | Medium-Hard |
| 5 | unused-ignore | 35 | 7% | Easy |
| 6 | Type guards (str/bytes/int/bool) | 72 | 14% | Easy |
| 7 | arg-type | 13 | 3% | Easy |
| 8 | call-arg | 5 | 1% | Easy |

---

## Most Problematic Files (Top 20)

| File | Errors | Primary Issues |
|------|--------|----------------|
| bgp/message/update/nlri/flow.py | 59 | Multiple inheritance conflicts |
| reactor/protocol.py | 28 | Optional types, union handling |
| configuration/check.py | 27 | Type guards for string/bytes |
| reactor/api/transcoder.py | 23 | Type conversions |
| configuration/flow/parser.py | 18 | Flow parsing types |
| reactor/peer.py | 17 | Optional Protocol/RIB access |
| reactor/api/processes.py | 16 | Process management types |
| configuration/static/route.py | 15 | Route configuration |
| configuration/static/mpls.py | 12 | MPLS configuration |
| configuration/configuration.py | 12 | Config parsing |
| reactor/listener.py | 11 | Network listener types |
| bgp/message/update/__init__.py | 11 | Update message handling |
| configuration/static/__init__.py | 10 | Static config |
| configuration/announce/__init__.py | 10 | Announcement config |
| bgp/message/operational.py | 9 | Operational message types |
| configuration/static/parser.py | 8 | Static parser |
| bgp/message/update/nlri/bgpls/nlri.py | 8 | BGP-LS types |
| configuration/announce/mup.py | 7 | MUP announcement |
| configuration/announce/ip.py | 7 | IP announcement |
| bgp/message/update/nlri/mup/nlri.py | 7 | MUP NLRI |

---

## Phase-by-Phase Implementation Plan

### Phase 1: Quick Wins (10-15 hours) - Week 1

**Goal:** Fix 125+ errors with minimal architectural changes

#### 1.1 Remove Unused Ignore Comments (35 errors, 2 hours)
- **Files:** Scan all 273 type: ignore comments
- **Action:** Remove or correct unused-ignore warnings
- **Risk:** Very low
- **Validation:** `mypy --warn-unused-ignores`

#### 1.2 Add Type Guards for Primitives (72 errors, 3 hours)
- **Error types:** [str], [bytes], [int], [bool]
- **Pattern:** Add `isinstance()` checks or type narrowing
- **Files:** configuration/check.py (27), reactor/api/transcoder.py (23+)
- **Example:**
  ```python
  # Before:
  value: Union[str, int] = get_value()
  length = len(value)  # Error: int has no len

  # After:
  value: Union[str, int] = get_value()
  if isinstance(value, str):
      length = len(value)
  ```

#### 1.3 Fix Simple arg-type and call-arg (18 errors, 3 hours)
- **Error types:** [arg-type], [call-arg]
- **Action:** Fix function call signatures
- **Files:** Scattered across codebase

#### 1.4 Fix Simple assignment Errors (30 errors, 4 hours)
- **Files:** Various configuration files
- **Action:** Add proper type conversions or assertions
- **Example:**
  ```python
  # Before:
  labels: List[Optional[int]] = [1, 2, 3]  # Error

  # After:
  labels: List[Optional[int]] = [1, 2, 3]  # Fixed: change to List[int]
  # or
  labels: List[int] = [1, 2, 3]
  ```

**Phase 1 Target:** ~125 errors fixed, down to **~380 errors**

---

### Phase 2: Attribute/Module Issues (15-20 hours) - Week 2

**Goal:** Fix attr-defined and import errors

#### 2.1 Fix Import/Module Errors (20 errors, 3 hours)
- **Pattern:** Module has no attribute X
- **Files:**
  - conf/yang/generate.py (Parser, Code missing)
  - cli/main.py (Config missing)
  - netlink/old.py, netlink/netlink.py (AF_NETLINK platform-specific)
- **Action:** Add TYPE_CHECKING guards or fix imports

#### 2.2 Fix Vendoring Compatibility (5 errors, 2 hours)
- **File:** vendoring/objgraph.py
- **Issues:** Python 2 compatibility code (InstanceType, basestring, iteritems)
- **Action:** Add version checks or type: ignore with explanation

#### 2.3 Fix Resource/Family Type Hierarchies (10 errors, 4 hours)
- **Files:** protocol/family.py
- **Issues:** AFI/SAFI dict types incompatible with Resource base class
- **Action:** Use Generic types or adjust base class

#### 2.4 Fix Attribute Method Resolution (50 errors, 6 hours)
- **Pattern:** "type[X]" has no attribute Y
- **Files:** bgp/message/update/attribute/attribute.py and subclasses
- **Issues:** Dynamic attribute lookup via klass()
- **Action:** Use Protocol or cast() for dynamic dispatch

#### 2.5 Fix Capability Instance/Class Variable Conflicts (6 errors, 2 hours)
- **Files:** bgp/message/open/capability/*.py
- **Pattern:** Cannot override instance variable with class variable
- **Action:** Align variable declarations across hierarchy

#### 2.6 Fix IP/Attribute Multiple Inheritance (4 errors, 3 hours)
- **Files:** bgp/message/update/attribute/nexthop.py, originatorid.py
- **Issue:** klass and register defined differently in IP and Attribute
- **Action:** Use Protocol or composition pattern

**Phase 2 Target:** ~95 errors fixed, down to **~285 errors**

---

### Phase 3: Override and Assignment Issues (20-25 hours) - Week 3

**Goal:** Fix method signature incompatibilities

#### 3.1 Fix NLRI feedback() Method Overrides (20 errors, 4 hours)
- **Files:** bgp/message/update/nlri/vpls.py, rtc.py, label.py, ipvpn.py, inet.py, etc.
- **Issue:** feedback() has different signature in base vs subclasses
- **Options:**
  1. Make base class signature flexible: `def feedback(self, *args: Any) -> Optional[str]`
  2. Align all subclasses to match base
- **Recommendation:** Option 1 (less invasive)

#### 3.2 Fix NLRI unpack_nlri() Return Types (10 errors, 3 hours)
- **Files:** vpls.py, rtc.py, etc.
- **Issue:** Returns Tuple[X, bytes] but base expects just NLRI
- **Fix:** Update base class return type to include Tuple

#### 3.3 Fix Message CODE Overrides (15 errors, 5 hours)
- **Files:** bgp/message/notification.py, operational.py
- **Issue:** CODE defined as int in subclass, Callable in base
- **Action:** Refactor Message.CODE to be properly typed

#### 3.4 Fix register() Method Signatures (10 errors, 4 hours)
- **Files:** bgp/message/operational.py, bgp/message/update/attribute/pmsi.py
- **Issue:** register() signature varies across hierarchy
- **Action:** Use overload or make signature more flexible

#### 3.5 Fix pack() and ton() Method Signatures (10 errors, 3 hours)
- **Files:** bgp/message/update/attribute/nexthop.py
- **Issue:** Different default arguments in subclass
- **Action:** Align signatures or use Optional properly

#### 3.6 Fix Remaining Assignment Errors (15 errors, 4 hours)
- **Files:** Various
- **Action:** Add type conversions, assertions, or fix types

**Phase 3 Target:** ~80 errors fixed, down to **~205 errors**

---

### Phase 4: Architecture Refactoring (25-35 hours) - Week 4-5

**Goal:** Fix fundamental design issues

#### 4.1 Fix Flow Multiple Inheritance (59 errors, 12 hours)
- **File:** bgp/message/update/nlri/flow.py
- **Issue:** Complex multiple inheritance hierarchy causes conflicts
- **Root cause:**
  ```python
  class DestinationPort(NumericString, IOperation):
      # NumericString.operations: str
      # IOperation.operations: List[Operation]
      # Conflict!
  ```
- **Solution Options:**
  1. **Composition over inheritance:** Make IOperation a mixin with Protocol
  2. **Split classes:** Separate data model from operations
  3. **Use Union types:** Instead of multiple inheritance
- **Recommendation:** Option 1 - Composition with Protocol
- **Steps:**
  1. Create OperationProtocol with operations interface
  2. Convert NumericString to composition pattern
  3. Update all 20+ flow classes
  4. Extensive testing required

#### 4.2 Fix Protocol/Processes/RIB Optional Access (40 errors, 8 hours)
- **Files:** reactor/peer.py, reactor/protocol.py, reactor/loop.py
- **Issue:** Optional types accessed without guards
- **Pattern:**
  ```python
  self.proto: Optional[Protocol]  # None during init
  self.proto.method()  # Error: might be None
  ```
- **Solution:**
  1. Add guards: `if self.proto: self.proto.method()`
  2. Use assertions: `assert self.proto is not None`
  3. Change to non-Optional with late init pattern
- **Recommendation:** Mix of 1 and 2 based on context

#### 4.3 Fix Generic Type Variance (15 errors, 5 hours)
- **Files:** protocol/family.py
- **Issue:** Invariant dict types in inheritance
- **Action:** Use Mapping (covariant) instead of dict

#### 4.4 Fix Sequence.__new__ Return Type (1 error, 2 hours)
- **File:** netlink/sequence.py
- **Issue:** __new__ returns int instead of Sequence
- **Action:** Proper metaclass pattern or remove __new__

#### 4.5 Refactor Dynamic Method Calls (20 errors, 8 hours)
- **Files:** reactor/api/transcoder.py, bgp/message/update/__init__.py
- **Issue:** Dynamic attribute access not type-safe
- **Action:** Use Protocol, TypedDict, or explicit dispatch

**Phase 4 Target:** ~135 errors fixed, down to **~70 errors**

---

### Phase 5: Final Cleanup (10-15 hours) - Week 6

**Goal:** Eliminate all remaining errors and type: ignore comments

#### 5.1 Remove All type: ignore Comments (238 comments, 6 hours)
- **Strategy:** Fix underlying issues rather than suppress
- **Priority:** Start with files that have fewest ignores
- **Files:**
  - reactor/daemon.py: 1 ignore
  - reactor/network/tcp.py: 1 ignore
  - configuration/flow/scope.py: 1 ignore
  - (etc.)

#### 5.2 Fix Remaining Edge Cases (70 errors, 6 hours)
- **Action:** Handle all remaining misc errors
- **Approach:** Case-by-case analysis and fix

#### 5.3 Enable Strict Mode (3 hours)
- **Action:** Add to pyproject.toml:
  ```toml
  [tool.mypy]
  strict = true
  warn_unreachable = true
  warn_return_any = true
  ```
- **Fix:** Any new errors revealed by strict mode

**Phase 5 Target:** 0 errors, 0 type: ignore comments ✅

---

## Testing Strategy

**After Each Phase:**
1. ✅ `ruff format src && ruff check src`
2. ✅ `env exabgp_log_enable=false pytest ./tests/unit/ -x -q` (1376 tests)
3. ✅ `./qa/bin/functional encoding` (1870 tests)
4. ✅ `./qa/bin/functional decoding` (360 tests)
5. ✅ `./sbin/exabgp configuration validate -nrv ./etc/exabgp/conf-ipself6.conf`

**Continuous Validation:**
- Run mypy after each file/group of files fixed
- Ensure error count decreases monotonically
- Commit working changes frequently

---

## Risk Mitigation

### High-Risk Changes
1. **Flow architecture refactor (Phase 4.1)**
   - Risk: Breaking existing flow functionality
   - Mitigation: Extensive functional testing, staged rollout

2. **Message/NLRI hierarchy changes (Phase 3.3, 3.2)**
   - Risk: API breaking changes
   - Mitigation: Check for external usage, maintain backward compatibility

### Medium-Risk Changes
1. **Optional type elimination (Phase 4.2)**
   - Risk: Runtime errors from None access
   - Mitigation: Comprehensive assertions and guards

2. **Method signature changes (Phase 3)**
   - Risk: Breaking subclass contracts
   - Mitigation: Use mypy --strict to catch all issues

---

## Success Metrics

### Phase Completion Criteria
- [ ] Phase 1: Error count ≤ 380
- [ ] Phase 2: Error count ≤ 285
- [ ] Phase 3: Error count ≤ 205
- [ ] Phase 4: Error count ≤ 70
- [ ] Phase 5: Error count = 0, type: ignore count = 0

### Quality Gates
- All tests pass (4606 total)
- No runtime regressions
- Code coverage maintained or improved
- Performance impact < 5%

---

## Alternative Strategies

### Option A: Incremental Adoption (Recommended)
- Fix errors phase by phase as outlined above
- 80-120 hours total
- Full compliance in 4-6 weeks

### Option B: Selective Compliance
- Fix easy wins (Phases 1-2 only)
- Accept remaining errors with documented type: ignore
- ~25-35 hours
- Achieves ~70% error reduction

### Option C: Strict New Code Only
- Enable mypy only for new modules
- Legacy code excluded via mypy.ini
- Minimal effort (~5 hours setup)
- Gradual improvement over time

---

## Recommendation

**Proceed with Option A (Incremental Adoption):**

**Rationale:**
1. ✅ Already 56% of the way there (505 errors from 1,149)
2. ✅ Most errors are mechanical fixes (type guards, imports)
3. ✅ Only 1 major architectural issue (Flow inheritance)
4. ✅ High ROI: Better IDE support, catch bugs at compile time
5. ✅ Clean codebase for future development

**Start with Phase 1 this week:**
- Low risk, high reward
- Build momentum with quick wins
- Validate testing/workflow processes

---

## Next Steps

1. **Get approval** for plan and time allocation
2. **Start Phase 1.1:** Remove unused-ignore comments (2 hours)
3. **Track progress** in this document
4. **Review** after Phase 1 completion to adjust plan

---

## Progress Tracking

### Completed
- ✅ Baseline assessment (1,149 errors)
- ✅ Remove 698 type: ignore comments (previous work)
- ✅ Fix BGP-LS/EVPN Any types (10 files, 40 instances)
- ✅ Fix peer: Any → Peer (4 instances in processes.py)
- ✅ **Phase 1.1: Remove 35 unused-ignore comments** (9 files)
  - reactor/protocol.py (15), reactor/api/transcoder.py (5), reactor/peer.py (4)
  - bgp/message/update/nlri/bgpls/nlri.py (3), configuration/check.py (2)
  - configuration/static/parser.py (2), and 3 others
- ✅ **Phase 1.2: Fix 6 errors properly (zero type: ignore added)**
  - labels.py: Fixed List type annotation
  - inet.py/ipvpn.py: Added Union[IP, _NoNextHop] type
  - rt_record.py: Fixed method call (unpack → unpack_attribute)
  - notification.py: Made negotiated Optional (NOTE: Should be reverted to use mocks)
  - inet.py: Added missing imports

### In Progress
- ⏸️ Phase 1: Paused - awaiting decision on Optional usage policy

### Pending
- ⏸️ Phase 2: Attribute/Module Issues (~95 errors)
- ⏸️ Phase 3: Override and Assignment (~80 errors)
- ⏸️ Phase 4: Architecture Refactoring (~135 errors)
- ⏸️ Phase 5: Final Cleanup (~70 errors)

### Important Notes
- **TODO:** notification.py change (making negotiated Optional) goes against preferred approach
  - Should revert to required parameter: `def unpack_message(cls, data: bytes, negotiated: Negotiated)`
  - Update tests to create real Negotiated objects or mocks
  - Example: `test_negotiated = Negotiated(test_neighbor, Direction.IN)`
  - This demonstrates core principle: avoid Optional, use real objects in tests

---

**Last Updated:** 2025-11-15 (Phase 1 partial completion)
**Current Errors:** 584 (down from 1,149 baseline)
**Errors Fixed:** 565 (49.2% reduction)
**Target:** 0
**Progress:** 49% complete
