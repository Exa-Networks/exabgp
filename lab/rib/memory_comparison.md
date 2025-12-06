# ExaBGP Memory Comparison

**Date:** 2025-12-06

## Test Configuration
- Python 3.12
- 100,000 IPv4 unicast routes (10.x.y.z/24)
- Each route has Origin IGP + LocalPreference 100 attributes

## Baselines

| # | Name | Commit | Description |
|---|------|--------|-------------|
| 1 | 5.0 Branch | 59f730a8 | Stable release branch |
| 1.5 | Pre-Deepcopy | ac803ba3 | main before deepcopy removal |
| 2 | main Branch | b1b384d1 | Current main with all optimizations |

## Results Comparison

### Per-Object Memory

| Metric | 1. 5.0 Branch | 1.5 Pre-Deepcopy | 2. main Branch |
|--------|---------------|------------------|----------------|
| Object class | Change | Change | Route |
| Per-object size | 1,154 bytes | 1,034 bytes | 1,034 bytes |
| `__slots__` | No | No | No |
| `__dict__` size | 296 bytes | 296 bytes | 296 bytes |

### RIB Operations Memory (100K routes)

| Stage | 1. 5.0 Branch | 1.5 Pre-Deepcopy | 2. main Branch |
|-------|---------------|------------------|----------------|
| Empty RIB | 0.00 MB | 0.00 MB | 0.00 MB |
| After add_to_rib | 13.41 MB | 13.70 MB | 13.73 MB |
| After cache | 13.41 MB | 13.70 MB | 13.73 MB |
| **After del_from_rib** | **44.91 MB** | **38.86 MB** | **13.73 MB** |
| After withdraw updates | 44.91 MB | 38.86 MB | 13.80 MB |

### Total Memory

| Metric | 1. 5.0 Branch | 1.5 Pre-Deepcopy | 2. main Branch |
|--------|---------------|------------------|----------------|
| Objects (100K) | 110.06 MB | 98.61 MB | 98.61 MB |
| RIB overhead | 13.41 MB | 13.70 MB | 13.73 MB |
| **Total** | **123.47 MB** | **112.31 MB** | **112.34 MB** |

## Improvement Summary

### 5.0 → main (total improvement)

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Per-object size | 1,154 bytes | 1,034 bytes | **-10%** |
| del_from_rib memory | 44.91 MB | 13.73 MB | **-69%** |
| Total (100K) | 123.47 MB | 112.34 MB | **-9%** |

### Pre-Deepcopy → main (deepcopy removal only)

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| Per-object size | 1,034 bytes | 1,034 bytes | same |
| del_from_rib memory | 38.86 MB | 13.73 MB | **-65%** |
| Total (100K) | 112.31 MB | 112.34 MB | same |

## Key Findings

1. **Route object size reduced by 10%** (1,154 → 1,034 bytes)
   - Class-level AFI/SAFI saves ~120 bytes per object
   - This happened between 5.0 and pre-deepcopy commits

2. **del_from_rib memory reduced by 65-69%**
   - 5.0: 44.91 MB (deepcopy + old object model)
   - Pre-deepcopy: 38.86 MB (deepcopy + new object model)
   - main: 13.73 MB (no deepcopy)
   - Now stores `(NLRI, Attributes)` tuples in `_pending_withdraws`

3. **Total memory unchanged by deepcopy removal**
   - The deepcopy memory was temporary (during withdrawal processing)
   - Permanent memory footprint is the same

## Future Optimization: __slots__

Adding `__slots__` to Route and NLRI classes would provide:
- Expected savings: ~104 bytes/route
- Projected total for 100K: **88.69 MB** (21% reduction from main)
- Total reduction from 5.0: **28%**

## Files

- `memory_baseline_1_5.0_branch.txt` - 5.0 branch baseline (59f730a8)
- `memory_baseline_1.5_pre_deepcopy.txt` - Pre-deepcopy baseline (ac803ba3)
- `memory_baseline_2_main_branch.txt` - main branch baseline (b1b384d1)
- `memory_baseline.py` - test script (run with `uv run python lab/rib/memory_baseline.py`)
