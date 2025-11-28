#!/usr/bin/env python3
"""
Test Real-World ExaBGP RIB Updates Pattern

This test mimics the EXACT pattern used in ExaBGP:
- OutgoingRIB.updates() generator that clears state during iteration
- Peer loop calling new_update_async()
- API callbacks calling resend() to populate _refresh_changes
- Async scheduler executing callbacks

The goal is to find the exact failure mode that affects test T.
"""

import asyncio
import inspect
from collections import deque
from typing import Any, Deque, Iterator, Tuple

import pytest


class MockUpdate:
    """Simulates BGP Update message"""

    def __init__(self, nlri: str):
        self.nlri = nlri

    def messages(self, negotiated, include_withdraw):
        """Simulates update.messages() - yields encoded messages"""
        yield f'MSG({self.nlri})'

    def __repr__(self):
        return f'Update({self.nlri})'


class OutgoingRIB:
    """
    Mimics ExaBGP's OutgoingRIB class
    Implements the EXACT pattern from src/exabgp/rib/outgoing.py
    """

    def __init__(self):
        self._new_nlri = {}
        self._refresh_changes = []
        self._cache = {}

    def pending(self) -> bool:
        """Line 84-85 from outgoing.py"""
        return len(self._new_nlri) != 0 or len(self._refresh_changes) != 0

    def add_to_rib(self, nlri: str):
        """Simulates adding a route"""
        self._new_nlri[nlri] = MockUpdate(nlri)
        self._cache[nlri] = MockUpdate(nlri)

    def cached_changes(self) -> Iterator[MockUpdate]:
        """Returns all cached routes"""
        for update in self._cache.values():
            yield update

    def resend(self):
        """
        Line 87-101 from outgoing.py
        This is what flush adj-rib out calls
        """
        print(f'  [RIB.resend] Before: _refresh_changes has {len(self._refresh_changes)} items')
        for change in self.cached_changes():
            self._refresh_changes.append(change)
        print(f'  [RIB.resend] After: _refresh_changes has {len(self._refresh_changes)} items')

    def updates(self, grouped: bool) -> Iterator[MockUpdate]:
        """
        Lines 223-265 from outgoing.py
        CRITICAL: This clears state during iteration!
        """
        print(f'  [RIB.updates] Called with {len(self._new_nlri)} new + {len(self._refresh_changes)} refresh')

        # Lines 224-227: Save and clear new updates
        new_nlri = self._new_nlri
        self._new_nlri = {}

        # Lines 229-252: Yield new updates
        for update in new_nlri.values():
            yield update

        # Lines 259-261: Yield refresh updates and CLEAR
        print(f'  [RIB.updates] Yielding {len(self._refresh_changes)} refresh items')
        for change in self._refresh_changes:
            yield change
        self._refresh_changes = []  # LINE 261 - CLEARS DURING ITERATION


class MockProtocol:
    """Simulates Protocol class"""

    def __init__(self, rib: OutgoingRIB):
        self.rib = rib
        self.sent_messages = []

    async def send_async(self, message: str):
        """Simulates async send"""
        self.sent_messages.append(message)
        await asyncio.sleep(0.001)  # Simulate network I/O

    async def new_update_async(self, include_withdraw: bool) -> str:
        """
        Lines 680-690 from protocol.py
        Consumes updates() generator and sends messages
        """
        print('  [Protocol.new_update_async] Starting...')
        updates = self.rib.updates(False)
        number = 0
        for update in updates:
            for message in update.messages(None, include_withdraw):
                number += 1
                print(f'    [Protocol] Sending message {number}: {message}')
                await self.send_async(message)
        print(f'  [Protocol.new_update_async] Sent {number} messages')
        return 'UPDATE'


class ASYNC:
    """
    Mimics ExaBGP's ASYNC scheduler
    Lines 87-139 from asynchronous.py
    """

    LIMIT = 50

    def __init__(self):
        self._async: Deque[Tuple[str, Any]] = deque()

    def schedule(self, uid: str, command: str, callback: Any):
        """Schedule a callback"""
        print(f'  [ASYNC.schedule] Scheduling: {uid} - {command}')
        self._async.append((uid, callback))

    async def _run_async(self) -> bool:
        """Execute scheduled callbacks"""
        if not self._async:
            return False

        length = range(self.LIMIT)
        uid, callback = self._async.popleft()

        print(f'  [ASYNC._run_async] Executing callback: {uid}')

        for _ in length:
            try:
                if inspect.isgenerator(callback):
                    next(callback)
                elif inspect.iscoroutine(callback):
                    await callback
                    break  # Coroutine completes
                elif inspect.iscoroutinefunction(callback):
                    await callback()
                    break
                else:
                    next(callback)
            except StopIteration:
                if not self._async:
                    return False
                uid, callback = self._async.popleft()

        # BUG LOCATION: Line 123 puts callback back
        # For coroutines, this is wrong!
        if inspect.isgenerator(callback):
            self._async.appendleft((uid, callback))

        return True


