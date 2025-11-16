# Incremental Pack Method Rename Plan - Ultra-Careful Approach

**Created:** 2025-11-16
**Baseline Commit:** 52c0c040d390a08b13d9bbcbd57c5155c57aa3b8 (known-good, 100% test pass rate)
**Strategy:** ONE function rename at a time, FULL testing after each, WAIT for approval before continuing

---

## Analysis Summary

The agent analyzed 5 commits made after the known-good baseline:

1. **d9417000** - Pack: Rename ESI.pack() to ESI.pack_esi()
2. **549edbca** - Phase 1: Standardize NLRI qualifier pack() methods (6 qualifiers)
3. **04b88769** - Phase 6: Rename Attribute.pack() to pack_attribute() (19+ attributes)
4. **83016a43** - Phase 7: Rename Message.message() to pack_message() (8+ messages)
5. **d396c68f** - Require negotiated parameter in all pack_attribute() calls

**Key Finding:** These commits batched multiple function renames together, making it hard to identify which specific rename caused test failures.

**Solution:** Break down into 40+ individual steps, each renaming ONE function only.

---

## Phase 0: Reset to Known-Good State

### Step 0.1: Hard Reset
```bash
git reset --hard 52c0c040d390a08b13d9bbcbd57c5155c57aa3b8
```

### Step 0.2: Verify Baseline (Must be 100% pass)
```bash
# Lint
ruff format src && ruff check src

# Unit tests
env exabgp_log_enable=false pytest ./tests/unit/ -x -q

# Functional encoding tests (ALL)
./qa/bin/functional encoding
```

**Expected Result:** ALL tests pass (baseline verification)

**Action:** Confirm baseline with user before proceeding to Phase 1

---

## Phase 1: NLRI Qualifiers (6 Individual Function Renames)

### Step 1.1: ESI.pack() → pack_esi()

**Method Definition:**
- File: `src/exabgp/bgp/message/update/nlri/qualifier/esi.py:58`
- Change: `def pack(self)` → `def pack_esi(self)`

**Call Sites (6 files):**
1. `src/exabgp/bgp/message/update/nlri/evpn/ethernetad.py` - 1 call: `self.esi.pack()` → `self.esi.pack_esi()`
2. `src/exabgp/bgp/message/update/nlri/evpn/mac.py` - 1 call: `self.esi.pack()` → `self.esi.pack_esi()`
3. `src/exabgp/bgp/message/update/nlri/evpn/prefix.py` - 1 call: `self.esi.pack()` → `self.esi.pack_esi()`
4. `src/exabgp/bgp/message/update/nlri/evpn/segment.py` - 1 call: `self.esi.pack()` → `self.esi.pack_esi()`
5. `tests/unit/test_evpn.py` - 2 calls: `.esi.pack()` → `.esi.pack_esi()`

**Total Changes:** 1 definition + 6 call sites = 7 edits

