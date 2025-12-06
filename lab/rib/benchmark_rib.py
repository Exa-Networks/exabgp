#!/usr/bin/env python3
"""Comprehensive RIB benchmark suite.

Measures:
1. Memory usage (tracemalloc)
2. CPU time (cProfile)
3. Operation throughput (timeit)

Operations benchmarked:
- add_to_rib (single and bulk)
- del_from_rib (withdrawal)
- in_cache (deduplication check)
- updates() iteration
- cached_routes() iteration

Run with: python lab/benchmark_rib.py
"""

import cProfile
import gc
import pstats
import sys
import timeit
import tracemalloc
from copy import copy, deepcopy
from dataclasses import dataclass
from typing import Callable

# Add src to path
sys.path.insert(0, 'src')

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import AttributeCollection, LocalPreference, Origin
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib.route import Route
from exabgp.rib.outgoing import OutgoingRIB


@dataclass
class BenchmarkResult:
    """Results from a single benchmark."""

    name: str
    route_count: int
    time_seconds: float
    memory_bytes: int
    ops_per_second: float

    def __str__(self) -> str:
        mem_mb = self.memory_bytes / (1024 * 1024)
        return (
            f'{self.name}:\n'
            f'  Routes: {self.route_count:,}\n'
            f'  Time: {self.time_seconds:.4f}s\n'
            f'  Memory: {mem_mb:.2f} MB\n'
            f'  Throughput: {self.ops_per_second:,.0f} ops/sec'
        )


def create_route(prefix_num: int, attr_variation: int = 0) -> Route:
    """Create a realistic Route object.

    Args:
        prefix_num: Used to generate unique IP prefix
        attr_variation: Varies attributes (0-9 gives 10 unique attr sets)
    """
    # Generate IP: 10.x.y.z from prefix_num
    b1 = (prefix_num >> 16) & 0xFF
    b2 = (prefix_num >> 8) & 0xFF
    b3 = prefix_num & 0xFF
    ip_bytes = bytes([10, b1, b2, b3])

    # Create NLRI using factory method
    nlri = INET.make_route(
        afi=AFI.ipv4,
        safi=SAFI.unicast,
        packed=ip_bytes,
        mask=24,
        action=Action.ANNOUNCE,
    )

    # Create AttributeCollection with some variation
    attrs = AttributeCollection()
    attrs.add(Origin.from_int(Origin.IGP))
    attrs.add(LocalPreference.from_int(100 + attr_variation))

    return Route(nlri, attrs)


def measure_memory(func: Callable[[], None]) -> int:
    """Measure peak memory usage of a function."""
    gc.collect()
    tracemalloc.start()

    func()

    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    gc.collect()

    return peak


def benchmark_add_to_rib(route_count: int) -> BenchmarkResult:
    """Benchmark adding routes to RIB."""
    families = {(AFI.ipv4, SAFI.unicast)}

    # Pre-create routes to exclude creation time
    routes = [create_route(i, i % 10) for i in range(route_count)]

    def run():
        rib = OutgoingRIB(cache=True, families=families)
        for route in routes:
            rib.add_to_rib(route, force=True)

    # Measure time
    time_taken = timeit.timeit(run, number=1)

    # Measure memory
    def run_for_memory():
        rib = OutgoingRIB(cache=True, families=families)
        for route in routes:
            rib.add_to_rib(route, force=True)
        # Keep rib alive for measurement
        return rib

    gc.collect()
    tracemalloc.start()
    _rib = run_for_memory()
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return BenchmarkResult(
        name='add_to_rib',
        route_count=route_count,
        time_seconds=time_taken,
        memory_bytes=peak,
        ops_per_second=route_count / time_taken,
    )


