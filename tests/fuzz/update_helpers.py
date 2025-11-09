"""Helper functions for constructing BGP UPDATE messages for testing.

This module provides utilities to create well-formed and malformed UPDATE
messages for fuzzing and testing the UPDATE message parser.
"""
import struct


def create_update_message(withdrawn_routes=b'', path_attributes=b'', nlri=b''):
    """Create a BGP UPDATE message with given components.

    Args:
        withdrawn_routes: Raw bytes of withdrawn routes (without length prefix)
        path_attributes: Raw bytes of path attributes (without length prefix)
        nlri: Raw bytes of NLRI

    Returns:
        bytes: Complete UPDATE message body (without BGP header)
    """
    withdrawn_len = struct.pack('!H', len(withdrawn_routes))
    attr_len = struct.pack('!H', len(path_attributes))

    return withdrawn_len + withdrawn_routes + attr_len + path_attributes + nlri


def create_ipv4_prefix(ip, prefix_len):
    """Create wire-format IPv4 prefix for NLRI or withdrawn routes.

    Args:
        ip: IP address as string (e.g., "192.0.2.0")
        prefix_len: Prefix length in bits (0-32)

    Returns:
        bytes: Wire format (length byte + address bytes)

    Example:
        >>> create_ipv4_prefix("192.0.2.0", 24)
        b'\\x18\\xc0\\x00\\x02'  # length=24, 3 bytes of IP
    """
    if not (0 <= prefix_len <= 32):
        raise ValueError(f"Invalid prefix length: {prefix_len} (must be 0-32)")

    # Calculate how many bytes needed for the prefix
    bytes_needed = (prefix_len + 7) // 8

    # Convert IP to bytes
    parts = ip.split('.')
    if len(parts) != 4:
        raise ValueError(f"Invalid IPv4 address: {ip}")

    ip_bytes = bytes([int(p) for p in parts])

    # Return length + required bytes
    return bytes([prefix_len]) + ip_bytes[:bytes_needed]


def create_path_attribute(type_code, value, optional=False, transitive=True, partial=False, extended=False):
    """Create a BGP path attribute.

    Args:
        type_code: Attribute type code (1-255)
        value: Attribute value (bytes)
        optional: Optional flag (bit 7)
        transitive: Transitive flag (bit 6)
        partial: Partial flag (bit 5)
        extended: Extended length flag (bit 4) - True for length > 255

    Returns:
        bytes: Wire format attribute (flags + type + length + value)

    Attribute Format:
        Flags (1 byte):
            Bit 7: Optional (1) / Well-known (0)
            Bit 6: Transitive (1) / Non-transitive (0)
            Bit 5: Partial (1) / Complete (0)
            Bit 4: Extended Length (1) / Regular (0)
            Bits 3-0: Unused (must be 0)
        Type Code (1 byte)
        Length (1 or 2 bytes depending on Extended flag)
        Value (variable)
    """
    # Build flags byte
    flags = 0
    if optional:
        flags |= 0x80  # Bit 7
    if transitive:
        flags |= 0x40  # Bit 6
    if partial:
        flags |= 0x20  # Bit 5
    if extended or len(value) > 255:
        flags |= 0x10  # Bit 4
        length_bytes = struct.pack('!H', len(value))
    else:
        length_bytes = struct.pack('!B', len(value))

    return bytes([flags, type_code]) + length_bytes + value


def create_origin_attribute(origin_type):
    """Create ORIGIN path attribute (Type 1).

    Args:
        origin_type: 0 (IGP), 1 (EGP), or 2 (INCOMPLETE)

    Returns:
        bytes: ORIGIN attribute
    """
    if origin_type not in (0, 1, 2):
        raise ValueError(f"Invalid origin type: {origin_type}")

    return create_path_attribute(
        type_code=1,
        value=bytes([origin_type]),
        optional=False,
        transitive=True,
    )


def create_as_path_attribute(as_sequence):
    """Create AS_PATH path attribute (Type 2).

    Args:
        as_sequence: List of AS numbers (e.g., [65001, 65002])

    Returns:
        bytes: AS_PATH attribute

    Format:
        Segment Type (1 byte): 2 = AS_SEQUENCE
        Segment Length (1 byte): Number of ASes
        AS Numbers (2 or 4 bytes each depending on AS size)
    """
    # AS_SEQUENCE segment type
    segment_type = 2
    segment_length = len(as_sequence)

    # For simplicity, assume 2-byte AS numbers
    # (4-byte AS would need AS4_PATH attribute)
    value = bytes([segment_type, segment_length])
    for asn in as_sequence:
        if asn > 65535:
            raise ValueError(f"AS number {asn} requires 4-byte AS support")
        value += struct.pack('!H', asn)

    return create_path_attribute(
        type_code=2,
        value=value,
        optional=False,
        transitive=True,
    )


def create_next_hop_attribute(ip_address):
    """Create NEXT_HOP path attribute (Type 3).

    Args:
        ip_address: IPv4 address as string (e.g., "192.0.2.1")

    Returns:
        bytes: NEXT_HOP attribute
    """
    parts = ip_address.split('.')
    if len(parts) != 4:
        raise ValueError(f"Invalid IPv4 address: {ip_address}")

    ip_bytes = bytes([int(p) for p in parts])

    return create_path_attribute(
        type_code=3,
        value=ip_bytes,
        optional=False,
        transitive=True,
    )


