#!/usr/bin/env python3
"""
Test Generator Interleaving in Async Mode

This test verifies that multiple data generators can coexist and be consumed
correctly in async mode without blocking each other.

The issue we're testing: In sync mode, generators yield control naturally.
In async mode, we need to ensure generators don't block the event loop.
"""

import asyncio
from typing import Iterator, List


def data_generator_1() -> Iterator[str]:
    """Simulates RIB updates() generator - yields data objects"""
    for i in range(5):
        yield f'GEN1-{i}'


def data_generator_2() -> Iterator[str]:
    """Simulates another data source"""
    for i in range(5):
        yield f'GEN2-{i}'


async def consume_generator_sync_style(gen: Iterator[str], name: str, results: List[str]):
    """
    Sync mode style: consume generator in tight loop
    This is what new_update_async() does
    """
    print(f'[{name}] Starting consumption (sync style)')
    for item in gen:
        results.append(f'{name}: {item}')
        # No yield here - tight loop!
    print(f'[{name}] Finished consumption (sync style)')


async def consume_generator_async_style(gen: Iterator[str], name: str, results: List[str]):
    """
    Async mode style: consume generator but yield control periodically
    This is what we SHOULD do if generators can block
    """
    print(f'[{name}] Starting consumption (async style)')
    for item in gen:
        results.append(f'{name}: {item}')
        await asyncio.sleep(0)  # Yield control
    print(f'[{name}] Finished consumption (async style)')


async def test_sync_style_consumption():
    """Test if tight loop consumption blocks other tasks"""
    print('\n' + '=' * 60)
    print('TEST 1: Sync-style consumption (tight loop, no yields)')
    print('=' * 60)

    results = []
    gen1 = data_generator_1()
    gen2 = data_generator_2()

    # Start both consumers concurrently
    await asyncio.gather(
        consume_generator_sync_style(gen1, 'GEN1', results),
        consume_generator_sync_style(gen2, 'GEN2', results),
    )

    print(f'\nResults collected: {len(results)} items')
    for i, item in enumerate(results):
        print(f'  {i}: {item}')

    # Check if results are interleaved or sequential
    gen1_items = [r for r in results if 'GEN1' in r]
    gen2_items = [r for r in results if 'GEN2' in r]

    print(f'\nGEN1 items: {len(gen1_items)}')
    print(f'GEN2 items: {len(gen2_items)}')

    # In sync style, we expect sequential execution (one completes before other starts)
    # or interleaving at Python level (depends on asyncio scheduling)
    print(f'\nFirst 5 items from GEN1: {results[:5]}')
    print(f'Last 5 items from GEN2: {results[-5:]}')


async def test_async_style_consumption():
    """Test if yielding allows interleaving"""
    print('\n' + '=' * 60)
    print('TEST 2: Async-style consumption (yields control)')
    print('=' * 60)

    results = []
    gen1 = data_generator_1()
    gen2 = data_generator_2()

    # Start both consumers concurrently
    await asyncio.gather(
        consume_generator_async_style(gen1, 'GEN1', results),
        consume_generator_async_style(gen2, 'GEN2', results),
    )

    print(f'\nResults collected: {len(results)} items')
    for i, item in enumerate(results):
        print(f'  {i}: {item}')

    gen1_items = [r for r in results if 'GEN1' in r]
    gen2_items = [r for r in results if 'GEN2' in r]

    print(f'\nGEN1 items: {len(gen1_items)}')
    print(f'GEN2 items: {len(gen2_items)}')

    # With yields, we expect interleaved execution
    print(f'\nInterleaving pattern: {results}')


