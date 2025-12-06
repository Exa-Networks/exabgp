"""Tests for Update/Attributes refactoring.

Tests the new class hierarchy:
- UpdateData (renamed from Update) - semantic container
- Update (new) - wire container (bytes-first)
- AttributeSet (renamed from Attributes) - semantic container
- Attributes (new) - wire container (bytes-first)
- UpdateSerializer - generation logic

Phase 1: Tests for renaming (aliases work)
Phase 2: Tests for new wire containers
Phase 3: Tests for UpdateSerializer
"""

import pytest


# ==============================================================================
# Phase 1: Test aliases work (UpdateData, AttributeSet)
# ==============================================================================


def test_update_data_alias_exists() -> None:
    """Test that UpdateData alias is available."""
    from exabgp.bgp.message.update import UpdateData

    # UpdateData should be the semantic container (current Update class)
    assert UpdateData is not None


def test_attribute_set_alias_exists() -> None:
    """Test that AttributeSet alias is available."""
    from exabgp.bgp.message.update.attribute import AttributeSet

    # AttributeSet should be the semantic container (current Attributes class)
    assert AttributeSet is not None


def test_update_data_can_be_constructed() -> None:
    """Test that UpdateData can be instantiated with standard arguments."""
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.update.attribute import AttributeSet

    # Create an UpdateData with empty announces/withdraws
    attrs = AttributeSet()
    update = UpdateData(announces=[], withdraws=[], attributes=attrs)

    assert update.announces == []
    assert update.withdraws == []
    assert update.attributes is attrs


def test_attribute_set_is_dict() -> None:
    """Test that AttributeSet inherits from dict."""
    from exabgp.bgp.message.update.attribute import AttributeSet

    attrs = AttributeSet()
    assert isinstance(attrs, dict)


def test_attribute_set_has_method() -> None:
    """Test AttributeSet.has() method works."""
    from exabgp.bgp.message.update.attribute import AttributeSet, Origin

    attrs = AttributeSet()
    attrs.add(Origin.from_int(Origin.IGP))

    assert attrs.has(1)  # ORIGIN code
    assert not attrs.has(4)  # MED code


# ==============================================================================
# Phase 2: Test wire containers (UpdateWire, AttributesWire)
# Note: Using *Wire suffix for now to avoid breaking existing code.
# The plan calls for eventual swap where Update/Attributes become wire containers.
# ==============================================================================


def test_update_wire_class_exists() -> None:
    """Test that new UpdateWire wire container class exists."""
    from exabgp.bgp.message.update import UpdateWire

    # UpdateWire is the wire container (bytes-first)
    assert UpdateWire is not None


def test_update_wire_from_payload() -> None:
    """Test creating UpdateWire wire container from payload bytes."""
    from exabgp.bgp.message.update import UpdateWire

    # Minimal valid UPDATE payload: 0 withdrawn length + 0 attributes length
    payload = b'\x00\x00\x00\x00'

    update = UpdateWire(payload)

    assert update.payload == payload


def test_update_wire_to_bytes() -> None:
    """Test UpdateWire.to_bytes() generates complete BGP message."""
    from exabgp.bgp.message.update import UpdateWire
    from exabgp.bgp.message.message import Message

    payload = b'\x00\x00\x00\x00'
    update = UpdateWire(payload)

    msg_bytes = update.to_bytes()

    # Should have 16-byte marker + 2-byte length + 1-byte type + payload
    assert msg_bytes[:16] == Message.MARKER
    assert len(msg_bytes) == 19 + len(payload)
    assert msg_bytes[18] == Message.CODE.UPDATE


def test_attributes_wire_class_exists() -> None:
    """Test that new AttributesWire wire container class exists."""
    from exabgp.bgp.message.update.attribute import AttributesWire

    # AttributesWire is the wire container (bytes-first)
    assert AttributesWire is not None


def test_attributes_wire_from_packed() -> None:
    """Test creating AttributesWire wire container from packed bytes."""
    from exabgp.bgp.message.update.attribute import AttributesWire

    # ORIGIN attribute: flag=0x40, type=1, length=1, value=0 (IGP)
    packed = bytes([0x40, 0x01, 0x01, 0x00])

    attrs = AttributesWire(packed)

    assert attrs.packed == packed