def create_med_attribute(med_value):
    """Create MULTI_EXIT_DISC (MED) path attribute (Type 4).

    Args:
        med_value: MED value (0-4294967295)

    Returns:
        bytes: MED attribute
    """
    if not (0 <= med_value <= 0xFFFFFFFF):
        raise ValueError(f"Invalid MED value: {med_value}")

    return create_path_attribute(
        type_code=4,
        value=struct.pack('!I', med_value),
        optional=True,
        transitive=False,
    )


def create_local_pref_attribute(local_pref):
    """Create LOCAL_PREF path attribute (Type 5).

    Args:
        local_pref: Local preference value (0-4294967295)

    Returns:
        bytes: LOCAL_PREF attribute
    """
    if not (0 <= local_pref <= 0xFFFFFFFF):
        raise ValueError(f"Invalid LOCAL_PREF value: {local_pref}")

    return create_path_attribute(
        type_code=5,
        value=struct.pack('!I', local_pref),
        optional=False,
        transitive=True,
    )


def create_eor_message():
    """Create End-of-RIB (EOR) marker for IPv4 unicast.

    Returns:
        bytes: EOR message (4 bytes of zeros)
    """
    return b'\x00\x00\x00\x00'


def create_minimal_update(nlri_prefix=None):
    """Create minimal valid UPDATE message.

    Args:
        nlri_prefix: Optional tuple (ip, prefix_len) for announced route

    Returns:
        bytes: Minimal UPDATE message
    """
    if nlri_prefix:
        ip, prefix_len = nlri_prefix
        nlri = create_ipv4_prefix(ip, prefix_len)

        # Need mandatory attributes for announcement
        attributes = (
            create_origin_attribute(0) +  # IGP
            create_as_path_attribute([]) +  # Empty AS_PATH
            create_next_hop_attribute("192.0.2.1")  # Some next-hop
        )

        return create_update_message(
            withdrawn_routes=b'',
            path_attributes=attributes,
            nlri=nlri,
        )
    # Empty UPDATE (EOR)
    return create_eor_message()


def create_withdrawal_update(prefixes):
    """Create UPDATE message with only withdrawals.

    Args:
        prefixes: List of (ip, prefix_len) tuples to withdraw

    Returns:
        bytes: UPDATE message with withdrawals
    """
    withdrawn = b''.join(create_ipv4_prefix(ip, plen) for ip, plen in prefixes)

    return create_update_message(
        withdrawn_routes=withdrawn,
        path_attributes=b'',
        nlri=b'',
    )


# Malformed message helpers for testing

def create_update_with_invalid_withdrawn_length(actual_data_length, claimed_length):
    """Create UPDATE with mismatched withdrawn routes length.

    Args:
        actual_data_length: Actual bytes of withdrawn data
        claimed_length: Length field value (will be wrong)

    Returns:
        bytes: Malformed UPDATE message
    """
    # Create actual withdrawn data
    withdrawn_data = b'\x00' * actual_data_length

    # Pack with incorrect length
    return struct.pack('!H', claimed_length) + withdrawn_data + b'\x00\x00'  # Zero attr length


def create_update_with_invalid_attr_length(withdrawn, actual_attr_length, claimed_attr_length):
    """Create UPDATE with mismatched path attributes length.

    Args:
        withdrawn: Withdrawn routes data
        actual_attr_length: Actual bytes of attributes
        claimed_attr_length: Length field value (will be wrong)

    Returns:
        bytes: Malformed UPDATE message
    """
    withdrawn_len = struct.pack('!H', len(withdrawn))
    attr_data = b'\x00' * actual_attr_length
    attr_len = struct.pack('!H', claimed_attr_length)

    return withdrawn_len + withdrawn + attr_len + attr_data


def create_truncated_update(valid_update, truncate_at):
    """Truncate an UPDATE message at specified byte.

    Args:
        valid_update: Valid UPDATE message bytes
        truncate_at: Byte position to truncate at

    Returns:
        bytes: Truncated UPDATE message
    """
    return valid_update[:truncate_at]


if __name__ == "__main__":
    # Quick self-test
    print("Testing UPDATE helper functions...")

    # Test EOR
    eor = create_eor_message()
    assert eor == b'\x00\x00\x00\x00', "EOR should be 4 zeros"
    print(f"✓ EOR: {eor.hex()}")

    # Test minimal update
    minimal = create_minimal_update()
    assert len(minimal) == 4, "Minimal UPDATE (no NLRI) should be EOR"
    print(f"✓ Minimal UPDATE: {minimal.hex()}")

    # Test prefix creation
    prefix = create_ipv4_prefix("192.0.2.0", 24)
    assert prefix == b'\x18\xc0\x00\x02', "Prefix should be correct"
    print(f"✓ Prefix 192.0.2.0/24: {prefix.hex()}")

    # Test UPDATE with announcement
    update_with_nlri = create_minimal_update(("10.0.0.0", 8))
    assert len(update_with_nlri) > 4, "UPDATE with NLRI should be larger than EOR"
    print(f"✓ UPDATE with NLRI: {len(update_with_nlri)} bytes")

    # Test withdrawal
    withdrawal = create_withdrawal_update([("192.0.2.0", 24), ("10.0.0.0", 8)])
    assert len(withdrawal) > 4, "Withdrawal should have data"
    print(f"✓ Withdrawal UPDATE: {len(withdrawal)} bytes")

    print("\nAll helper tests passed! ✓")
