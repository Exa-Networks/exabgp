#!/usr/bin/env python3
"""Benchmark: MPRNLRI nexthop caching potential

Question: Is slicing bytes expensive enough to warrant caching?
And: How often do we see the same nexthop?

In practice, nexthops tend to be:
- Same peer IP for many routes from same neighbor
- A few unique nexthops per session
"""

import timeit


def without_cache(data: bytes, offset: int, size: int, iterations: int) -> list:
    """Current approach: slice every time."""
    results = []
    for _ in range(iterations):
        nhs = data[offset : offset + size]
        results.append(nhs)
    return results


def with_cache(data: bytes, offset: int, size: int, iterations: int) -> list:
    """Proposed: cache by key."""
    cache = {}
    results = []
    for _ in range(iterations):
        key = (id(data), offset, size)  # Or use data[offset:offset+size] as key
        if key not in cache:
            cache[key] = data[offset : offset + size]
        results.append(cache[key])
    return results


def run_benchmark():
    print("Benchmark: MPRNLRI nexthop caching\n")
    print("=" * 60)

    # Typical MPRNLRI data with 16-byte IPv6 nexthop
    data = b'\x00' * 100 + b'\x20\x01\x0d\xb8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01' + b'\x00' * 100
    offset = 100
    size = 16

    print("Scenario: Same nexthop repeated (cache hit)")
    for iterations in [10, 100, 1000]:
        print(f"\n  Iterations: {iterations}")

        t_no_cache = timeit.timeit(
            lambda: without_cache(data, offset, size, iterations),
            number=1000
        )
        t_cache = timeit.timeit(
            lambda: with_cache(data, offset, size, iterations),
            number=1000
        )

        print(f"    Without cache: {t_no_cache:.4f}s")
        print(f"    With cache:    {t_cache:.4f}s")
        print(f"    Speedup:       {t_no_cache / t_cache:.2f}x" if t_cache > 0 else "")

    print("\n" + "=" * 60)
    print("\nRaw slice operation timing:")

    # Just measure the slice operation itself
    t_slice = timeit.timeit(
        'data[100:116]',
        globals={'data': data},
        number=1000000
    )
    print(f"  1M slices: {t_slice:.4f}s")
    print(f"  Per slice: {t_slice / 1000000 * 1e9:.1f}ns")

    print("\n" + "=" * 60)
    print("\nConclusion:")
    print("  - Byte slicing is extremely fast (~50-100ns)")
    print("  - Cache overhead (dict lookup) may exceed slice cost")
    print("  - Only beneficial if same nexthop used 100s of times")
    print("  - Recommendation: Skip unless profiling shows bottleneck")


if __name__ == '__main__':
    run_benchmark()
