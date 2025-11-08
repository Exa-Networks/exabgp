# ExaBGP Testing Implementation Tasks

This directory contains detailed, step-by-step instructions for implementing the comprehensive testing strategy outlined in `TESTING_IMPROVEMENT_PLAN.md`.

## Task Organization

Each file represents a discrete phase of work that can be completed independently. Tasks are ordered by priority and dependency.

### Phase 0: Foundation
- **00-SETUP-FOUNDATION.md** - Set up testing infrastructure
  - Time: 2-3 hours
  - Must complete first
  - Sets up: Dependencies, directories, configuration, helpers

### Phase 1: Critical Path Fuzzing
- **01-FUZZ-MESSAGE-HEADER.md** - Fuzz BGP message header parser
  - Time: 3-4 hours
  - Target: `reactor/network/connection.py::reader()`
  - Goal: 95%+ coverage

- **02-FUZZ-UPDATE-MESSAGE.md** - Fuzz UPDATE message parser
  - Time: 6-8 hours
  - Target: `bgp/message/update/__init__.py::unpack_message()`
  - Goal: 85%+ coverage

- **03-FUZZ-ATTRIBUTES.md** - Fuzz path attributes parser
  - Time: 6-8 hours
  - Target: `bgp/message/update/attribute/attributes.py`
  - Goal: 85%+ coverage

- **04-FUZZ-OPEN-MESSAGE.md** - Fuzz OPEN message and capabilities
  - Time: 4-6 hours
  - Target: `bgp/message/open/__init__.py`
  - Goal: 90%+ coverage

### Phase 2: NLRI Type Fuzzing
- **05-FUZZ-NLRI-FLOW.md** - Fuzz FlowSpec NLRI
- **06-FUZZ-NLRI-EVPN.md** - Fuzz EVPN NLRI
- **07-FUZZ-NLRI-BGPLS.md** - Fuzz BGP-LS NLRI
- **08-FUZZ-NLRI-VPN.md** - Fuzz VPN NLRI types

### Phase 3: Configuration & State
- **09-FUZZ-CONFIGURATION.md** - Fuzz configuration parser
- **10-TEST-STATE-MACHINE.md** - Test BGP FSM
- **11-TEST-REACTOR.md** - Test reactor/event loop

### Phase 4: Integration & Performance
- **12-INTEGRATION-TESTS.md** - Integration test suite
- **13-PERFORMANCE-TESTS.md** - Performance benchmarks
- **14-SECURITY-TESTS.md** - Security-focused tests

### Phase 5: CI/CD & Automation
- **15-CI-FUZZING.md** - Continuous fuzzing in CI
- **16-COVERAGE-ENFORCEMENT.md** - Coverage thresholds in CI
- **17-REGRESSION-FRAMEWORK.md** - Regression test framework

## How to Use These Tasks

### 1. Start with Foundation
```bash
# Complete Phase 0 first
cat .claude/todo/00-SETUP-FOUNDATION.md
# Follow step-by-step instructions
```

### 2. Work Through Each Task
- Read the entire task file first
- Complete tasks in order within the file
- Check off completion checkboxes
- Verify acceptance criteria
- Run verification commands

### 3. Commit After Each Phase
Each task file includes a commit step. Commit your work frequently.

### 4. Track Progress
Update the completion checklists at the end of each file.

## Task File Structure

Each task file follows this structure:

```markdown
# Phase X: [Task Name]

**Estimated Time**: X hours
**Priority**: CRITICAL/HIGH/MEDIUM
**Depends On**: [Previous tasks]
**Target**: [Code being tested]

## Background
[Context and explanation]

## Task X.1: [Specific Task]
**File**: [Path to file]
**What to do**: [Detailed steps]
**Acceptance Criteria**: [Checkboxes]
**Verification**: [Commands to verify]

## Completion Checklist
[Final checklist]
```

## Estimated Timeline

| Phase | Tasks | Time | Cumulative |
|-------|-------|------|------------|
| 0 - Foundation | 1 | 2-3 hrs | 3 hrs |
| 1 - Critical Fuzzing | 4 | 19-26 hrs | 29 hrs |
| 2 - NLRI Fuzzing | 4 | 20-24 hrs | 53 hrs |
| 3 - Config & State | 3 | 15-18 hrs | 71 hrs |
| 4 - Integration | 3 | 12-15 hrs | 86 hrs |
| 5 - CI/CD | 3 | 6-8 hrs | 94 hrs |
| **Total** | **18** | **~94 hrs** | **~12 days** |

*Assuming 8-hour work days*

## Tips for Success

### 1. Read First, Code Second
- Read entire task before starting
- Understand the goal
- Plan your approach

### 2. Verify Frequently
- Run verification commands after each subtask
- Don't skip acceptance criteria checks
- Commit working code

### 3. Document as You Go
- Add comments to complex tests
- Document findings and issues
- Update task files with notes

### 4. Don't Skip Foundation
- Phase 0 is critical
- Proper setup saves time later
- Get it right the first time

### 5. Measure Coverage
- Run coverage after each phase
- Aim for the target percentages
- Add tests for uncovered lines

### 6. Run Extensive Fuzzing
- Use HYPOTHESIS_PROFILE=extensive periodically
- Let it run overnight
- Document any failures found

## Current Progress

**Last Updated**: [Date]

- [ ] 00-SETUP-FOUNDATION.md (0%)
- [ ] 01-FUZZ-MESSAGE-HEADER.md (0%)
- [ ] 02-FUZZ-UPDATE-MESSAGE.md (0%)
- [ ] 03-FUZZ-ATTRIBUTES.md (0%)
- [ ] 04-FUZZ-OPEN-MESSAGE.md (0%)

**Overall Progress**: 0/18 tasks (0%)

## Questions or Issues?

If you encounter issues:
1. Re-read the task instructions
2. Check the main TESTING_IMPROVEMENT_PLAN.md
3. Review existing tests for patterns
4. Document the issue and move to next task

## Contributing

When completing tasks:
- Keep to the structure
- Maintain consistent style
- Document unexpected findings
- Update this README with progress

## Next Steps

1. Start with `00-SETUP-FOUNDATION.md`
2. Complete each subtask in order
3. Verify after each step
4. Commit when complete
5. Move to next task file

Good luck! 🚀
