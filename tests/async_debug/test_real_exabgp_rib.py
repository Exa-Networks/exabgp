#!/usr/bin/env python3
"""
Test using REAL ExaBGP classes

This imports and tests the actual OutgoingRIB class to see if there's
something we're missing in our mock implementation.
"""

import sys
import os

# Add src to path so we can import exabgp
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

from exabgp.rib.outgoing import OutgoingRIB
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.action import Action
from exabgp.rib.change import Change
from exabgp.protocol.ip import IPv4


def test_real_rib_resend():
    """
    Test the ACTUAL OutgoingRIB.resend() method
    to ensure our understanding is correct
    """
    print('\n' + '=' * 70)
    print('TEST: Real ExaBGP OutgoingRIB.resend()')
    print('=' * 70)

    # Create RIB with caching enabled
    families = {(AFI.ipv4, SAFI.unicast)}
    rib = OutgoingRIB(cache=True, families=families)

    print('\n[STEP 1] Check initial state')
    print(f'  pending() = {rib.pending()}')
    print(f'  _refresh_changes = {len(rib._refresh_changes)}')

    # Create a change (route)
    print('\n[STEP 2] Create and cache a route')
    nlri = INET(afi=AFI.ipv4, safi=SAFI.unicast, action=Action.ANNOUNCE)
    nlri.cidr = CIDR.make_cidr(IPv4.pton('192.168.0.1'), 32)
    attrs = Attributes()
    change = Change(nlri, attrs)

    # Add to cache (simulates what happens when route is announced)
    rib.update_cache(change)
    cached = list(rib.cached_changes(list(families)))
    print(f'  Cached routes: {len(cached)}')

    # Call resend() - this is what flush adj-rib out does
    print('\n[STEP 3] Call resend() - simulates flush command')
    rib.resend(enhanced_refresh=False, family=None)

    print('  After resend():')
    print(f'    pending() = {rib.pending()}')
    print(f'    _refresh_changes = {len(rib._refresh_changes)}')

    # Consume via updates()
    print('\n[STEP 4] Consume via updates() generator')
    update_count = 0
    for update in rib.updates(grouped=False):
        update_count += 1
        print(f'    Update #{update_count}: {update}')

    print(f'  Total updates yielded: {update_count}')

    print('\n[STEP 5] Check state after consumption')
    print(f'  pending() = {rib.pending()}')
    print(f'  _refresh_changes = {len(rib._refresh_changes)}')

    # Try second resend
    print('\n[STEP 6] Second resend() - should work again')
    rib.resend(enhanced_refresh=False, family=None)
    print('  After second resend():')
    print(f'    pending() = {rib.pending()}')
    print(f'    _refresh_changes = {len(rib._refresh_changes)}')

    update_count2 = 0
    for update in rib.updates(grouped=False):
        update_count2 += 1

    print(f'  Second consumption: {update_count2} updates')

    if update_count > 0 and update_count2 > 0:
        print('\n✅ TEST PASSED - resend() works multiple times')
    else:
        print(f'\n❌ TEST FAILED - First: {update_count}, Second: {update_count2}')


def test_real_rib_concurrent_operations():
    """
    Test multiple operations on real RIB
    """
    print('\n' + '=' * 70)
    print('TEST: Concurrent add + resend operations')
    print('=' * 70)

    families = {(AFI.ipv4, SAFI.unicast)}
    rib = OutgoingRIB(cache=True, families=families)

    # Add multiple routes
    print('\n[SETUP] Adding 3 routes to cache')
    for i in range(3):
        nlri = INET(afi=AFI.ipv4, safi=SAFI.unicast, action=Action.ANNOUNCE)
        nlri.cidr = CIDR.make_cidr(IPv4.pton(f'192.168.0.{i}'), 32)
        attrs = Attributes()
        change = Change(nlri, attrs)
        rib.update_cache(change)
        rib.add_to_rib(change)  # Also add to pending

    # Send initial
    print('\n[STEP 1] Send initial routes')
    count1 = sum(1 for _ in rib.updates(grouped=False))
    print(f'  Sent {count1} initial routes')

    # Flush
    print('\n[STEP 2] Flush (resend cached)')
    rib.resend(enhanced_refresh=False, family=None)
    count2 = sum(1 for _ in rib.updates(grouped=False))
    print(f'  Sent {count2} flushed routes')

    # Add new route while cache exists
    print('\n[STEP 3] Add new route + flush again')
    nlri = INET(afi=AFI.ipv4, safi=SAFI.unicast, action=Action.ANNOUNCE)
    nlri.cidr = CIDR.make_cidr(IPv4.pton('192.168.0.100'), 32)
    attrs = Attributes()
    change = Change(nlri, attrs)
    rib.update_cache(change)
    rib.add_to_rib(change)

    rib.resend(enhanced_refresh=False, family=None)
    count3 = sum(1 for _ in rib.updates(grouped=False))
    print(f'  Sent {count3} routes (should be 4 new + 4 refresh = more)')

    print('\n[RESULTS]')
    print(f'  Initial send: {count1} routes')
    print(f'  First flush:  {count2} routes')
    print(f'  Second flush: {count3} routes')

    if count1 >= 3 and count2 >= 3:
        print('\n✅ TEST PASSED - Flush resends cached routes')
    else:
        print(f'\n❌ TEST FAILED - Expected ≥3 routes in flush, got {count2}')


def main():
    """Run all real ExaBGP tests"""
    print('\n' + '#' * 70)
    print('# REAL EXABGP RIB CLASS TESTS')
    print('#' * 70)

    try:
        test_real_rib_resend()
        test_real_rib_concurrent_operations()

        print('\n' + '#' * 70)
        print('# ALL REAL EXABGP TESTS COMPLETE')
        print('#' * 70)

    except Exception as e:
        print(f'\n❌ TEST ERROR: {e}')
        import traceback

        traceback.print_exc()


if __name__ == '__main__':
    main()
