"""Helper utilities for performance testing.

Provides functions to create high volumes of test data and mock objects
for performance benchmarking.
"""

import struct
from io import BytesIO
from unittest.mock import Mock, MagicMock
from exabgp.bgp.message import Message, Update, KeepAlive, Notification, Open
from exabgp.bgp.message.update.nlri import NLRI
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath
from exabgp.bgp.message.update.attribute.nexthop import NextHop
from exabgp.protocol.ip import IPv4, NoNextHop
from exabgp.bgp.neighbor import Neighbor
from exabgp.reactor.protocol import Protocol


def create_mock_logger():
    """Create a mock logger for testing."""
    logger = Mock()
    logger.debug = Mock()
    logger.info = Mock()
    logger.warning = Mock()
    logger.error = Mock()
    logger.critical = Mock()
    logger.network = Mock()
    logger.packets = Mock()
    return logger


def create_mock_negotiated(add_path=False, extended_message=False):
    """Create a mock negotiated capabilities object."""
    negotiated = Mock()
    negotiated.families = {(1, 1)}  # IPv4 Unicast
    negotiated.addpath = Mock()
    negotiated.addpath.receive = Mock(return_value=add_path)
    negotiated.addpath.send = Mock(return_value=add_path)
    negotiated.extended_message = extended_message
    return negotiated


def create_mock_neighbor(asn=65000, router_id='1.2.3.4'):
    """Create a mock neighbor configuration."""
    neighbor = Mock(spec=Neighbor)
    neighbor.peer_address = IPv4.create('192.0.2.1')
    neighbor.local_address = IPv4.create('192.0.2.2')
    neighbor.peer_as = asn
    neighbor.local_as = 65001
    neighbor.router_id = IPv4.create(router_id)
    neighbor.hold_time = 180
    return neighbor


def create_simple_update_bytes(num_routes=1, base_prefix='10.0.0.0/24'):
    """Create raw bytes for a simple UPDATE message with specified number of routes.

    Args:
        num_routes: Number of NLRI prefixes to include
        base_prefix: Base prefix to use (will increment for multiple routes)

    Returns:
        bytes: Raw BGP UPDATE message
    """
    # Parse base prefix
    prefix_parts = base_prefix.split('/')
    prefix_ip = prefix_parts[0]
    prefix_len = int(prefix_parts[1])

    # Convert IP to integer for easy incrementing
    ip_parts = [int(x) for x in prefix_ip.split('.')]
    base_ip_int = (ip_parts[0] << 24) + (ip_parts[1] << 16) + (ip_parts[2] << 8) + ip_parts[3]

    # Build path attributes
    attributes = b''

    # ORIGIN (type=1, length=1, value=IGP)
    attributes += struct.pack('!BBB', 0x40, 1, 1)  # flags, type, length
    attributes += b'\x00'  # IGP

    # AS_PATH (type=2, empty AS_SEQUENCE)
    attributes += struct.pack('!BBB', 0x40, 2, 0)  # flags, type, length (empty)

    # NEXT_HOP (type=3, length=4)
    attributes += struct.pack('!BBB', 0x40, 3, 4)  # flags, type, length
    attributes += struct.pack('!I', 0xC0000201)  # 192.0.2.1

    # Build NLRI (announced routes)
    nlri = b''
    for i in range(num_routes):
        ip_int = base_ip_int + (i * 256)  # Increment by /24 blocks
        ip_bytes = struct.pack('!I', ip_int)

        # Encode prefix length and IP bytes needed
        bytes_needed = (prefix_len + 7) // 8
        nlri += struct.pack('!B', prefix_len) + ip_bytes[:bytes_needed]

    # Build UPDATE message
    withdrawn_len = 0
    path_attr_len = len(attributes)

    update_body = struct.pack('!H', withdrawn_len)  # withdrawn routes length
    update_body += struct.pack('!H', path_attr_len)  # path attributes length
    update_body += attributes
    update_body += nlri

    # Build BGP header
    marker = b'\xff' * 16
    length = 19 + len(update_body)
    msg_type = 2  # UPDATE

    message = marker + struct.pack('!HB', length, msg_type) + update_body

    return message


def create_keepalive_bytes():
    """Create raw bytes for a KEEPALIVE message."""
    marker = b'\xff' * 16
    length = 19
    msg_type = 4  # KEEPALIVE
    return marker + struct.pack('!HB', length, msg_type)


def create_notification_bytes(error_code=6, error_subcode=0):
    """Create raw bytes for a NOTIFICATION message."""
    marker = b'\xff' * 16
    body = struct.pack('!BB', error_code, error_subcode)
    length = 19 + len(body)
    msg_type = 3  # NOTIFICATION
    return marker + struct.pack('!HB', length, msg_type) + body