@pytest.mark.asyncio
async def test_exabgp_pattern_single_flush():
    """
    Test Case 1: Single flush command
    Simulates test T's first flush at line 31 of api-rib.msg
    """
    print('\n' + '=' * 70)
    print('TEST 1: Single flush command (mimics test T)')
    print('=' * 70)

    rib = OutgoingRIB()
    protocol = MockProtocol(rib)
    scheduler = ASYNC()

    # 1. Add routes via API (lines 30 of api-rib.run)
    print('\n[STEP 1] API adds routes 192.168.0.2 and 192.168.0.3')
    rib.add_to_rib('192.168.0.2/32')
    rib.add_to_rib('192.168.0.3/32')

    # 2. Peer loop sends them
    print('\n[STEP 2] Peer loop detects pending() and sends')
    assert rib.pending(), 'Should have pending routes'
    await protocol.new_update_async(True)
    print(f'[STEP 2] Sent messages: {protocol.sent_messages}')
    protocol.sent_messages.clear()

    # 3. API sends flush command (line 31 of api-rib.msg)
    print("\n[STEP 3] API sends 'flush adj-rib out'")

    async def flush_callback():
        """Mimics flush_adj_rib_out callback from rib.py line 150-157"""
        print('  [flush_callback] Executing...')
        rib.resend()
        print('  [flush_callback] Done')

    scheduler.schedule('flush-cmd', 'flush adj-rib out', flush_callback())

    # 4. Reactor processes callback
    print('\n[STEP 4] Reactor executes scheduled callback')
    await scheduler._run_async()

    # 5. Peer loop should now see pending routes
    print('\n[STEP 5] Peer loop checks pending() after callback')
    pending = rib.pending()
    print(f'[STEP 5] pending() = {pending}')
    print(f'[STEP 5] _refresh_changes = {len(rib._refresh_changes)} items')

    if pending:
        print('\n[STEP 6] Peer loop sends refresh updates')
        await protocol.new_update_async(True)
        print(f'[STEP 6] Sent messages: {protocol.sent_messages}')

        expected = ['MSG(192.168.0.2/32)', 'MSG(192.168.0.3/32)']
        if set(protocol.sent_messages) == set(expected):
            print('\n✅ TEST PASSED - Flush sent expected routes')
        else:
            print(f'\n❌ TEST FAILED - Expected {expected}, got {protocol.sent_messages}')
    else:
        print('\n❌ TEST FAILED - pending() returned False after flush!')


