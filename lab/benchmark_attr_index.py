#!/usr/bin/env python3
"""Benchmark: Attributes.index() memory usage

Current: Full text string as index
Alternatives:
1. Hash of text (int)
2. Packed bytes representation
3. Tuple of attribute codes + values
"""

import sys


def measure_size(obj, name: str) -> int:
    size = sys.getsizeof(obj)
    print(f"  {name}: {size} bytes")
    return size


def run_benchmark():
    print("Benchmark: Attributes.index() memory usage\n")
    print("=" * 60)

    # Simulate typical attribute index string
    # Example: " origin igp as-path [ 65000 65001 65002 ] next-hop 192.168.1.1"
    typical_index = " origin igp as-path [ 65000 65001 65002 ] med 100 local-preference 100 next-hop 192.168.1.1"

    print("\nTypical attribute index:")
    print(f"  Content: {typical_index[:50]}...")
    print(f"  Length: {len(typical_index)} chars")
    print()

    print("Memory usage comparison:")
    str_size = measure_size(typical_index, "String (current)")
    hash_size = measure_size(hash(typical_index), "Hash (int)")
    bytes_size = measure_size(typical_index.encode(), "Bytes")

    # Tuple of components
    components = ('igp', (65000, 65001, 65002), 100, 100, '192.168.1.1')
    tuple_size = measure_size(components, "Tuple of values")

    print()
    print("Savings:")
    print(f"  Hash vs String: {str_size - hash_size} bytes ({(str_size - hash_size) / str_size * 100:.1f}%)")
    print(f"  Bytes vs String: {str_size - bytes_size} bytes ({(str_size - bytes_size) / str_size * 100:.1f}%)")
    print(f"  Tuple vs String: {str_size - tuple_size} bytes ({(str_size - tuple_size) / str_size * 100:.1f}%)")

    print("\n" + "=" * 60)
    print("\nWith 10,000 unique attribute sets:")

    # Simulate 10k unique attribute sets
    indices_str = [f" origin igp as-path [ {i} ] med {i % 100} next-hop 10.0.{i // 256}.{i % 256}" for i in range(10000)]
    indices_hash = [hash(s) for s in indices_str]

    str_total = sum(sys.getsizeof(s) for s in indices_str)
    hash_total = sum(sys.getsizeof(h) for h in indices_hash)

    print(f"  Total string memory: {str_total:,} bytes ({str_total / 1024 / 1024:.2f} MB)")
    print(f"  Total hash memory:   {hash_total:,} bytes ({hash_total / 1024 / 1024:.2f} MB)")
    print(f"  Savings: {(str_total - hash_total):,} bytes ({(str_total - hash_total) / str_total * 100:.1f}%)")

    print("\n" + "=" * 60)
    print("\nHowever, index() is used for:")
    print("  - Dict keys (hash is fine)")
    print("  - Equality comparison (need full value or reliable hash)")
    print("  - NOT for display/logging (that uses __repr__)")
    print()
    print("Recommendation: Keep string for correctness, or use tuple.")
    print("Hash alone risks collisions for equality checks.")


if __name__ == '__main__':
    run_benchmark()