**Testing Commands:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -x -q
./qa/bin/functional encoding
```

**Success Criteria:** ALL tests pass

**Commit Message:** `Pack: Rename ESI.pack() to ESI.pack_esi()`

**Action After Success:** STOP and WAIT for user approval before Step 1.2

---

### Step 1.2: Labels.pack() → pack_labels()

**Method Definition:**
- File: `src/exabgp/bgp/message/update/nlri/qualifier/labels.py:73`
- Change: `def pack(self, negotiated=None)` → `def pack_labels(self, negotiated=None)`

**Call Sites (~12 files):**
1. `src/exabgp/bgp/message/update/nlri/evpn/ethernetad.py` - 1 call: `self.label.pack()` → `self.label.pack_labels()`
2. `src/exabgp/bgp/message/update/nlri/evpn/mac.py` - 1 call: `self.label.pack()` → `self.label.pack_labels()`
3. `src/exabgp/bgp/message/update/nlri/evpn/prefix.py` - 1 call: `self.label.pack()` → `self.label.pack_labels()`
4. `src/exabgp/bgp/message/update/nlri/ipvpn.py` - 2 calls: `.labels.pack()` → `.labels.pack_labels()`
5. `src/exabgp/bgp/message/update/nlri/label.py` - 2 calls: `.labels.pack()` → `.labels.pack_labels()`
6. `tests/unit/test_evpn.py` - calls in tests
7. Other NLRI files that use Labels

**Testing Commands:** (same as above)

**Commit Message:** `Pack: Rename Labels.pack() to Labels.pack_labels()`

**Action After Success:** STOP and WAIT for user approval before Step 1.3

---

### Step 1.3: EthernetTag.pack() → pack_etag()

**Method Definition:**
- File: `src/exabgp/bgp/message/update/nlri/qualifier/etag.py:53`
- Change: `def pack(self)` → `def pack_etag(self)`

**Call Sites (~7 files):**
1. `src/exabgp/bgp/message/update/nlri/evpn/ethernetad.py` - 1 call: `self.etag.pack()` → `self.etag.pack_etag()`
2. `src/exabgp/bgp/message/update/nlri/evpn/mac.py` - 1 call: `self.etag.pack()` → `self.etag.pack_etag()`
3. `src/exabgp/bgp/message/update/nlri/evpn/multicast.py` - 1 call: `self.etag.pack()` → `self.etag.pack_etag()`
4. `src/exabgp/bgp/message/update/nlri/evpn/prefix.py` - 1 call: `self.etag.pack()` → `self.etag.pack_etag()`
5. `tests/unit/test_evpn.py` - calls in tests

**Testing Commands:** (same as above)

**Commit Message:** `Pack: Rename EthernetTag.pack() to EthernetTag.pack_etag()`

**Action After Success:** STOP and WAIT for user approval before Step 1.4

---

### Step 1.4: RouteDistinguisher.pack() → pack_rd()

**Method Definition:**
- File: `src/exabgp/bgp/message/update/nlri/qualifier/rd.py:191`
- Change: `def pack(self, negotiated=None)` → `def pack_rd(self, negotiated=None)`

**Call Sites (~20 files - MOST IMPACTFUL):**

**EVPN NLRIs (4 files):**
1. `src/exabgp/bgp/message/update/nlri/evpn/ethernetad.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
2. `src/exabgp/bgp/message/update/nlri/evpn/mac.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
3. `src/exabgp/bgp/message/update/nlri/evpn/multicast.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
4. `src/exabgp/bgp/message/update/nlri/evpn/prefix.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`

