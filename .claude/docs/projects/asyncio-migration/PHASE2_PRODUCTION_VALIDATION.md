# Phase 2: Production Validation

**Status:** IN PROGRESS
**Started:** 2025-11-18
**Objective:** Validate async/await mode stability and performance in production

---

## Prerequisites

### Phase 1: Implementation (COMPLETE ✅)

- ✅ All async functions implemented (57 functions)
- ✅ 100% test parity achieved (72/72 functional, 1376/1376 unit)
- ✅ Dual-mode architecture working
- ✅ CI testing both modes on Python 3.8-3.12
- ✅ Documentation complete

**See:** `GENERATOR_VS_ASYNC_EQUIVALENCE.md` for equivalence analysis

---

## Phase 2 Objectives

### 1. Production Stability Validation

**Goal:** Prove async mode is as stable as generator mode in production

**Success criteria:**
- Run continuously for 30+ days without issues
- No crashes or unexpected restarts
- BGP sessions maintain ESTABLISHED state
- Memory usage stable (no leaks)
- CPU usage comparable to generator mode

### 2. Performance Validation

**Goal:** Compare async vs generator mode performance

**Metrics to collect:**
- BGP message processing latency
- Session establishment time
- Memory footprint
- CPU utilization
- API command response time
- Concurrent peer handling

### 3. Edge Case Discovery

**Goal:** Find issues not caught by tests

**Areas to monitor:**
- High peer count scenarios (100+ peers)
- Route churn (frequent UPDATE messages)
- API command bursts
- Network instability (flapping connections)
- Long-running sessions (weeks/months)

---

## Validation Stages

### Stage 1: Development/QA Environment (2-4 weeks)

**Setup:**
- Deploy with `exabgp_reactor_asyncio=true`
- Mirror production topology
- Automated testing scripts
- Continuous monitoring

**Validation:**
- Run all functional tests daily
- Stress testing (100+ peers, route churn)
- API command load testing
- Memory leak detection (valgrind, tracemalloc)

**Success criteria:**
- All tests pass consistently
- No memory leaks detected
- Performance within 10% of generator mode
- No unexpected behavior

### Stage 2: Canary Production (4-6 weeks)

**Setup:**
- Select low-risk production deployment
- Enable async mode on single instance
- Keep generator mode on remaining instances
- Enhanced monitoring and alerting

**Validation:**
- Compare metrics vs generator instances
- Monitor BGP session stability
- Track error logs
- User feedback (if applicable)

**Success criteria:**
- Metrics comparable to generator mode
- No production incidents
- BGP sessions stable
- No rollbacks required

**Rollback plan:**
- Disable async mode: `exabgp_reactor_asyncio=false`
- Restart ExaBGP instance
- Validate generator mode operational
- Document issues found

### Stage 3: Expanded Production (6-8 weeks)

**Setup:**
- Expand to 25-50% of production instances
- Include diverse peer scenarios
- Maintain generator mode on critical instances
- Continue monitoring

**Validation:**
- Larger sample size for metrics
- Edge cases from varied deployments
- Performance comparison at scale
- Stability over time

**Success criteria:**
- No async-specific issues found
- Performance parity confirmed
- User confidence established
- Ready for wider rollout

### Stage 4: Full Production (8-12 weeks)

**Setup:**
- Deploy async mode to all instances
- Generator mode still available (opt-out)
- Comprehensive monitoring

**Validation:**
- All production traffic on async mode
- Final performance validation
- User acceptance
- Prepare for Phase 3 (default switch)

**Success criteria:**
- 100% of production on async mode
- No open async-related bugs
- Performance meets/exceeds expectations
- Community feedback positive

---

## Enabling Async Mode in Production

### Configuration Methods

#### Method 1: Environment Variable

```bash
# Single instance
exabgp_reactor_asyncio=true /usr/local/bin/exabgp /etc/exabgp/exabgp.conf

# Export for multiple commands
export exabgp_reactor_asyncio=true
/usr/local/bin/exabgp /etc/exabgp/exabgp.conf
```

#### Method 2: Systemd Service

**Edit:** `/etc/systemd/system/exabgp.service`

```ini
[Service]
Environment="exabgp_reactor_asyncio=true"
ExecStart=/usr/local/bin/exabgp /etc/exabgp/exabgp.conf
```

