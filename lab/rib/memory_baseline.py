#!/usr/bin/env python3
"""Memory baseline measurement for RIB operations.

Measures actual memory usage (not deepcopy overhead) for:
- Route object creation
- RIB add/cache operations
- RIB withdrawal operations

Run with: uv run python lab/rib/memory_baseline.py
"""

import gc
import sys
import tracemalloc

sys.path.insert(0, 'src')

from exabgp.bgp.message import Action
from exabgp.bgp.message.update.attribute import AttributeCollection, LocalPreference, Origin
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.protocol.family import AFI, SAFI
from exabgp.rib.outgoing import OutgoingRIB
from exabgp.rib.route import Route


def create_route(i: int) -> Route:
    """Create a route with unique prefix 10.x.y.z/24."""
    b1, b2, b3 = (i >> 16) & 0xFF, (i >> 8) & 0xFF, i & 0xFF
    nlri = INET.make_route(AFI.ipv4, SAFI.unicast, bytes([10, b1, b2, b3]), 24, Action.ANNOUNCE)
    attrs = AttributeCollection()
    attrs.add(Origin.from_int(Origin.IGP))
    attrs.add(LocalPreference.from_int(100))
    return Route(nlri, attrs)


def measure_route_objects(n: int) -> tuple[float, float]:
    """Measure memory for N Route objects."""
    gc.collect()
    tracemalloc.start()
    routes = [create_route(i) for i in range(n)]
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return peak / 1024 / 1024, peak / n


def measure_rib_operations(n: int) -> dict:
    """Measure memory at each RIB operation stage."""
    routes = [create_route(i) for i in range(n)]

    gc.collect()
    tracemalloc.start()

    # Stage 1: Create RIB
    rib = OutgoingRIB(cache=True, families={(AFI.ipv4, SAFI.unicast)})
    mem_rib_empty = tracemalloc.get_traced_memory()[1]

    # Stage 2: Add routes
    for r in routes:
        rib.add_to_rib(r, force=True)
    mem_after_add = tracemalloc.get_traced_memory()[1]

    # Stage 3: Generate updates (moves to cache)
    list(rib.updates(grouped=True))
    mem_after_cache = tracemalloc.get_traced_memory()[1]

    # Stage 4: Withdraw all routes
    for r in routes:
        rib.del_from_rib(r)
    mem_after_del = tracemalloc.get_traced_memory()[1]

    # Stage 5: Generate withdrawal updates
    list(rib.updates(grouped=True))
    mem_after_withdraw_updates = tracemalloc.get_traced_memory()[1]

    tracemalloc.stop()

    return {
        'rib_empty': mem_rib_empty,
        'after_add': mem_after_add,
        'after_cache': mem_after_cache,
        'after_del': mem_after_del,
        'after_withdraw_updates': mem_after_withdraw_updates,
    }


def check_slots() -> dict:
    """Check __slots__ usage on key classes."""
    route = create_route(0)
    return {
        'Route': {
            'has_slots': hasattr(Route, '__slots__'),
            'has_dict': hasattr(route, '__dict__'),
            'dict_size': sys.getsizeof(route.__dict__) if hasattr(route, '__dict__') else 0,
        },
        'INET': {
            'has_slots': hasattr(INET, '__slots__'),
            'has_dict': hasattr(route.nlri, '__dict__'),
            'dict_size': sys.getsizeof(route.nlri.__dict__) if hasattr(route.nlri, '__dict__') else 0,
        },
        'AttributeCollection': {
            'has_slots': hasattr(AttributeCollection, '__slots__'),
            'has_dict': hasattr(route.attributes, '__dict__'),
            # AttributeCollection is a dict subclass, so check differently
        },
    }


def main():
    print('=' * 70)
    print('ExaBGP Memory Baseline Measurement')
    print('=' * 70)
    print()

    # Check slots
    print('Class Configuration:')
    print('-' * 70)
    slots_info = check_slots()
    for cls_name, info in slots_info.items():
        print(f'  {cls_name}:')
        print(f'    __slots__: {info["has_slots"]}')
        print(f'    __dict__:  {info["has_dict"]}')
        if 'dict_size' in info and info['dict_size']:
            print(f'    dict size: {info["dict_size"]} bytes')
    print()

    # Route object memory
    print('Route Object Memory:')
    print('-' * 70)
    for n in [1000, 10000]:
        mem_mb, mem_per = measure_route_objects(n)
        print(f'  {n:,} routes: {mem_mb:.2f} MB ({mem_per:.1f} bytes/route)')
    print()

    # RIB operations memory
    print('RIB Operations Memory (100,000 routes):')
    print('-' * 70)
    n = 100000
    mem = measure_rib_operations(n)
    print(f'  Empty RIB:              {mem["rib_empty"] / 1024 / 1024:8.2f} MB')
    print(f'  After add_to_rib:       {mem["after_add"] / 1024 / 1024:8.2f} MB  ({mem["after_add"] / n:.1f} bytes/route)')
    print(f'  After cache (updates):  {mem["after_cache"] / 1024 / 1024:8.2f} MB  ({mem["after_cache"] / n:.1f} bytes/route)')
    print(f'  After del_from_rib:     {mem["after_del"] / 1024 / 1024:8.2f} MB  ({mem["after_del"] / n:.1f} bytes/route)')
    print(f'  After withdraw updates: {mem["after_withdraw_updates"] / 1024 / 1024:8.2f} MB')
    print()

    # Summary
    print('Summary:')
    print('-' * 70)
    route_mem_mb, route_mem_per = measure_route_objects(100000)
    rib_overhead = mem["after_cache"] / n
    total_per_route = route_mem_per + rib_overhead
    print(f'  Route objects (100K):    {route_mem_mb:.2f} MB ({route_mem_per:.1f} bytes/route)')
    print(f'  RIB overhead (100K):     {mem["after_cache"] / 1024 / 1024:.2f} MB ({rib_overhead:.1f} bytes/route)')
    print(f'  Total per route:         {total_per_route:.1f} bytes')
    print(f'  Total for 100K routes:   {(route_mem_mb + mem["after_cache"] / 1024 / 1024):.2f} MB')
    print()

    # Projection with __slots__
    print('Projection with __slots__:')
    print('-' * 70)
    # __slots__ typically saves ~104 bytes per object (removes __dict__ overhead)
    slots_savings = 104  # bytes per object
    projected_per_route = route_mem_per - slots_savings
    projected_total = projected_per_route * 100000 / 1024 / 1024
    print(f'  Expected savings:        ~{slots_savings} bytes/route')
    print(f'  Projected per route:     {projected_per_route:.1f} bytes')
    print(f'  Projected for 100K:      {projected_total:.2f} MB')
    print(f'  Reduction:               {100 * slots_savings / route_mem_per:.0f}%')


if __name__ == '__main__':
    main()