def benchmark_del_from_rib(route_count: int) -> BenchmarkResult:
    """Benchmark withdrawing routes (del_from_rib)."""
    families = {(AFI.ipv4, SAFI.unicast)}
    routes = [create_route(i, i % 10) for i in range(route_count)]

    # Pre-populate RIB
    rib = OutgoingRIB(cache=True, families=families)
    for route in routes:
        rib.add_to_rib(route, force=True)
    # Consume pending to move to cache
    list(rib.updates(grouped=True))

    # Now benchmark withdrawals
    def run():
        for route in routes:
            rib.del_from_rib(route)

    time_taken = timeit.timeit(run, number=1)
    memory = measure_memory(lambda: [deepcopy(r) for r in routes[:1000]])

    return BenchmarkResult(
        name='del_from_rib',
        route_count=route_count,
        time_seconds=time_taken,
        memory_bytes=memory * (route_count // 1000),
        ops_per_second=route_count / time_taken,
    )


def benchmark_in_cache(route_count: int) -> BenchmarkResult:
    """Benchmark cache checking (in_cache)."""
    families = {(AFI.ipv4, SAFI.unicast)}
    routes = [create_route(i, i % 10) for i in range(route_count)]

    # Pre-populate RIB cache
    rib = OutgoingRIB(cache=True, families=families)
    for route in routes:
        rib.add_to_rib(route, force=True)
    list(rib.updates(grouped=True))  # Move to cache

    # Benchmark cache hits
    def run_hits():
        for route in routes:
            rib.in_cache(route)

    time_hits = timeit.timeit(run_hits, number=1)

    # Benchmark cache misses (new routes)
    new_routes = [create_route(route_count + i, i % 10) for i in range(route_count)]

    def run_misses():
        for route in new_routes:
            rib.in_cache(route)

    time_misses = timeit.timeit(run_misses, number=1)

    return BenchmarkResult(
        name=f'in_cache (hits={time_hits:.3f}s, misses={time_misses:.3f}s)',
        route_count=route_count,
        time_seconds=time_hits + time_misses,
        memory_bytes=0,  # No additional memory
        ops_per_second=route_count * 2 / (time_hits + time_misses),
    )


def benchmark_updates_iteration(route_count: int) -> BenchmarkResult:
    """Benchmark UPDATE message generation."""
    families = {(AFI.ipv4, SAFI.unicast)}
    routes = [create_route(i, i % 10) for i in range(route_count)]

    rib = OutgoingRIB(cache=True, families=families)
    for route in routes:
        rib.add_to_rib(route, force=True)

    def run():
        updates = list(rib.updates(grouped=True))
        return len(updates)

    time_taken = timeit.timeit(run, number=1)

    return BenchmarkResult(
        name='updates() iteration',
        route_count=route_count,
        time_seconds=time_taken,
        memory_bytes=0,
        ops_per_second=route_count / time_taken,
    )


def benchmark_route_object_size() -> None:
    """Measure Route object memory footprint."""
    print('\n' + '=' * 60)
    print('Route Object Memory Analysis')
    print('=' * 60)

    route = create_route(1)

    # Measure single object
    gc.collect()
    tracemalloc.start()
    routes = [create_route(i) for i in range(1000)]
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f'\n1000 Route objects: {peak / 1024:.1f} KB')
    print(f'Per object: {peak / 1000:.1f} bytes')

    # Check if __slots__ is used
    has_slots = hasattr(Route, '__slots__')
    has_dict = hasattr(route, '__dict__')
    print('\nRoute class:')
    print(f'  Has __slots__: {has_slots}')
    print(f'  Has __dict__: {has_dict}')
    if has_dict:
        print(f'  __dict__ size: {sys.getsizeof(route.__dict__)} bytes')

    # Measure index computation
    print('\nIndex computation:')
    print(f'  route.index() = {route.index()!r}')
    print(f'  Length: {len(route.index())} bytes')
    print(f'  attributes.index() length: {len(route.attributes.index())} chars')