**MUP NLRIs (4 files):**
5. `src/exabgp/bgp/message/update/nlri/mup/dsd.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
6. `src/exabgp/bgp/message/update/nlri/mup/isd.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
7. `src/exabgp/bgp/message/update/nlri/mup/t1st.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
8. `src/exabgp/bgp/message/update/nlri/mup/t2st.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`

**MVPN NLRIs (3 files):**
9. `src/exabgp/bgp/message/update/nlri/mvpn/sharedjoin.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
10. `src/exabgp/bgp/message/update/nlri/mvpn/sourcead.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
11. `src/exabgp/bgp/message/update/nlri/mvpn/sourcejoin.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`

**Other NLRIs (2 files):**
12. `src/exabgp/bgp/message/update/nlri/flow.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`
13. `src/exabgp/bgp/message/update/nlri/vpls.py` - 1 call: `self.rd.pack()` → `self.rd.pack_rd()`

**Test Files (3 files):**
14. `tests/unit/test_evpn.py` - multiple calls
15. `tests/unit/test_mup.py` - multiple calls
16. `tests/unit/test_mvpn.py` - multiple calls

**Testing Commands:** (same as above)

**Commit Message:** `Pack: Rename RouteDistinguisher.pack() to RouteDistinguisher.pack_rd()`

**Action After Success:** STOP and WAIT for user approval before Step 1.5

---

### Step 1.5: PathInfo.pack() → pack_path()

**Method Definition:**
- File: `src/exabgp/bgp/message/update/nlri/qualifier/path.py:44`
- Change: `def pack(self, negotiated=None)` → `def pack_path(self, negotiated=None)`

**Call Sites (~8 files):**
1. `src/exabgp/bgp/message/update/nlri/inet.py` - 4 calls: `self.path_info.pack(negotiated)` → `self.path_info.pack_path(negotiated)`
2. `src/exabgp/bgp/message/update/nlri/ipvpn.py` - 2 calls: `self.path_info.pack(negotiated)` → `self.path_info.pack_path(negotiated)`
3. `src/exabgp/bgp/message/update/nlri/label.py` - 2 calls: `self.path_info.pack(negotiated)` → `self.path_info.pack_path(negotiated)`

**Testing Commands:** (same as above)

**Commit Message:** `Pack: Rename PathInfo.pack() to PathInfo.pack_path()`

**Action After Success:** STOP and WAIT for user approval before Step 1.6

---

### Step 1.6: MAC.pack() → pack_mac()

**Method Definition:**
- File: `src/exabgp/bgp/message/update/nlri/qualifier/mac.py:78`
- Change: `def pack(self)` → `def pack_mac(self)`

**Call Sites (~3 files):**
1. `src/exabgp/bgp/message/update/nlri/evpn/mac.py` - 1 call: `self.mac.pack()` → `self.mac.pack_mac()`
2. `tests/unit/test_evpn.py` - calls in tests

**Testing Commands:** (same as above)

**Commit Message:** `Pack: Rename MAC.pack() to MAC.pack_mac()`

**Action After Success:** Phase 1 complete! STOP and WAIT for user approval before Phase 2

---

## Phase 1 Summary

**Total Steps:** 6 individual function renames
**Total Files Modified:** ~30 files
**Total Edits:** ~50 individual changes
**Time per Step:** 5-10 minutes
**Total Phase 1 Time:** 30-60 minutes

**Success Criteria:**
- ✅ Each step passes ALL tests (ruff, pytest, functional)
- ✅ User approves each step before proceeding
- ✅ Clean commit after each successful step

---

## Phase 2: Attributes (19+ Individual Function Renames)

**IMPORTANT:** Phase 2 will NOT start until Phase 1 is 100% complete and approved.

### Attributes to Rename (All .pack() → .pack_attribute())

Each is a separate step with full testing:

1. **Step 2.1:** `Origin.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/origin.py`
   - Call sites: `attributes.py`, `origin.py` (setCache), tests
   - **Note:** Origin has internal calls in setCache() that need updating

2. **Step 2.2:** `ASPath.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/aspath.py`
   - Call sites: `attributes.py`, tests

3. **Step 2.3:** `AS4Path.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/aspath.py` (same file as ASPath)
   - Call sites: `attributes.py`, tests

4. **Step 2.4:** `NextHop.pack()` + `NextHopSelf.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/nexthop.py`
   - Call sites: `attributes.py`, tests
   - **Note:** Two classes in same file, do together

5. **Step 2.5:** `LocalPreference.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/localpref.py`
   - Call sites: `attributes.py`, tests

6. **Step 2.6:** `MED.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/med.py`
   - Call sites: `attributes.py`, tests

7. **Step 2.7:** `AtomicAggregate.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/atomicaggregate.py`
   - Call sites: `attributes.py`, tests

8. **Step 2.8:** `Aggregator.pack()` + `Aggregator4.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/aggregator.py`
   - Call sites: `attributes.py`, `aggregator.py` (internal), tests
   - **Note:** Aggregator has internal call to Aggregator4.pack()

9. **Step 2.9:** `OriginatorID.pack()` → `pack_attribute()`
   - File: `src/exabgp/bgp/message/update/attribute/originatorid.py`
   - Call sites: `attributes.py`, tests

10. **Step 2.10:** `ClusterList.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/clusterlist.py`
    - Call sites: `attributes.py`, tests

11. **Step 2.11:** `Community.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/community/initial/community.py`
    - Call sites: `attributes.py`, tests

12. **Step 2.12:** `Communities.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/community/initial/communities.py`
    - Call sites: `attributes.py`, tests

13. **Step 2.13:** `ExtendedCommunity.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/community/extended/community.py`
    - Call sites: `attributes.py`, `rtc.py`, tests
    - **Note:** Base class for many extended community types
    - **CRITICAL:** This affects RTC.pack_nlri() which calls RouteTarget.pack()

14. **Step 2.14:** `LargeCommunity.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/community/large/community.py`
    - Call sites: `attributes.py`, tests

15. **Step 2.15:** `AIGP.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/aigp.py`
    - Call sites: `attributes.py`, tests

16. **Step 2.16:** `PMSI.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/pmsi.py`
    - Call sites: `attributes.py`, tests

17. **Step 2.17:** `PrefixSid.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/sr/prefixsid.py`
    - Call sites: `attributes.py`, tests

18. **Step 2.18:** `MPRNLRI.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/mprnlri.py`
    - Call sites: `attributes.py`, tests

19. **Step 2.19:** `MPURNLRI.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/mpurnlri.py`
    - Call sites: `attributes.py`, tests

20. **Step 2.20:** `GenericAttribute.pack()` → `pack_attribute()`
    - File: `src/exabgp/bgp/message/update/attribute/generic.py`
    - Call sites: `attributes.py`, tests

**Testing Commands for Each Step:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -x -q
./qa/bin/functional encoding
```