def create_large_update_bytes(num_attributes=10, num_routes=100):
    """Create a large UPDATE message with many attributes and routes.

    Args:
        num_attributes: Number of path attributes (will add communities)
        num_routes: Number of NLRI prefixes

    Returns:
        bytes: Raw BGP UPDATE message
    """
    # Build base attributes
    attributes = b''

    # ORIGIN
    attributes += struct.pack('!BBB', 0x40, 1, 1)
    attributes += b'\x00'  # IGP

    # AS_PATH (add some AS numbers)
    as_sequence = struct.pack('!BHHHHH', 2, 65001, 65002, 65003, 65004, 65005)  # type, 5 ASNs
    attributes += struct.pack('!BBB', 0x40, 2, len(as_sequence))
    attributes += as_sequence

    # NEXT_HOP
    attributes += struct.pack('!BBB', 0x40, 3, 4)
    attributes += struct.pack('!I', 0xC0000201)

    # Add COMMUNITIES for additional attributes
    for i in range(num_attributes - 3):  # Already have 3 base attributes
        community = struct.pack('!I', 65000 << 16 | (100 + i))
        if i == 0:
            attributes += struct.pack('!BBB', 0xC0, 8, 4)  # First community attribute
            attributes += community
        # Note: Multiple communities would need to be in one attribute

    # Build NLRI with many routes
    nlri = b''
    for i in range(num_routes):
        prefix_len = 24
        # 10.0.0.0/24, 10.0.1.0/24, etc.
        ip_bytes = struct.pack('!BBB', 10, i // 256, i % 256)
        nlri += struct.pack('!B', prefix_len) + ip_bytes

    # Build UPDATE message
    update_body = struct.pack('!H', 0)  # withdrawn routes length
    update_body += struct.pack('!H', len(attributes))  # path attributes length
    update_body += attributes
    update_body += nlri

    # Build BGP header
    marker = b'\xff' * 16
    length = 19 + len(update_body)
    msg_type = 2  # UPDATE

    return marker + struct.pack('!HB', length, msg_type) + update_body


def create_mock_connection_with_data(data_bytes):
    """Create a mock connection object that will return specified data.

    Args:
        data_bytes: bytes to return from the connection

    Returns:
        Mock connection object
    """
    from exabgp.reactor.network.connection import Connection

    connection = Mock(spec=Connection)
    connection.io = BytesIO(data_bytes)
    connection.logger = create_mock_logger()

    # Mock socket operations
    original_read = connection.io.read

    def mock_read(size):
        return original_read(size)

    connection.io.read = mock_read

    return connection


def create_batch_messages(message_type='update', count=1000):
    """Create a batch of BGP messages for load testing.

    Args:
        message_type: Type of message ('update', 'keepalive', 'notification')
        count: Number of messages to create

    Returns:
        bytes: Concatenated BGP messages
    """
    if message_type == 'update':
        single_msg = create_simple_update_bytes(num_routes=1)
    elif message_type == 'keepalive':
        single_msg = create_keepalive_bytes()
    elif message_type == 'notification':
        single_msg = create_notification_bytes()
    else:
        raise ValueError(f"Unknown message type: {message_type}")

    return single_msg * count


def create_mixed_message_batch(update_count=500, keepalive_count=300, notification_count=200):
    """Create a batch of mixed message types.

    Args:
        update_count: Number of UPDATE messages
        keepalive_count: Number of KEEPALIVE messages
        notification_count: Number of NOTIFICATION messages

    Returns:
        bytes: Concatenated BGP messages in mixed order
    """
    messages = []

    # Create messages
    for _ in range(update_count):
        messages.append(create_simple_update_bytes())

    for _ in range(keepalive_count):
        messages.append(create_keepalive_bytes())

    for _ in range(notification_count):
        messages.append(create_notification_bytes())

    # Interleave them for realistic pattern
    result = b''
    update_idx = 0
    keepalive_idx = update_count
    notif_idx = update_count + keepalive_count

    total = update_count + keepalive_count + notification_count
    for i in range(total):
        if i % 3 == 0 and update_idx < update_count:
            result += messages[update_idx]
            update_idx += 1
        elif i % 3 == 1 and keepalive_idx < update_count + keepalive_count:
            result += messages[keepalive_idx]
            keepalive_idx += 1
        elif notif_idx < total:
            result += messages[notif_idx]
            notif_idx += 1

    # Add any remaining
    result += b''.join(messages[update_idx:keepalive_idx])
    result += b''.join(messages[keepalive_idx:notif_idx])
    result += b''.join(messages[notif_idx:])

    return result
