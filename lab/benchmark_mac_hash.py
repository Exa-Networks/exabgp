#!/usr/bin/env python3
"""Benchmark: MAC.__hash__ using str(self) vs packed bytes

Current: hash(str(self)) - formats to string, then hashes
Proposed: hash(self._packed) - hashes bytes directly
"""

import timeit


class MACCurrent:
    """Current implementation."""

    def __init__(self, packed: bytes) -> None:
        self._packed = packed

    def __str__(self) -> str:
        return ':'.join('{:02X}'.format(_) for _ in self._packed)

    def __hash__(self) -> int:
        return hash(str(self))


class MACProposed:
    """Proposed implementation - hash packed bytes directly."""

    def __init__(self, packed: bytes) -> None:
        self._packed = packed

    def __hash__(self) -> int:
        return hash(self._packed)


def run_benchmark():
    print("Benchmark: MAC.__hash__ performance\n")
    print("=" * 60)

    # Create test MACs
    mac_bytes = b'\x00\x11\x22\x33\x44\x55'

    mac_current = MACCurrent(mac_bytes)
    mac_proposed = MACProposed(mac_bytes)

    # Verify hashes are stable (not necessarily equal)
    h1 = hash(mac_current)
    h2 = hash(mac_current)
    assert h1 == h2, "Hash not stable for current"

    h3 = hash(mac_proposed)
    h4 = hash(mac_proposed)
    assert h3 == h4, "Hash not stable for proposed"

    print(f"Current hash:  {h1}")
    print(f"Proposed hash: {h3}")
    print()

    for n_hashes in [100, 1000, 10000, 100000]:
        print(f"\nHash operations: {n_hashes}")

        current_time = timeit.timeit(
            'hash(mac)',
            globals={'mac': mac_current},
            number=n_hashes
        )
        proposed_time = timeit.timeit(
            'hash(mac)',
            globals={'mac': mac_proposed},
            number=n_hashes
        )

        speedup = current_time / proposed_time
        print(f"  Current (str):   {current_time:.6f}s")
        print(f"  Proposed (bytes): {proposed_time:.6f}s")
        print(f"  Speedup:          {speedup:.2f}x")

    # Test in dict/set context (real use case)
    print("\n" + "=" * 60)
    print("\nDict insertion benchmark (10000 unique MACs):")

    current_macs = [MACCurrent(bytes([i // 256, i % 256, 0, 0, 0, 0])) for i in range(10000)]
    proposed_macs = [MACProposed(bytes([i // 256, i % 256, 0, 0, 0, 0])) for i in range(10000)]

    current_time = timeit.timeit(
        'd = {m: True for m in macs}',
        globals={'macs': current_macs},
        number=10
    )
    proposed_time = timeit.timeit(
        'd = {m: True for m in macs}',
        globals={'macs': proposed_macs},
        number=10
    )

    speedup = current_time / proposed_time
    print(f"  Current:  {current_time:.4f}s (10 iterations)")
    print(f"  Proposed: {proposed_time:.4f}s (10 iterations)")
    print(f"  Speedup:  {speedup:.2f}x")


if __name__ == '__main__':
    run_benchmark()