@pytest.mark.asyncio
async def test_exabgp_pattern_multiple_flush():
    """
    Test Case 2: Multiple flush commands in sequence
    This is the EXACT pattern from test T (api-rib.run)
    """
    print('\n' + '=' * 70)
    print('TEST 2: Multiple flush commands (EXACT test T pattern)')
    print('=' * 70)

    rib = OutgoingRIB()
    protocol = MockProtocol(rib)
    scheduler = ASYNC()
    results = []

    # Sequence from api-rib.run:
    # Line 77: announce 192.168.0.0
    # Line 78: clear adj-rib out
    # Line 84: announce 192.168.0.1
    # Line 89: clear adj-rib out
    # Lines 95-96: announce 192.168.0.2 and 192.168.0.3
    # Line 101: flush adj-rib out  ← First flush
    # Line 107: announce 192.168.0.4
    # Line 112: flush adj-rib out  ← Second flush

    print('\n[SETUP] Adding routes 0.2, 0.3, 0.4 to cache')
    rib.add_to_rib('192.168.0.2/32')
    rib.add_to_rib('192.168.0.3/32')
    rib.add_to_rib('192.168.0.4/32')

    # Send initial routes
    print('\n[INITIAL] Sending initial routes')
    await protocol.new_update_async(True)
    results.append(('initial', list(protocol.sent_messages)))
    protocol.sent_messages.clear()

    # First flush - should resend 0.2, 0.3, 0.4
    print('\n[FLUSH-1] First flush command')

    async def flush1():
        rib.resend()

    scheduler.schedule('flush-1', 'flush adj-rib out', flush1())
    await scheduler._run_async()

    if rib.pending():
        await protocol.new_update_async(True)
        results.append(('flush-1', list(protocol.sent_messages)))
        protocol.sent_messages.clear()
    else:
        results.append(('flush-1', []))

    # Second flush - should resend 0.2, 0.3, 0.4 again
    print('\n[FLUSH-2] Second flush command')

    async def flush2():
        rib.resend()

    scheduler.schedule('flush-2', 'flush adj-rib out', flush2())
    await scheduler._run_async()

    if rib.pending():
        await protocol.new_update_async(True)
        results.append(('flush-2', list(protocol.sent_messages)))
        protocol.sent_messages.clear()
    else:
        results.append(('flush-2', []))

    print('\n[RESULTS] Messages sent:')
    for step, messages in results:
        print(f'  {step:12s}: {messages}')

    # Verify
    flush1_msgs = results[1][1]
    flush2_msgs = results[2][1]

    expected = 3  # Should resend 3 routes each time
    if len(flush1_msgs) == expected and len(flush2_msgs) == expected:
        print(f'\n✅ TEST PASSED - Both flushes sent {expected} routes')
    else:
        print(f'\n❌ TEST FAILED - flush-1: {len(flush1_msgs)}, flush-2: {len(flush2_msgs)}, expected: {expected}')


@pytest.mark.asyncio
async def test_concurrent_flush_and_peer():
    """
    Test Case 3: Concurrent execution (most realistic)
    Peer task and API callbacks run concurrently
    """
    print('\n' + '=' * 70)
    print('TEST 3: Concurrent peer task + API callbacks')
    print('=' * 70)

    rib = OutgoingRIB()
    protocol = MockProtocol(rib)
    scheduler = ASYNC()

    # Setup
    rib.add_to_rib('192.168.0.2/32')
    rib.add_to_rib('192.168.0.3/32')

    async def peer_task():
        """Simulates peer main loop"""
        print('[PEER] Starting')
        for i in range(5):
            await asyncio.sleep(0.01)
            if rib.pending():
                print(f'[PEER] Iteration {i}: pending=True, sending...')
                await protocol.new_update_async(True)
                print(f'[PEER] Sent: {protocol.sent_messages[-2:]}')
            else:
                print(f'[PEER] Iteration {i}: pending=False')
        print('[PEER] Finished')

    async def reactor_task():
        """Simulates reactor processing API commands"""
        print('[REACTOR] Starting')

        # Initial send
        await asyncio.sleep(0.005)

        # Flush command 1
        await asyncio.sleep(0.015)
        print('[REACTOR] Processing flush-1')

        async def flush1():
            rib.resend()

        scheduler.schedule('flush-1', 'flush', flush1())
        await scheduler._run_async()

        # Flush command 2
        await asyncio.sleep(0.020)
        print('[REACTOR] Processing flush-2')

        async def flush2():
            rib.resend()

        scheduler.schedule('flush-2', 'flush', flush2())
        await scheduler._run_async()

        print('[REACTOR] Finished')

    # Run concurrently
    await asyncio.gather(peer_task(), reactor_task())

    total_sent = len(protocol.sent_messages)
    print(f'\n[RESULT] Total messages sent: {total_sent}')
    print(f'[RESULT] Messages: {protocol.sent_messages}')

    # Should have sent: initial (2) + flush-1 (2) + flush-2 (2) = 6
    if total_sent >= 6:
        print('✅ TEST PASSED - Sent at least 6 messages')
    else:
        print(f'❌ TEST FAILED - Expected ≥6 messages, got {total_sent}')


async def main():
    """Run all ExaBGP-specific tests"""
    print('\n' + '#' * 70)
    print('# EXABGP RIB UPDATES PATTERN TESTS')
    print('#' * 70)

    await test_exabgp_pattern_single_flush()
    await test_exabgp_pattern_multiple_flush()
    await test_concurrent_flush_and_peer()

    print('\n' + '#' * 70)
    print('# ALL EXABGP TESTS COMPLETE')
    print('#' * 70)


if __name__ == '__main__':
    asyncio.run(main())
