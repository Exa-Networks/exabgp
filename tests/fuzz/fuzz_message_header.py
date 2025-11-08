"""Fuzzing tests for BGP message header parsing."""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
import struct

# Mark all tests in this module as fuzz tests
pytestmark = pytest.mark.fuzz


@given(data=st.binary(min_size=0, max_size=100))
@settings(suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_header_parsing_with_random_data(data):
    """Fuzz header parser with completely random binary data.

    The parser should handle any binary data gracefully without crashing.
    It should either parse successfully or raise expected exceptions.
    """
    from exabgp.reactor.network.connection import Connection
    from exabgp.reactor.network.error import NotifyError, NotConnected, LostConnection, NetworkError

    # TODO: Determine how to properly invoke reader()
    # This is a placeholder - adjust based on actual API
    try:
        # reader is a generator, need to understand how to test it
        # For now, this is a skeleton that will be improved in Task 1.3-1.4

        # We'll need to mock the connection properly
        # Placeholder: just ensure imports work for now
        pass
    except (NotifyError, NotConnected, LostConnection, NetworkError, ValueError, KeyError, IndexError, struct.error, StopIteration):
        # Expected exceptions for malformed data
        pass
    except Exception as e:
        pytest.fail(f"Unexpected exception: {type(e).__name__}: {e}")


if __name__ == "__main__":
    # Run with: python -m pytest tests/fuzz/fuzz_message_header.py -v
    pytest.main([__file__, "-v", "-m", "fuzz"])
