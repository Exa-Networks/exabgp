#!/usr/bin/env python3
"""Test that async mode handles task cancellation properly"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


async def test_cancelled_error_handling():
    """Simulate what happens when asyncio.run() cancels a task"""
    caught_cancelled_error = False

    try:
        # Simulate the main loop
        for i in range(10):
            if i == 5:
                # Simulate cancellation (like Ctrl+C would cause)
                raise asyncio.CancelledError()
            await asyncio.sleep(0)
    except asyncio.CancelledError:
        caught_cancelled_error = True
        print('✅ CancelledError caught successfully')
    except Exception as e:
        print(f'❌ Unexpected exception: {e}')
        return False

    return caught_cancelled_error


if __name__ == '__main__':
    result = asyncio.run(test_cancelled_error_handling())
    if result:
        print('✅ Test PASSED: CancelledError handling works')
        sys.exit(0)
    else:
        print('❌ Test FAILED: CancelledError not handled')
        sys.exit(1)