**Commit Message Pattern:** `Pack: Rename <Attribute>.pack() to <Attribute>.pack_attribute()`

**Action After Each Step:** STOP and WAIT for user approval

---

## Phase 3: Messages (8+ Individual Function Renames)

**IMPORTANT:** Phase 3 will NOT start until Phase 2 is 100% complete and approved.

### Messages to Rename (All .message() → .pack_message())

Each is a separate step with full testing:

1. **Step 3.1:** `KeepAlive.message()` → `pack_message()`
   - File: `src/exabgp/bgp/message/keepalive.py`
   - Call sites: `protocol.py` (write method), tests

2. **Step 3.2:** `Notification.message()` → `pack_message()`
   - File: `src/exabgp/bgp/message/notification.py`
   - Call sites: `protocol.py`, `incoming.py`, tests

3. **Step 3.3:** `Open.message()` → `pack_message()`
   - File: `src/exabgp/bgp/message/open/__init__.py`
   - Call sites: `protocol.py`, tests

4. **Step 3.4:** `RouteRefresh.message()` → `pack_message()`
   - File: `src/exabgp/bgp/message/refresh.py`
   - Call sites: `protocol.py`, `refresh.py` (messages method), tests
   - **Note:** Has internal call in messages() method

5. **Step 3.5:** `EOR.message()` → `pack_message()`
   - File: `src/exabgp/bgp/message/update/eor.py`
   - Call sites: `protocol.py`, tests

6. **Step 3.6:** `Operational.message()` → `pack_message()`
   - File: `src/exabgp/bgp/message/operational.py`
   - Call sites: `protocol.py`, tests
   - **Note:** Multiple operational message subclasses

7. **Step 3.7:** `NOP.message()` → `pack_message()`
   - File: `src/exabgp/bgp/message/nop.py`
   - Call sites: `protocol.py`, tests

8. **Step 3.8:** `UnknownMessage.message()` → `pack_message()`
   - File: `src/exabgp/bgp/message/unknown.py`
   - Call sites: `protocol.py`, tests

9. **Step 3.9:** `Message.message()` → `pack_message()` (Base Class)
   - File: `src/exabgp/bgp/message/message.py`
   - **Note:** Base class, might need to do FIRST or LAST depending on inheritance

**Testing Commands for Each Step:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -x -q
./qa/bin/functional encoding
```

**Commit Message Pattern:** `Pack: Rename <Message>.message() to <Message>.pack_message()`

**Action After Each Step:** STOP and WAIT for user approval

---

## Phase 4: Parameter Requirements (Cleanup)

**IMPORTANT:** Phase 4 will NOT start until Phase 3 is 100% complete and approved.

### Step 4.1: Ensure negotiated parameter is passed to pack_attribute()

**Files to update:**
1. `src/exabgp/bgp/message/update/attribute/origin.py` - Origin.setCache() internal calls
2. `src/exabgp/bgp/message/update/nlri/rtc.py` - RTC.pack_nlri() calls to RouteTarget.pack_attribute()
3. `src/exabgp/bgp/message/update/attribute/community/extended/rt_record.py` - RTRecord.from_rt()
4. All test files - pass `create_negotiated()` to pack_attribute() calls

**Testing Commands:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -x -q
./qa/bin/functional encoding
```

**Commit Message:** `Pack: Require negotiated parameter in all pack_attribute() calls`

**Action After Success:** COMPLETE! All pack method standardization done.

---

## Testing Protocol (MANDATORY FOR EVERY STEP)

### After Each Single Function Rename:

```bash
# Step 1: Lint
ruff format src && ruff check src
# Must show: "All checks passed!"

# Step 2: Unit Tests
env exabgp_log_enable=false pytest ./tests/unit/ -x -q
# Must show: "XXXX passed" with NO failures

# Step 3: Functional Encoding Tests
./qa/bin/functional encoding
# Must show: ALL tests pass (green checkmarks)
```

**ALL THREE must pass before declaring success.**

### If ANY Test Fails:

1. **STOP immediately**
2. **Analyze** the exact failure
3. **Investigate** root cause:
   - Missing call site?
   - Typo in rename?
   - Inheritance issue?
   - Test needs updating?
