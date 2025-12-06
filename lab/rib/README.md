# ExaBGP RIB Benchmark Suite

Performance and memory benchmarks for the RIB (Routing Information Base).

## Running Benchmarks

```bash
# Full RIB benchmark suite (1K, 10K, 100K routes)
uv run python lab/rib/benchmark_rib.py

# Quick benchmark (1K routes only)
uv run python lab/rib/benchmark_rib.py --quick

# CPU profiling only
uv run python lab/rib/benchmark_rib.py --profile --routes 10000
```

## Benchmarks

### benchmark_rib.py

Comprehensive RIB (Routing Information Base) benchmark measuring:

- `add_to_rib()` throughput and memory
- `del_from_rib()` throughput (includes deepcopy overhead)
- `in_cache()` lookup performance (hits and misses)
- `updates()` iteration performance
- Change object memory footprint
- Deepcopy vs shallow copy comparison

## Baseline Results (2025-12-05)

### Performance (100K routes)

| Operation | Time | Throughput | Memory |
|-----------|------|------------|--------|
| `add_to_rib` | 0.30s | 331K ops/sec | 0.23 MB |
| `del_from_rib` | 1.50s | 67K ops/sec | 155 MB |
| `in_cache` (hits) | 0.05s | 1.26M ops/sec | - |
| `updates()` | 0.0002s | 614M ops/sec | - |

### Memory

```
Change object: 1,035 bytes (no __slots__)
  - __dict__ overhead: 96 bytes

Withdrawal (deepcopy vs shallow):
  - Deepcopy: 12.6 µs, 1575 KB per 1000
  - Shallow:  0.4 µs,  298 KB per 1000
  - Speedup: 28.7x
  - Memory savings: 81%
```

### CPU Profile (10K routes)

```
Top bottleneck: deepcopy() in del_from_rib()
  - 88% of withdrawal time spent in deepcopy
  - deepcopy calls: _reconstruct(), _deepcopy_dict()
```

## Adding New Benchmarks

Create new benchmark files following the pattern in `benchmark_rib.py`:

1. Use `timeit` for timing
2. Use `tracemalloc` for memory measurement
3. Use `cProfile` for CPU profiling
4. Support `--quick` flag for fast iteration
