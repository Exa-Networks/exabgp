"""Integration tests for UPDATE message unpack_message() method.

These tests verify the complete UPDATE parsing pipeline from raw bytes
through split() to full message unpacking. Uses minimal mocking to test
real integration between components.

Target: src/exabgp/bgp/message/update/__init__.py::unpack_message()

Test Coverage:
- Simple UPDATE with withdrawals
- Simple UPDATE with announcements
- UPDATE with mandatory path attributes
- Integration between split() and attribute parsing
- Integration between split() and NLRI parsing
"""

from typing import Any, Generator
from unittest.mock import Mock, patch

import pytest

pytestmark = pytest.mark.fuzz


@pytest.fixture(autouse=True)
def mock_logger() -> Generator[None, None, None]:
    """Mock the logger to avoid initialization issues."""
    with (
        patch('exabgp.bgp.message.update.log') as mock_log,
        patch('exabgp.bgp.message.update.log') as mock_log,
        patch('exabgp.bgp.message.update.nlri.nlri.log') as mock_nlri_log,
        patch('exabgp.bgp.message.update.attribute.collection.log') as mock_attr_log,
    ):
        mock_log.debug = Mock()
        mock_log.debug = Mock()
        mock_nlri_log.debug = Mock()
        mock_attr_log.debug = Mock()
        yield


def create_negotiated_mock() -> Any:
    """Create a minimal mock negotiated object."""
    from exabgp.bgp.message.direction import Direction

    negotiated = Mock()
    negotiated.direction = Direction.IN
    negotiated.addpath.receive = Mock(return_value=False)
    negotiated.addpath.send = Mock(return_value=False)
    negotiated.required = Mock(return_value=False)
    negotiated.families = []
    return negotiated


@pytest.mark.fuzz
def test_unpack_simple_withdrawal() -> None:
    """Test unpacking UPDATE with only withdrawals."""
    from exabgp.bgp.message.update import UpdateCollection
    from tests.fuzz.update_helpers import create_withdrawal_update

    negotiated = create_negotiated_mock()

    # Create UPDATE withdrawing 192.0.2.0/24
    data = create_withdrawal_update([('192.0.2.0', 24)])

    result = UpdateCollection.unpack_message(data, negotiated)

    # Should return Update object with withdrawals
    assert isinstance(result, UpdateCollection)
    # Action is determined by list placement: withdraws list contains withdrawal NLRIs
    assert len(result.withdraws) >= 1


@pytest.mark.fuzz
def test_unpack_empty_update_is_eor() -> None:
    """Test that empty UPDATE is detected as EOR."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.update.eor import EOR

    negotiated = create_negotiated_mock()

    # Empty UPDATE (EOR marker)
    data = b'\x00\x00\x00\x00'

    result = UpdateCollection.unpack_message(data, negotiated)

    assert isinstance(result, EOR)


@pytest.mark.fuzz
def test_unpack_with_minimal_attributes() -> None:
    """Test UPDATE with minimal valid attributes (ORIGIN only)."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.update.attribute import AttributeCollection
    from tests.fuzz.update_helpers import create_update_message, create_origin_attribute

    negotiated = create_negotiated_mock()

    # Create UPDATE with ORIGIN attribute only (simplest valid attribute)
    origin_attr = create_origin_attribute(0)  # IGP

    data = create_update_message(
        withdrawn_routes=b'',
        path_attributes=origin_attr,
        nlri=b'',
    )

    result = UpdateCollection.unpack_message(data, negotiated)

    # Should return Update object
    assert isinstance(result, UpdateCollection)
    # Should have attributes
    assert isinstance(result.attributes, AttributeCollection)


@pytest.mark.fuzz
def test_split_integration_with_unpack() -> None:
    """Test that split() output integrates correctly with unpack_message()."""
    from exabgp.bgp.message.update import UpdateCollection
    from tests.fuzz.update_helpers import create_update_message, create_ipv4_prefix

    negotiated = create_negotiated_mock()

    # Create a simple UPDATE with withdrawals
    withdrawn = create_ipv4_prefix('10.0.0.0', 8)

    data = create_update_message(
        withdrawn_routes=withdrawn,
        path_attributes=b'',
        nlri=b'',
    )

    # First verify split() works
    w, a, n = UpdateCollection.split(data)
    assert len(w) == len(withdrawn)
    assert len(a) == 0
    assert len(n) == 0

    # Now verify unpack_message() can process it
    result = UpdateCollection.unpack_message(data, negotiated)

    assert isinstance(result, UpdateCollection)
    assert len(result.nlris) >= 1


@pytest.mark.fuzz
def test_unpack_with_multiple_withdrawals() -> None:
    """Test UPDATE with multiple withdrawn routes."""
    from exabgp.bgp.message.update import UpdateCollection
    from tests.fuzz.update_helpers import create_withdrawal_update

    negotiated = create_negotiated_mock()

    # Multiple withdrawals
    prefixes = [
        ('192.0.2.0', 24),
        ('10.0.0.0', 8),
        ('172.16.0.0', 12),
    ]

    data = create_withdrawal_update(prefixes)

    result = UpdateCollection.unpack_message(data, negotiated)

    assert isinstance(result, UpdateCollection)
    # Should have multiple NLRI entries
    assert len(result.nlris) == len(prefixes)


@pytest.mark.fuzz
def test_unpack_handles_split_validation() -> None:
    """Test that unpack_message() properly handles split() validation errors."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.notification import Notify

    negotiated = create_negotiated_mock()

    # Invalid UPDATE: length field mismatch
    data = b'\x00\x05\x00\x00'  # Claims 5 bytes of withdrawals but has none

    with pytest.raises(Notify) as exc_info:
        UpdateCollection.unpack_message(data, negotiated)

    # Should raise Notify from split()
    assert exc_info.value.code == 3
    assert exc_info.value.subcode == 1


@pytest.mark.fuzz
def test_unpack_preserves_data_integrity() -> None:
    """Test that data flows correctly through split() to unpack_message()."""
    from exabgp.bgp.message.update import UpdateCollection
    from tests.fuzz.update_helpers import create_ipv4_prefix, create_update_message

    negotiated = create_negotiated_mock()

    # Create UPDATE with known data
    test_prefix = create_ipv4_prefix('203.0.113.0', 24)

    data = create_update_message(
        withdrawn_routes=test_prefix,
        path_attributes=b'',
        nlri=b'',
    )

    # Verify split extracts the data correctly
    withdrawn, attrs, announced = UpdateCollection.split(data)
    assert withdrawn == test_prefix

    # Verify unpack_message processes the same data
    result = UpdateCollection.unpack_message(data, negotiated)

    assert isinstance(result, UpdateCollection)
    # The withdrawn prefix should be in the result
    assert len(result.nlris) >= 1


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'fuzz'])