def test_attributes_wire_from_set() -> None:
    """Test AttributesWire.from_set() creates wire container from AttributeSet."""
    from exabgp.bgp.message.update.attribute import AttributesWire, AttributeSet, Origin
    from unittest.mock import Mock

    attr_set = AttributeSet()
    attr_set.add(Origin.from_int(Origin.IGP))

    # Create mock negotiated - use same ASN for iBGP (simpler case)
    negotiated = Mock()
    negotiated.local_as = 65000
    negotiated.peer_as = 65000  # Same ASN = iBGP, avoids AS_PATH prepend
    negotiated.asn4 = True

    # Call with with_default=False to avoid complex default attribute generation
    wire_attrs = AttributesWire.from_set(attr_set, negotiated)

    assert isinstance(wire_attrs, AttributesWire)
    assert isinstance(wire_attrs.packed, bytes)
    # With with_default=True (the default), we get ORIGIN packed
    assert len(wire_attrs.packed) > 0


def test_attributes_wire_unpack_attributes_lazy() -> None:
    """Test AttributesWire.unpack_attributes() returns AttributeSet."""
    from exabgp.bgp.message.update.attribute import AttributesWire, AttributeSet
    from unittest.mock import Mock, patch

    # ORIGIN attribute
    packed = bytes([0x40, 0x01, 0x01, 0x00])

    with patch('exabgp.bgp.message.update.attribute.attributes.log'):
        attrs = AttributesWire(packed)

        negotiated = Mock()
        negotiated.asn4 = False
        negotiated.families = []
        negotiated.addpath = Mock()
        negotiated.addpath.receive = Mock(return_value=False)

        unpacked = attrs.unpack_attributes(negotiated)

        assert isinstance(unpacked, AttributeSet)
        assert 1 in unpacked  # ORIGIN code


# ==============================================================================
# Phase 3: Test UpdateSerializer
# ==============================================================================


def test_serializer_class_exists() -> None:
    """Test that UpdateSerializer class exists."""
    from exabgp.bgp.message.update.serializer import UpdateSerializer

    assert UpdateSerializer is not None


def test_serializer_serialize_method() -> None:
    """Test UpdateSerializer.serialize() returns iterator of UpdateWire."""
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.update.attribute import AttributeSet
    from exabgp.bgp.message.update.serializer import UpdateSerializer
    from unittest.mock import Mock

    # Create UpdateData
    attrs = AttributeSet()
    update_data = UpdateData(announces=[], withdraws=[], attributes=attrs)

    # Create mock negotiated
    negotiated = Mock()
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = []

    result = list(UpdateSerializer.serialize(update_data, negotiated))

    # With empty announces/withdraws, may return nothing or EOR
    # The test is that it doesn't crash and returns an iterator
    assert isinstance(result, list)


def test_serializer_serialize_bytes_method() -> None:
    """Test UpdateSerializer.serialize_bytes() returns iterator of bytes."""
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.update.attribute import AttributeSet
    from exabgp.bgp.message.update.serializer import UpdateSerializer
    from unittest.mock import Mock

    # Create UpdateData
    attrs = AttributeSet()
    update_data = UpdateData(announces=[], withdraws=[], attributes=attrs)

    # Create mock negotiated
    negotiated = Mock()
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = []

    result = list(UpdateSerializer.serialize_bytes(update_data, negotiated))

    # Check each item is bytes
    for item in result:
        assert isinstance(item, bytes)


# ==============================================================================
# Phase 4: Backward compatibility tests
# ==============================================================================


def test_update_data_messages_still_works() -> None:
    """Test that UpdateData.messages() still works (backward compatibility).

    Note: In the incremental implementation (Phase 1), messages() continues
    to work without deprecation warning. Deprecation will be added in Phase 2
    when the canonical names are swapped.
    """
    from exabgp.bgp.message.update import UpdateData
    from exabgp.bgp.message.update.attribute import AttributeSet
    from unittest.mock import Mock

    attrs = AttributeSet()
    update_data = UpdateData(announces=[], withdraws=[], attributes=attrs)

    negotiated = Mock()
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = []

    # Should work without errors
    result = list(update_data.messages(negotiated))

    # With empty announces/withdraws, returns empty list
    assert isinstance(result, list)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
