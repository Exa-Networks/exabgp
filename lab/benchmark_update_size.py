#!/usr/bin/env python3
"""Benchmark: Progressive size calculation vs current approach in Update.messages()

Current: len(announced + withdraws + packed) - creates new bytes object each time
Proposed: Track size as int, only concatenate when yielding

This measures the overhead of the length calculation approach.
"""

import timeit


def current_approach(n_nlris: int, nlri_size: int = 23) -> int:
    """Simulates current approach: concatenate to check length."""
    msg_size = 4000
    announced = b''
    withdraws = b''
    yields = 0

    for _ in range(n_nlris):
        packed = b'x' * nlri_size
        if len(announced + withdraws + packed) <= msg_size:
            announced += packed
        else:
            yields += 1
            announced = packed
            withdraws = b''

    return yields


def progressive_approach(n_nlris: int, nlri_size: int = 23) -> int:
    """Simulates proposed approach: track size as int."""
    msg_size = 4000
    announced = b''
    withdraws = b''
    announced_size = 0
    withdraws_size = 0
    yields = 0

    for _ in range(n_nlris):
        packed = b'x' * nlri_size
        packed_size = len(packed)
        if announced_size + withdraws_size + packed_size <= msg_size:
            announced += packed
            announced_size += packed_size
        else:
            yields += 1
            announced = packed
            announced_size = packed_size
            withdraws = b''
            withdraws_size = 0

    return yields


def run_benchmark():
    print("Benchmark: Update.messages() size calculation\n")
    print("=" * 60)

    for n_nlris in [10, 100, 1000, 10000]:
        print(f"\nNLRIs: {n_nlris}")

        # Verify both produce same result
        current_result = current_approach(n_nlris)
        progressive_result = progressive_approach(n_nlris)
        assert current_result == progressive_result, f"Results differ: {current_result} vs {progressive_result}"

        # Time both approaches
        current_time = timeit.timeit(
            f'current_approach({n_nlris})',
            globals={'current_approach': current_approach},
            number=100
        )
        progressive_time = timeit.timeit(
            f'progressive_approach({n_nlris})',
            globals={'progressive_approach': progressive_approach},
            number=100
        )

        speedup = current_time / progressive_time
        print(f"  Current:     {current_time:.4f}s (100 iterations)")
        print(f"  Progressive: {progressive_time:.4f}s (100 iterations)")
        print(f"  Speedup:     {speedup:.2f}x")


if __name__ == '__main__':
    run_benchmark()