**Reload:**
```bash
systemctl daemon-reload
systemctl restart exabgp
```

#### Method 3: Configuration File

**Add to:** `/etc/exabgp/exabgp.env`

```ini
[exabgp.reactor]
asyncio = true
```

**Load environment:**
```bash
exabgp /etc/exabgp/exabgp.conf --env /etc/exabgp/exabgp.env
```

### Verification

**Check logs for async mode confirmation:**
```bash
journalctl -u exabgp | grep -i async
# OR
tail -f /var/log/exabgp/exabgp.log | grep -i async
```

**Expected:** Log messages indicating asyncio event loop started

---

## Monitoring Checklist

### System Metrics

**Process monitoring:**
```bash
# Memory usage
ps aux | grep exabgp | awk '{print $6}'  # RSS in KB

# CPU usage
top -p $(pidof exabgp) -b -n 1 | tail -1

# File descriptors
lsof -p $(pidof exabgp) | wc -l
```

**Automated monitoring:**
- Set up Prometheus/Grafana for ExaBGP metrics
- Alert on memory increase > 10% over 24 hours
- Alert on unexpected restarts
- Track BGP session count and state

### BGP Metrics

**Session state:**
```bash
# Via API (if enabled)
echo '{"exabgp": "3.4.0", "command": "neighbor json"}' | socat - /var/run/exabgp.sock

# Expected: All peers in "up" state
```

**Message counters:**
- OPEN messages sent/received
- UPDATE messages sent/received
- KEEPALIVE timing
- NOTIFICATION errors (should be zero)

### Application Metrics

**Log monitoring:**
```bash
# Watch for errors
journalctl -u exabgp -f | grep -i -E "error|exception|traceback"

# Session establishment
journalctl -u exabgp | grep -i "established"

# API commands processed
journalctl -u exabgp | grep -i "api"
```

**Key indicators:**
- No Python tracebacks
- Session establishment times normal
- API responsiveness maintained

---

## Performance Comparison Template

### Baseline Collection (Generator Mode)

**Run before switching to async:**

```bash
# Session establishment time (average of 10)
time_start=$(date +%s)
systemctl restart exabgp
# Wait for all sessions ESTABLISHED
time_end=$(date +%s)
echo "Establishment: $((time_end - time_start))s"

# Memory footprint (after 24h uptime)
ps -o rss= -p $(pidof exabgp)

# CPU usage (average over 1 hour)
pidstat -p $(pidof exabgp) 1 3600 | awk '{sum+=$7; count++} END {print sum/count}'
```

**Record:**
- Session establishment time: _____ seconds
- Memory RSS after 24h: _____ MB
- CPU usage average: _____ %
- Peak CPU during session setup: _____ %

### Async Mode Testing

**Run with async enabled:**

```bash
# Same tests as baseline
exabgp_reactor_asyncio=true systemctl restart exabgp
# ... collect same metrics ...
```

**Record:**
- Session establishment time: _____ seconds
- Memory RSS after 24h: _____ MB
- CPU usage average: _____ %
- Peak CPU during session setup: _____ %

### Comparison

| Metric | Generator | Async | Delta | Status |
|--------|-----------|-------|-------|--------|
| Establishment time | ___s | ___s | ___% | ✅/❌ |
| Memory (24h) | ___MB | ___MB | ___% | ✅/❌ |
| CPU avg | ___% | ___% | ___% | ✅/❌ |
| CPU peak | ___% | ___% | ___% | ✅/❌ |

**Acceptance:** Async within ±10% of generator mode

---

## Issue Tracking

### Known Issues (if any)

**Template for reporting:**

```markdown
## Issue #N: [Short description]

**Severity:** Critical / High / Medium / Low
**Async-specific:** Yes / No / Unknown

**Symptoms:**
- [What happened]

**Reproduction:**
1. [Steps to reproduce]
2. ...

**Environment:**
- Python version:
- ExaBGP commit:
- OS:
- Peer count:

**Workaround:**
- [If available]

**Status:** Open / In Progress / Fixed / Wont Fix
```

### Regression Testing

**If issues found:**
1. Create minimal reproduction test
2. Add to functional test suite
3. Verify generator mode unaffected
4. Fix async implementation
5. Verify fix with new test
6. Re-run full validation

---

## Rollback Procedures