def benchmark_deepcopy_vs_shallow() -> None:
    """Compare deepcopy vs shallow copy for withdrawals."""
    print('\n' + '=' * 60)
    print('Deepcopy vs Shallow Copy Analysis')
    print('=' * 60)

    route = create_route(1)

    # Time deepcopy
    deep_time = timeit.timeit(lambda: deepcopy(route), number=10000)
    print(f'\nDeepcopy 10K times: {deep_time:.4f}s ({deep_time / 10000 * 1e6:.1f} µs/op)')

    # Time shallow copy
    def shallow_withdrawal(r: Route) -> Route:
        new_nlri = copy(r.nlri)
        new_nlri.action = Action.WITHDRAW
        return Route(new_nlri, r.attributes)

    shallow_time = timeit.timeit(lambda: shallow_withdrawal(route), number=10000)
    print(f'Shallow copy 10K times: {shallow_time:.4f}s ({shallow_time / 10000 * 1e6:.1f} µs/op)')

    speedup = deep_time / shallow_time
    print(f'Speedup: {speedup:.1f}x')

    # Memory comparison
    gc.collect()
    tracemalloc.start()
    _deep_copies = [deepcopy(route) for _ in range(1000)]
    deep_mem = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    gc.collect()
    tracemalloc.start()
    _shallow_copies = [shallow_withdrawal(route) for _ in range(1000)]
    shallow_mem = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()

    print('\nMemory for 1000 copies:')
    print(f'  Deepcopy: {deep_mem / 1024:.1f} KB')
    print(f'  Shallow: {shallow_mem / 1024:.1f} KB')
    print(f'  Savings: {(deep_mem - shallow_mem) / 1024:.1f} KB ({100 * (deep_mem - shallow_mem) / deep_mem:.0f}%)')


def profile_hot_paths(route_count: int = 10000) -> None:
    """Profile CPU usage to identify hot paths."""
    print('\n' + '=' * 60)
    print(f'CPU Profile (cProfile) - {route_count:,} routes')
    print('=' * 60)

    families = {(AFI.ipv4, SAFI.unicast)}
    routes = [create_route(i, i % 10) for i in range(route_count)]

    def workload():
        rib = OutgoingRIB(cache=True, families=families)

        # Add routes
        for route in routes:
            rib.add_to_rib(route, force=True)

        # Generate updates
        list(rib.updates(grouped=True))

        # Withdraw routes
        for route in routes:
            rib.del_from_rib(route)

        # Generate withdrawal updates
        list(rib.updates(grouped=True))

    profiler = cProfile.Profile()
    profiler.enable()
    workload()
    profiler.disable()

    # Print top 20 by cumulative time
    print('\nTop 20 functions by cumulative time:')
    stats = pstats.Stats(profiler, stream=sys.stdout)
    stats.sort_stats('cumulative')
    stats.print_stats(20)


def run_all_benchmarks() -> None:
    """Run complete benchmark suite."""
    print('=' * 60)
    print('ExaBGP RIB Benchmark Suite')
    print('=' * 60)

    route_counts = [1000, 10000, 100000]

    for count in route_counts:
        print(f'\n{"=" * 60}')
        print(f'Route count: {count:,}')
        print('=' * 60)

        results = [
            benchmark_add_to_rib(count),
            benchmark_del_from_rib(count),
            benchmark_in_cache(count),
            benchmark_updates_iteration(count),
        ]

        for result in results:
            print(f'\n{result}')

    # Detailed analysis
    benchmark_route_object_size()
    benchmark_deepcopy_vs_shallow()

    # CPU profiling (smaller dataset)
    profile_hot_paths(10000)


def quick_benchmark() -> None:
    """Quick benchmark for development iteration."""
    print('Quick RIB Benchmark (1000 routes)')
    print('=' * 40)

    results = [
        benchmark_add_to_rib(1000),
        benchmark_del_from_rib(1000),
    ]

    for result in results:
        print(f'\n{result}')

    benchmark_deepcopy_vs_shallow()


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='RIB Benchmark Suite')
    parser.add_argument('--quick', action='store_true', help='Run quick benchmark only')
    parser.add_argument('--profile', action='store_true', help='Run CPU profiling only')
    parser.add_argument('--routes', type=int, default=10000, help='Route count for profiling')
    args = parser.parse_args()

    if args.quick:
        quick_benchmark()
    elif args.profile:
        profile_hot_paths(args.routes)
    else:
        run_all_benchmarks()