async def test_state_modification_during_consumption():
    """
    Critical test: Does state modification during generator consumption work?

    This simulates what happens with flush adj-rib out:
    1. Callback modifies _refresh_changes
    2. updates() generator yields from _refresh_changes
    3. During iteration, _refresh_changes is cleared (line 261)
    """
    print('\n' + '=' * 60)
    print('TEST 3: State modification during generator consumption')
    print('=' * 60)

    class RIBSimulator:
        def __init__(self):
            self._data = []

        def add_data(self, items: List[str]):
            """Simulates resend() adding to _refresh_changes"""
            self._data.extend(items)
            print(f'[RIB] Added {len(items)} items, total now: {len(self._data)}')

        def updates(self) -> Iterator[str]:
            """Simulates updates() generator"""
            print(f'[RIB] updates() called, have {len(self._data)} items to yield')
            data_snapshot = list(self._data)
            self._data = []  # Clear during iteration (like line 261)
            print(f'[RIB] Cleared _data, yielding {len(data_snapshot)} items')
            for item in data_snapshot:
                yield item

    rib = RIBSimulator()

    # Initial population
    rib.add_data(['item1', 'item2', 'item3'])

    # Consume first batch
    results1 = []
    for item in rib.updates():
        results1.append(item)
    print(f'First consumption: {results1}')

    # Add more data (simulates second flush command)
    rib.add_data(['item4', 'item5'])

    # Consume second batch
    results2 = []
    for item in rib.updates():
        results2.append(item)
    print(f'Second consumption: {results2}')

    # This should work fine - testing if async changes behavior
    assert len(results1) == 3, f'Expected 3 items in first batch, got {len(results1)}'
    assert len(results2) == 2, f'Expected 2 items in second batch, got {len(results2)}'
    print('\n✅ State modification test PASSED')


async def test_concurrent_state_modification():
    """
    Most critical test: Concurrent state modification and consumption

    Simulates:
    - Peer task consuming updates()
    - API callback adding more data via resend()
    - Both happening concurrently
    """
    print('\n' + '=' * 60)
    print('TEST 4: Concurrent state modification and consumption')
    print('=' * 60)

    class AsyncRIBSimulator:
        def __init__(self):
            self._data = []
            self.consumption_count = 0

        def add_data(self, items: List[str]):
            """Simulates resend() - called from API callback"""
            self._data.extend(items)
            print(f'[RIB] API callback added {len(items)} items, total: {len(self._data)}')

        def pending(self) -> bool:
            """Simulates pending() check"""
            return len(self._data) > 0

        async def updates_async(self) -> Iterator[str]:
            """Async-aware updates generator"""
            print(f'[RIB] updates() called, have {len(self._data)} items')
            data_snapshot = list(self._data)
            self._data = []
            for item in data_snapshot:
                yield item
                await asyncio.sleep(0)  # Yield control during iteration

    rib = AsyncRIBSimulator()
    results = []

    async def peer_task():
        """Simulates peer loop checking pending() and consuming updates"""
        print('[PEER] Starting peer task')
        for iteration in range(5):
            await asyncio.sleep(0.01)  # Wait for API commands
            if rib.pending():
                print(f'[PEER] Iteration {iteration}: pending() = True, consuming...')
                async for item in rib.updates_async():
                    results.append(item)
                    print(f'[PEER] Got: {item}')
            else:
                print(f'[PEER] Iteration {iteration}: pending() = False, skipping')
        print('[PEER] Peer task finished')

    async def api_callback_task():
        """Simulates API callbacks adding data"""
        print('[API] Starting API callback task')
        await asyncio.sleep(0.005)
        rib.add_data(['batch1-item1', 'batch1-item2'])

        await asyncio.sleep(0.02)
        rib.add_data(['batch2-item1', 'batch2-item2', 'batch2-item3'])

        await asyncio.sleep(0.02)
        rib.add_data(['batch3-item1'])
        print('[API] API callback task finished')

    # Run both concurrently
    await asyncio.gather(
        peer_task(),
        api_callback_task(),
    )

    print(f'\n[RESULT] Total items collected: {len(results)}')
    print(f'[RESULT] Items: {results}')

    expected_count = 6  # 2 + 3 + 1
    if len(results) == expected_count:
        print(f'✅ Concurrent test PASSED - got all {expected_count} items')
    else:
        print(f'❌ Concurrent test FAILED - expected {expected_count}, got {len(results)}')
        print(f'   Missing items: {expected_count - len(results)}')


async def main():
    """Run all tests"""
    print('\n' + '#' * 60)
    print('# GENERATOR INTERLEAVING AND STATE SYNC TESTS')
    print('#' * 60)

    await test_sync_style_consumption()
    await test_async_style_consumption()
    await test_state_modification_during_consumption()
    await test_concurrent_state_modification()

    print('\n' + '#' * 60)
    print('# ALL TESTS COMPLETE')
    print('#' * 60)


if __name__ == '__main__':
    asyncio.run(main())