### Emergency Rollback (Immediate)

**If critical issue in production:**

```bash
# Method 1: Environment variable
unset exabgp_reactor_asyncio
systemctl restart exabgp

# Method 2: Systemd service
systemctl stop exabgp
# Remove Environment line from service file
systemctl daemon-reload
systemctl start exabgp

# Method 3: Configuration file
# Comment out asyncio=true
systemctl restart exabgp
```

**Validation:**
```bash
# Verify generator mode active
journalctl -u exabgp -n 100 | grep -v async
# Should NOT see asyncio references

# Verify sessions establish
# Monitor for 15 minutes
```

### Planned Rollback (Staged Validation)

**If issues found during testing:**
1. Document issue thoroughly
2. Collect logs and metrics
3. Plan fix in development
4. Roll back affected instances
5. Continue generator mode
6. Resume Phase 2 after fix

---

## Success Criteria Checklist

### Stage 1: Development/QA

- [ ] All functional tests pass (72/72)
- [ ] All unit tests pass (1376/1376)
- [ ] Stress test: 100+ peers, 24h+ uptime
- [ ] Memory leak test: No growth over 48h
- [ ] API load test: 1000+ commands/second
- [ ] Performance within 10% of generator

### Stage 2: Canary Production

- [ ] 30+ days uptime without restart
- [ ] Zero async-specific incidents
- [ ] Metrics match generator instances
- [ ] BGP sessions stable (zero flaps)
- [ ] No rollbacks required

### Stage 3: Expanded Production

- [ ] 50%+ instances on async mode
- [ ] Diverse peer scenarios covered
- [ ] Edge cases tested (high load, flapping, etc.)
- [ ] Performance validated at scale
- [ ] User feedback positive

### Stage 4: Full Production

- [ ] 100% instances on async mode
- [ ] No open async-related bugs
- [ ] Performance meets expectations
- [ ] Community acceptance
- [ ] Ready for Phase 3 (default switch)

**When ALL checked:** Phase 2 complete, proceed to Phase 3

---

## Timeline

### Estimated Duration: 3-6 months

**Breakdown:**
- Stage 1 (Dev/QA): 2-4 weeks
- Stage 2 (Canary): 4-6 weeks
- Stage 3 (Expanded): 6-8 weeks
- Stage 4 (Full): 8-12 weeks

**Variables affecting timeline:**
- Issue discovery and resolution
- Production deployment cycles
- User migration pace
- Performance validation rigor

**Accelerators:**
- No issues found (shorter stages)
- Automated testing (faster validation)
- Clear performance wins (faster adoption)

**Delays:**
- Issues requiring fixes (pause/restart)
- Performance regression (investigation)
- User concerns (slower rollout)

---

## Next Phase Preview

### Phase 3: Switch Default Mode

**After Phase 2 success:**
- Make async mode the default
- Generator mode becomes opt-out
- Update documentation
- Announce to community

**Timeline:** 3-6 months after Phase 2 completion

### Phase 4: Deprecation

**After Phase 3 success:**
- Announce generator mode deprecation
- 6-12 month warning period
- Migration support for holdouts
- Prepare for removal

**Timeline:** 6-12 months after Phase 3

### Phase 5: Removal

**After Phase 4 warning period:**
- Remove generator-based code (~2,000 lines)
- Simplify codebase (~40% reduction)
- Async/await only codebase
- Modernization complete

**Timeline:** 12-24 months from Phase 2 start

**Total migration timeline:** 18-36 months

---

## References

**Documentation:**
- `GENERATOR_VS_ASYNC_EQUIVALENCE.md` - Why both exist
- `docs/asyncio-migration/` - Complete technical docs
- `CLAUDE.md` - Usage instructions

**Code locations:**
- `src/exabgp/reactor/loop.py:427` - Mode selection
- `src/exabgp/environment/setup.py:309-314` - Configuration
- `src/exabgp/reactor/peer.py` - Dual implementation

**Testing:**
- `./qa/bin/functional encoding` - Functional tests
- `pytest ./tests/unit/` - Unit tests
- `.github/workflows/` - CI configuration

---

**Phase 2 Owner:** [To be assigned]
**Started:** 2025-11-18
**Target Completion:** 2025-Q2/Q3 2026
**Status:** READY TO BEGIN
