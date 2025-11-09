from typing import Any, Generator
# encoding: utf-8
"""tests/unit/test_async_infrastructure.py

Tests for async/await infrastructure in ASYNC class
"""

import asyncio
import os
import pytest
from unittest.mock import Mock

# Set up environment before importing ExaBGP modules
os.environ['exabgp_log_enable'] = 'false'
os.environ['exabgp_log_level'] = 'CRITICAL'

from exabgp.reactor.asynchronous import ASYNC


@pytest.fixture(autouse=True)
def mock_logger() -> Any:
    """Mock the logger to avoid initialization issues."""
    from exabgp.logger.option import option

    # Save original values
    original_logger = option.logger
    original_formater = option.formater

    # Create a mock logger with all required methods
    mock_option_logger = Mock()
    mock_option_logger.debug = Mock()
    mock_option_logger.info = Mock()
    mock_option_logger.warning = Mock()
    mock_option_logger.error = Mock()
    mock_option_logger.critical = Mock()

    # Create a mock formater
    mock_option_formater = Mock(return_value='')

    # Set mocks
    option.logger = mock_option_logger
    option.formater = mock_option_formater

    yield

    # Restore original values
    option.logger = original_logger
    option.formater = original_formater


def test_async_supports_generators() -> None:
    """Test that ASYNC still works with generators (backward compatibility)"""
    async_handler = ASYNC()
    results = []

    def gen_callback() -> Generator[None, None, None]:
        results.append(1)
        yield
        results.append(2)
        yield

    async_handler.schedule('test', 'test-gen', gen_callback())

    # Run synchronously - run() handles the event loop internally
    async_handler.run()

    assert 1 in results


@pytest.mark.asyncio
async def test_async_supports_coroutines() -> None:
    """Test that ASYNC works with new coroutines"""
    async_handler = ASYNC()
    results = []

    async def coro_callback():
        results.append(1)
        await asyncio.sleep(0)
        results.append(2)

    async_handler.schedule('test', 'test-coro', coro_callback())
    await async_handler._run_async()

    assert 1 in results
    assert 2 in results


@pytest.mark.asyncio
async def test_async_mixed_workload() -> None:
    """Test that ASYNC handles both generators and coroutines"""
    async_handler = ASYNC()
    results = []

    def gen_callback() -> Generator[None, None, None]:
        results.append('gen')
        yield

    async def coro_callback():
        results.append('coro')
        await asyncio.sleep(0)

    async_handler.schedule('test1', 'test-gen', gen_callback())
    async_handler.schedule('test2', 'test-coro', coro_callback())

    await async_handler._run_async()

    assert 'gen' in results
    assert 'coro' in results


@pytest.mark.asyncio
async def test_async_multiple_yields() -> None:
    """Test that ASYNC handles generators with multiple yields"""
    async_handler = ASYNC()
    results = []

    def gen_with_yields() -> Generator[None, None, None]:
        for i in range(3):
            results.append(i)
            yield

    async_handler.schedule('test', 'test-multi-yield', gen_with_yields())

    # Run multiple times to process all yields
    for _ in range(5):
        if not await async_handler._run_async():
            break

    assert results == [0, 1, 2]


@pytest.mark.asyncio
async def test_async_coroutine_exception_handling() -> None:
    """Test that ASYNC handles exceptions in coroutines"""
    async_handler = ASYNC()
    results = []

    async def failing_coro():
        results.append('start')
        raise ValueError('Test exception')

    async def success_coro():
        results.append('success')

    async_handler.schedule('test1', 'test-fail', failing_coro())
    async_handler.schedule('test2', 'test-success', success_coro())

    # Should handle exception and continue
    await async_handler._run_async()

    assert 'start' in results
    assert 'success' in results


@pytest.mark.asyncio
async def test_async_generator_exception_handling() -> None:
    """Test that ASYNC handles exceptions in generators (backward compatibility)"""
    async_handler = ASYNC()
    results = []

    def failing_gen() -> Generator[None, None, None]:
        results.append('gen_start')
        raise ValueError('Test exception')
        yield

    def success_gen() -> Generator[None, None, None]:
        results.append('gen_success')
        yield

    async_handler.schedule('test1', 'test-fail', failing_gen())
    async_handler.schedule('test2', 'test-success', success_gen())

    # Should handle exception and continue
    await async_handler._run_async()

    assert 'gen_start' in results
    assert 'gen_success' in results


def test_async_ready() -> None:
    """Test that ready() returns correct status"""
    async_handler = ASYNC()

    # Should be ready when empty
    assert async_handler.ready()

    def gen() -> Generator[None, None, None]:
        yield

    async_handler.schedule('test', 'test-cmd', gen())

    # Should not be ready when tasks are scheduled
    assert not async_handler.ready()


def test_async_clear() -> None:
    """Test that clear() removes scheduled tasks"""
    async_handler = ASYNC()

    def gen1() -> Generator[None, None, None]:
        yield

    def gen2() -> Generator[None, None, None]:
        yield

    async_handler.schedule('uid1', 'cmd1', gen1())
    async_handler.schedule('uid2', 'cmd2', gen2())

    # Clear specific uid
    async_handler.clear('uid1')
    assert not async_handler.ready()  # uid2 still there

    # Clear all
    async_handler.clear()
    assert async_handler.ready()


def test_async_sync_run_with_coroutines() -> None:
    """Test that synchronous run() works with coroutines"""
    async_handler = ASYNC()
    results = []

    async def coro_callback():
        results.append('coro')

    async_handler.schedule('test', 'test-coro', coro_callback())

    # Call run() synchronously
    async_handler.run()

    assert 'coro' in results


@pytest.mark.asyncio
async def test_async_is_coroutine_helper() -> None:
    """Test the _is_coroutine helper method"""
    async_handler = ASYNC()

    async def coro():
        pass

    def gen() -> Generator[None, None, None]:
        yield

    # Test with coroutine
    coro_instance = coro()
    assert async_handler._is_coroutine(coro_instance)
    await coro_instance  # Clean up

    # Test with coroutine function
    assert async_handler._is_coroutine(coro)

    # Test with generator
    gen_instance = gen()
    assert not async_handler._is_coroutine(gen_instance)
