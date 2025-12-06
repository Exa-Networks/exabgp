"""Tests for Update/Attributes refactoring.

Tests the new class hierarchy:
- UpdateCollection (renamed from Update) - semantic container
- Update (new) - wire container (bytes-first)
- AttributeCollection (renamed from Attributes) - semantic container
- Attributes (new) - wire container (bytes-first)
- UpdateSerializer - generation logic

Phase 1: Tests for renaming (aliases work)
Phase 2: Tests for new wire containers
Phase 3: Tests for UpdateSerializer
"""

import pytest


# ==============================================================================
# Phase 1: Test aliases work (UpdateCollection, AttributeCollection)
# ==============================================================================


def test_update_data_alias_exists() -> None:
    """Test that UpdateCollection alias is available."""
    from exabgp.bgp.message.update import UpdateCollection

    # UpdateCollection should be the semantic container (current Update class)
    assert UpdateCollection is not None


def test_attribute_set_alias_exists() -> None:
    """Test that AttributeCollection alias is available."""
    from exabgp.bgp.message.update.attribute import AttributeCollection

    # AttributeCollection should be the semantic container (current Attributes class)
    assert AttributeCollection is not None


def test_update_data_can_be_constructed() -> None:
    """Test that UpdateCollection can be instantiated with standard arguments."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.update.attribute import AttributeCollection

    # Create an UpdateCollection with empty announces/withdraws
    attrs = AttributeCollection()
    update = UpdateCollection(announces=[], withdraws=[], attributes=attrs)

    assert update.announces == []
    assert update.withdraws == []
    assert update.attributes is attrs


def test_attribute_set_is_dict() -> None:
    """Test that AttributeCollection inherits from dict."""
    from exabgp.bgp.message.update.attribute import AttributeCollection

    attrs = AttributeCollection()
    assert isinstance(attrs, dict)


def test_attribute_set_has_method() -> None:
    """Test AttributeCollection.has() method works."""
    from exabgp.bgp.message.update.attribute import AttributeCollection, Origin

    attrs = AttributeCollection()
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
    """Test AttributesWire.from_set() creates wire container from AttributeCollection."""
    from exabgp.bgp.message.update.attribute import AttributesWire, AttributeCollection, Origin
    from unittest.mock import Mock

    attr_set = AttributeCollection()
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
    """Test AttributesWire.unpack_attributes() returns AttributeCollection."""
    from exabgp.bgp.message.update.attribute import AttributesWire, AttributeCollection
    from unittest.mock import Mock, patch

    # ORIGIN attribute
    packed = bytes([0x40, 0x01, 0x01, 0x00])

    with patch('exabgp.bgp.message.update.attribute.collection.log'):
        attrs = AttributesWire(packed)

        negotiated = Mock()
        negotiated.asn4 = False
        negotiated.families = []
        negotiated.addpath = Mock()
        negotiated.addpath.receive = Mock(return_value=False)

        unpacked = attrs.unpack_attributes(negotiated)

        assert isinstance(unpacked, AttributeCollection)
        assert 1 in unpacked  # ORIGIN code


# ==============================================================================
# Phase 3: Test UpdateCollection.pack_messages()
# ==============================================================================


def test_pack_messages_method_exists() -> None:
    """Test that UpdateCollection.pack_messages() method exists."""
    from exabgp.bgp.message.update import UpdateCollection

    assert hasattr(UpdateCollection, 'pack_messages')


def test_pack_messages_returns_update_objects() -> None:
    """Test UpdateCollection.pack_messages() returns iterator of Update."""
    from exabgp.bgp.message.update import UpdateCollection, Update
    from exabgp.bgp.message.update.attribute import AttributeCollection
    from unittest.mock import Mock

    # Create UpdateCollection
    attrs = AttributeCollection()
    update_data = UpdateCollection(announces=[], withdraws=[], attributes=attrs)

    # Create mock negotiated
    negotiated = Mock()
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = []

    result = list(update_data.pack_messages(negotiated))

    # With empty announces/withdraws, may return nothing or EOR
    # The test is that it doesn't crash and returns an iterator
    assert isinstance(result, list)
    for item in result:
        assert isinstance(item, Update)


def test_messages_returns_bytes() -> None:
    """Test UpdateCollection.messages() returns iterator of bytes."""
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.update.attribute import AttributeCollection
    from unittest.mock import Mock

    # Create UpdateCollection
    attrs = AttributeCollection()
    update_data = UpdateCollection(announces=[], withdraws=[], attributes=attrs)

    # Create mock negotiated
    negotiated = Mock()
    negotiated.local_as = 65000
    negotiated.peer_as = 65001
    negotiated.asn4 = True
    negotiated.msg_size = 4096
    negotiated.families = []

    result = list(update_data.messages(negotiated))

    # Check each item is bytes
    for item in result:
        assert isinstance(item, bytes)


# ==============================================================================
# Phase 4: Backward compatibility tests
# ==============================================================================


def test_update_data_messages_still_works() -> None:
    """Test that UpdateCollection.messages() still works (backward compatibility).

    Note: In the incremental implementation (Phase 1), messages() continues
    to work without deprecation warning. Deprecation will be added in Phase 2
    when the canonical names are swapped.
    """
    from exabgp.bgp.message.update import UpdateCollection
    from exabgp.bgp.message.update.attribute import AttributeCollection
    from unittest.mock import Mock

    attrs = AttributeCollection()
    update_data = UpdateCollection(announces=[], withdraws=[], attributes=attrs)

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
