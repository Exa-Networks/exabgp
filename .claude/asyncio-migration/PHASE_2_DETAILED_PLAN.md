# Phase 2: Async Event Loop Integration - Detailed Plan

**Created:** 2025-11-17
**Status:** DRAFT - Awaiting User Approval
**Risk Level:** CRITICAL - Architectural change affecting core event loop
**Dependencies:** Phase 1 complete ✅

---

## CRITICAL ANALYSIS: Why Phase 2 Is Different

### The Challenge

Phase 1 was **SAFE** because:
- Added NEW methods alongside existing ones
- No existing code was modified
- Zero behavior changes
- 100% backward compatible

Phase 2 is **VERY HIGH RISK** because:
- Must modify the CORE event loop
- Event loop is critical path for ALL BGP operations
- Any bug affects ALL peers, ALL connections
- Hard to test incrementally (event loop is atomic)

### The Problem

The current architecture has a **circular dependency**:

```
loop.run() (sync)
  ↓
  calls peer.run() which returns generator
  ↓
  advances generator with next()/send()
  ↓
  generator yields control back to loop
  ↓
  loop.run() continues
```

**You cannot convert just ONE piece to async/await** because:
- If `loop.run()` becomes async, it needs `await peer.run()`
- But `peer.run()` returns a generator, not a coroutine
- Generators cannot be awaited
- Must convert BOTH at once OR create a bridge

---

## RECOMMENDATION: Phase 2 Should Be Split

After analyzing the PoC and the actual codebase, I recommend:

### Option A: STOP HERE (CONSERVATIVE)

**Rationale:**
- Phase 1 added async I/O infrastructure
- But we're NOT actually using it yet
- The current generator-based system WORKS
- Risk of Phase 2 is VERY HIGH
- Benefit is unclear (asyncio doesn't help if we keep generators)

**Action:**
- Keep current generator-based event loop
- Don't integrate async I/O (it's there if needed later)
- Continue with other lower-risk async migrations

### Option B: DEEP RESEARCH FIRST (RECOMMENDED)

**Rationale:**
- Need to prototype the integration in isolation
- Test performance implications
- Understand edge cases
- Make data-driven decision

**Action:**
1. Create a standalone integration test
2. Run performance benchmarks
3. Test with real BGP traffic
4. If successful AND shows benefit → proceed
5. If risky OR no benefit → STOP

### Option C: PROCEED WITH INTEGRATION (HIGH RISK)

**If you choose this option**, we need a VERY detailed plan with:
- Incremental steps that maintain working state
- Extensive testing at each step
- Clear rollback strategy
- Performance benchmarking

---

## IF PROCEEDING WITH OPTION C: Integration Steps

**WARNING: This is HIGH RISK. Consider Options A or B first.**

### Step 1: Add configuration flag

**File:** `src/exabgp/environment.py` (or appropriate config location)

**Changes:**
- Add `reactor.use_asyncio` flag (default: False)
- This allows switching between sync/async modes

**Verification:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:** All tests pass (flag added, not used yet)

---

### Step 2: Create async version of peer.run()

**File:** `src/exabgp/reactor/peer.py`

**Changes:**
- Add `run_async()` method alongside `run()`
- Keep existing `run()` unchanged

**Challenge:** The `run()` method calls generators like `_run()`, which yield.
Need to wrap these generators to work with async.

**Verification:**
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/ -q
```

**Expected:** All tests pass

---

### Step 3-N: [MORE STEPS NEEDED]

**At this point, the plan becomes VERY complex because:**

1. Need to wrap ALL generator-based state machines
2. Need to modify event loop to use asyncio.run()
3. Need to ensure both modes work
4. Need extensive testing of both modes

**This could be 20-30+ steps, each requiring careful verification.**

---

## HONEST ASSESSMENT

After reviewing the architecture and the PoCs:

### What We Learned from Phase 1

- Async I/O methods are EASY to add
- They coexist nicely with generators
- No integration issues when they're NOT used

### What Phase 2 Reveals

- **Integration is HARD** - circular dependencies
- **Risk is HIGH** - core event loop
- **Benefit is UNCLEAR** - what do we gain?
  - Generators work fine for state machines
  - asyncio I/O is only useful if event loop uses it
  - But event loop needs generators for state machines

### The Hybrid Approach Reality Check

The PoC showed hybrid approach works for a **SIMPLE** example.
But the real codebase has:
- Complex generator-based FSM
- Multiple layers of generators calling generators
- External process communication
- Signal handling
- Listener management

**Converting all of this while maintaining stability is VERY difficult.**

---

## MY RECOMMENDATION

**PAUSE Phase 2 and choose one of:**

### Path 1: Keep Current Architecture (SAFEST)

- Phase 1 work is not wasted (infrastructure is there)
- Current generator system works well
- Focus on other improvements
- Revisit async integration later if compelling reason emerges

### Path 2: Proof of Concept Integration (SAFER)

- Create a FULL integration PoC with real BGP peers
- Test in isolated environment
- Measure performance difference
- Verify stability
- **ONLY proceed if PoC shows clear benefit**

### Path 3: Proceed with Integration (RISKIEST)

- Requires 30-40 detailed steps
- Each step needs verification
- Multiple commits
- Extensive testing
- Could take 20-40 hours
- High chance of discovering blockers mid-way

---

## Questions for User

Before creating a detailed Phase 2 plan, please answer:

1. **What is the PRIMARY GOAL of async migration?**
   - [ ] Better performance?
   - [ ] Modern code style?
   - [ ] Integration with asyncio libraries?
   - [ ] Something else?

2. **What is your RISK TOLERANCE?**
   - [ ] Conservative - only low-risk changes
   - [ ] Moderate - willing to do PoC first
   - [ ] Aggressive - proceed with integration

3. **What is the DEADLINE?**
   - [ ] No deadline - can take time to do it right
   - [ ] Urgent - need to complete soon
   - [ ] Flexible - want it done but not rushed

4. **Are you willing to REVERT if Phase 2 fails?**
   - [ ] Yes - Phase 1 work is acceptable stopping point
   - [ ] No - must complete full async migration
   - [ ] Depends on reason for failure

---

## Recommended Next Steps

Based on my analysis, I recommend:

**Option B: Deep Research First**

1. Create a complete integration PoC (4-6 hours)
2. Test with real configuration (2 hours)
3. Run performance benchmarks (2 hours)
4. Analyze results (1 hour)
5. Make informed decision (30 min)

**Total: 10-12 hours before committing to full integration**

This approach:
- ✅ Validates the approach works in real codebase
- ✅ Identifies problems early
- ✅ Provides performance data
- ✅ Allows informed go/no-go decision
- ✅ Minimizes risk of wasted effort

---

## Approval Required

Please choose:

- [ ] **Option A** - Stop here, keep current architecture
- [ ] **Option B** - Deep research/PoC first (RECOMMENDED)
- [ ] **Option C** - Proceed with integration (need detailed 30-40 step plan)
- [ ] **Option D** - Something else (please specify)

---

**Awaiting your decision before proceeding...**