4. **Fix** the issue
5. **Retest** all three test suites
6. **Only proceed** when all tests pass

### After All Tests Pass:

1. **Report** to user: "Step X.Y complete - all tests pass"
2. **Show** test output summaries
3. **STOP** and WAIT for user approval
4. **Do NOT** proceed to next step until explicitly told

---

## Commit Strategy

After each successful step (with user approval):

```bash
git add -A
git commit -m "Pack: Rename <Class>.<method>() to <Class>.<new_method>()"
```

**Examples:**
- `Pack: Rename ESI.pack() to ESI.pack_esi()`
- `Pack: Rename Labels.pack() to Labels.pack_labels()`
- `Pack: Rename Origin.pack() to Origin.pack_attribute()`
- `Pack: Rename KeepAlive.message() to KeepAlive.pack_message()`

**NO batch commits.** One commit per function rename.

---

## Risk Mitigation

### Why This Approach Works:

1. **Isolation** - Each function rename is completely independent
2. **Verification** - Full test suite after each change catches issues immediately
3. **Rollback** - Can revert single commit if needed without losing other work
4. **Debugging** - If tests fail, exactly one function change to investigate
5. **Progress** - User can save work after each successful step
6. **Confidence** - Builds incrementally with verified success at each step

### What Could Go Wrong:

1. **Missing call site** - Test will fail, we fix, retest
2. **Inheritance issue** - Test will fail, we fix, retest
3. **Test needs update** - Test will fail, we update test, retest
4. **Typo in rename** - Ruff/pytest will fail, we fix, retest

**All issues are caught immediately and fixed before proceeding.**

---

## Success Metrics

### Phase 1 Success:
- ✅ 6 function renames complete
- ✅ 6 clean commits
- ✅ ALL tests passing
- ✅ User approved each step

### Phase 2 Success:
- ✅ 20 function renames complete
- ✅ 20 clean commits
- ✅ ALL tests passing
- ✅ User approved each step

### Phase 3 Success:
- ✅ 9 function renames complete
- ✅ 9 clean commits
- ✅ ALL tests passing
- ✅ User approved each step

### Phase 4 Success:
- ✅ Parameter requirements enforced
- ✅ 1 clean commit
- ✅ ALL tests passing
- ✅ User approval

### Overall Success:
- ✅ 36+ total commits (one per function)
- ✅ Perfect symmetry: unpack_X() ↔ pack_X()
- ✅ 100% test pass rate maintained throughout
- ✅ User confidence in each incremental step

---

## Estimated Timeline

### Phase 1: NLRI Qualifiers
- 6 steps × 5-10 minutes = 30-60 minutes
- Includes testing and waiting for approval

### Phase 2: Attributes
- 20 steps × 5-10 minutes = 100-200 minutes (1.5-3.5 hours)
- Includes testing and waiting for approval

### Phase 3: Messages
- 9 steps × 5-10 minutes = 45-90 minutes
- Includes testing and waiting for approval

### Phase 4: Cleanup
- 1 step × 10-15 minutes = 10-15 minutes

### Total Time
- **Minimum:** 3 hours
- **Maximum:** 6 hours
- **Realistic:** 4-5 hours (with breaks for user approval)

**This is MUCH safer than batching and risking failure.**

---

## Key Principles (NEVER VIOLATE)

1. ✅ **ONE function rename at a time**
2. ✅ **FULL testing after each change** (ruff + pytest + functional)
3. ✅ **STOP and WAIT** for user approval before continuing
4. ✅ **FIX immediately** if any test fails
5. ✅ **COMMIT after approval** with clear message
6. ✅ **NEVER proceed** without all tests passing
7. ✅ **NEVER batch** multiple functions together
8. ✅ **ALWAYS report** results before waiting

---

## Next Actions

1. ✅ **Save this plan** (done)
2. ⏳ **Get user approval** to start
3. ⏳ **Reset to baseline** (Phase 0)
4. ⏳ **Verify baseline** tests all pass
5. ⏳ **Start Step 1.1** (ESI rename only)
6. ⏳ **Test Step 1.1**
7. ⏳ **Report and WAIT**
8. ⏳ **Continue based on user direction**

---

**END OF PLAN**

This plan provides a complete, exhaustive, ultra-careful approach to applying the pack method standardization changes one function at a time with full testing and user approval at each step.
