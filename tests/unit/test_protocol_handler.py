"""Comprehensive tests for BGP Protocol Handler (Extended).

These tests cover src/exabgp/reactor/protocol.py:

Test Coverage:
- Protocol initialization and configuration
- Connection management (accept, close)
- File descriptor access
- Session identification
- Message statistics tracking
- Read and write operations (basic)
- EOR (End-of-RIB) handling
- API callback integration
"""
import pytest
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture(autouse=True)
def mock_logger():
    """Mock the logger to avoid initialization issues."""
    from exabgp.logger.option import option

    original_logger = option.logger
    original_formater = option.formater

    mock_option_logger = Mock()
    mock_option_logger.debug = Mock()
    mock_option_logger.info = Mock()
    mock_option_logger.warning = Mock()
    mock_option_logger.error = Mock()
    mock_option_logger.critical = Mock()

    mock_formater = Mock(return_value="formatted message")

    option.logger = mock_option_logger
    option.formater = mock_formater

    yield

    option.logger = original_logger
    option.formater = original_formater


@pytest.fixture
def mock_neighbor():
    """Create a mock neighbor configuration."""
    neighbor = MagicMock()
    neighbor.__getitem__ = Mock(side_effect=lambda x: {
        'peer-address': Mock(top=Mock(return_value='192.0.2.1'), afi=1, __str__=Mock(return_value='192.0.2.1')),
        'peer-as': 65001,
        'local-as': 65000,
        'local-address': None,
        'router-id': Mock(__str__=Mock(return_value='1.2.3.4')),
        'hold-time': 180,
        'connect': None,
        'md5-ip': Mock(top=Mock(return_value=None)),
        'md5-password': None,
        'md5-base64': False,
        'outgoing-ttl': None,
        'source-interface': None,
        'adj-rib-in': False,
        'capability': {'aigp': False},
    }.get(x))
    neighbor.auto_discovery = False
    neighbor.api = {
        'neighbor-changes': False,
        'receive-packets': False,
        'receive-parsed': False,
        'receive-consolidate': False,
        'send-packets': False,
        'send-parsed': False,
        'send-consolidate': False,
        'negotiated': False,
    }
    # Allow iteration for mismatch checking
    neighbor.ip_self = Mock(return_value=None)
    return neighbor


@pytest.fixture
def mock_peer(mock_neighbor):
    """Create a mock peer."""
    # Create a custom stats class that behaves like defaultdict
    class Stats(dict):
        def __getitem__(self, key):
            if key not in self:
                self[key] = 0
            return super().__getitem__(key)

    peer = Mock()
    peer.neighbor = mock_neighbor
    peer.stats = Stats()
    peer._restarted = False
    peer.reactor = Mock()
    peer.reactor.processes = Mock()
    peer.reactor.processes.connected = Mock()
    peer.reactor.processes.message = Mock()
    peer.reactor.processes.packets = Mock()
    peer.reactor.processes.notification = Mock()
    peer.reactor.processes.negotiated = Mock()
    return peer


# ==============================================================================
# Phase 1: Protocol Initialization and Basic Operations
# ==============================================================================

def test_protocol_initialization(mock_peer):
    """Test Protocol initialization with neighbor configuration."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)

    assert protocol.peer == mock_peer
    assert protocol.neighbor == mock_peer.neighbor
    assert protocol.connection is None
    assert protocol.port == 179  # Default BGP port
    assert protocol.negotiated is not None


def test_protocol_environment_port(mock_peer, monkeypatch):
    """Test Protocol initialization with port from environment variable."""
    from exabgp.reactor.protocol import Protocol

    monkeypatch.setenv('exabgp.tcp.port', '2179')
    protocol = Protocol(mock_peer)

    assert protocol.port == 2179


def test_protocol_fd_no_connection(mock_peer):
    """Test file descriptor access without active connection."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)
    assert protocol.fd() == -1


def test_protocol_fd_with_connection(mock_peer):
    """Test file descriptor access with active connection."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)
    mock_connection = Mock()
    mock_connection.fd = Mock(return_value=42)
    protocol.connection = mock_connection

    assert protocol.fd() == 42


def test_protocol_me_message(mock_peer):
    """Test session identification string generation."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)
    message = protocol.me('test message')

    assert '65001' in message
    assert 'test message' in message


def test_protocol_accept(mock_peer):
    """Test accepting an incoming connection."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)
    mock_incoming = Mock()
    mock_incoming.session = Mock(return_value='test-session')

    result = protocol.accept(mock_incoming)

    assert protocol.connection == mock_incoming
    assert result == protocol


def test_protocol_accept_with_api_notification(mock_peer):
    """Test accepting connection with API notification enabled."""
    from exabgp.reactor.protocol import Protocol

    mock_peer.neighbor.api['neighbor-changes'] = True
    protocol = Protocol(mock_peer)

    mock_incoming = Mock()
    protocol.accept(mock_incoming)

    mock_peer.reactor.processes.connected.assert_called_once()


def test_protocol_close_no_connection(mock_peer):
    """Test closing when no connection exists."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)
    protocol.close('test reason')

    assert protocol.connection is None


def test_protocol_close_with_connection(mock_peer):
    """Test closing an active connection."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.session = Mock(return_value='test-session')
    mock_connection.close = Mock()
    protocol.connection = mock_connection

    protocol.close('test reason')

    mock_connection.close.assert_called_once()
    assert protocol.connection is None
    assert mock_peer.stats['down'] == 1


# ==============================================================================
# Phase 2: Message Writing and Statistics
# ==============================================================================

def test_protocol_write_keepalive(mock_peer):
    """Test writing a KEEPALIVE message updates statistics."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message.keepalive import KeepAlive

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.writer = Mock(return_value=[True])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    keepalive = KeepAlive()
    result = list(protocol.write(keepalive, protocol.negotiated))

    assert mock_connection.writer.called
    assert mock_peer.stats['send-keepalive'] == 1
    assert result == [True]


def test_protocol_write_with_api_callback(mock_peer):
    """Test writing a message with API callback enabled."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message.keepalive import KeepAlive

    mock_peer.neighbor.api['send-keepalive'] = True
    mock_peer.neighbor.api['send-consolidate'] = True

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.writer = Mock(return_value=[True])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    keepalive = KeepAlive()
    list(protocol.write(keepalive, protocol.negotiated))

    mock_peer.reactor.processes.message.assert_called_once()


# ==============================================================================
# Phase 3: Message Reading - Basic
# ==============================================================================

def test_protocol_read_message_keepalive(mock_peer):
    """Test reading a KEEPALIVE message."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message import Message
    from exabgp.bgp.message.keepalive import KeepAlive

    protocol = Protocol(mock_peer)

    # Mock connection reader that yields KEEPALIVE
    mock_connection = Mock()
    mock_connection.reader = Mock(return_value=[
        (19, Message.CODE.KEEPALIVE, b'\xff' * 19, b'', None)
    ])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    messages = list(protocol.read_message())

    assert len(messages) == 1
    assert messages[0].TYPE == KeepAlive.TYPE
    assert mock_peer.stats['receive-keepalive'] == 1


def test_protocol_read_message_nop(mock_peer):
    """Test reading when no data is available (NOP)."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message import Message, NOP

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.reader = Mock(return_value=[
        (0, Message.CODE.KEEPALIVE, b'', b'', None)
    ])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    messages = list(protocol.read_message())

    assert len(messages) == 1
    assert messages[0].TYPE == NOP.TYPE


def test_protocol_read_message_invalid_type(mock_peer):
    """Test reading a message with invalid type."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message import Notify

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.reader = Mock(return_value=[
        (19, 99, b'\xff' * 19, b'', None)
    ])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    with pytest.raises(Notify) as exc_info:
        list(protocol.read_message())

    assert exc_info.value.code == 1  # Message Header Error


# ==============================================================================
# Phase 4: EOR (End-of-RIB) Support
# ==============================================================================

def test_protocol_new_eor_single_family(mock_peer):
    """Test creating and sending EOR for a single address family."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message import EOR

    protocol = Protocol(mock_peer)
    protocol.negotiated.families = [(AFI.ipv4, SAFI.unicast)]

    mock_connection = Mock()
    mock_connection.writer = Mock(return_value=[True])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    messages = list(protocol.new_eor(AFI.ipv4, SAFI.unicast))

    assert any(hasattr(msg, 'TYPE') and msg.TYPE == EOR.TYPE for msg in messages if hasattr(msg, 'TYPE'))


def test_protocol_new_eors_all_families(mock_peer):
    """Test creating and sending EOR markers for all negotiated families."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.protocol.family import AFI, SAFI

    protocol = Protocol(mock_peer)
    protocol.negotiated.families = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
    ]

    mock_connection = Mock()
    mock_connection.writer = Mock(return_value=[True])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    list(protocol.new_eors())

    # Verify writer was called multiple times (once per EOR)
    assert mock_connection.writer.call_count >= 2


def test_protocol_new_eors_no_families(mock_peer):
    """Test new_eors() when no families are negotiated sends KEEPALIVE."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)
    protocol.negotiated.families = []

    mock_connection = Mock()
    mock_connection.writer = Mock(return_value=[True])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    list(protocol.new_eors())

    assert mock_connection.writer.called


# ==============================================================================
# Phase 5: Advanced Features
# ==============================================================================

def test_protocol_read_update_basic(mock_peer):
    """Test reading a basic UPDATE message."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message import Message
    import struct

    protocol = Protocol(mock_peer)
    protocol.neighbor.api['receive-parsed'] = True

    # Create minimal UPDATE message
    update_body = struct.pack('!HH', 0, 0)  # withdrawn_len=0, attr_len=0

    mock_connection = Mock()
    mock_connection.reader = Mock(return_value=[
        (23, Message.CODE.UPDATE, b'\xff' * 19, update_body, None)
    ])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    messages = list(protocol.read_message())

    assert len(messages) > 0


def test_protocol_api_callbacks_with_packets(mock_peer):
    """Test API callbacks with packet data enabled."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message import Message

    mock_peer.neighbor.api['receive-keepalive'] = True
    mock_peer.neighbor.api['receive-packets'] = True

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.reader = Mock(return_value=[
        (19, Message.CODE.KEEPALIVE, b'\xff' * 19, b'', None)
    ])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    list(protocol.read_message())

    mock_peer.reactor.processes.packets.assert_called()


def test_protocol_negotiated_initialization(mock_peer):
    """Test that negotiated state is properly initialized."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

    protocol = Protocol(mock_peer)

    assert protocol.negotiated is not None
    assert isinstance(protocol.negotiated, Negotiated)
    assert protocol.negotiated.neighbor == mock_peer.neighbor


def test_protocol_port_from_environment_legacy(mock_peer, monkeypatch):
    """Test protocol port configuration from legacy environment variable."""
    from exabgp.reactor.protocol import Protocol

    monkeypatch.setenv('exabgp_tcp_port', '3179')
    protocol = Protocol(mock_peer)

    assert protocol.port == 3179


def test_protocol_new_keepalive(mock_peer):
    """Test creating and sending a KEEPALIVE message."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message.keepalive import KeepAlive

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.writer = Mock(return_value=[True])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    messages = list(protocol.new_keepalive())

    assert any(hasattr(msg, 'TYPE') and msg.TYPE == KeepAlive.TYPE for msg in messages if hasattr(msg, 'TYPE'))


def test_protocol_new_keepalive_with_comment(mock_peer):
    """Test creating KEEPALIVE with comment for logging."""
    from exabgp.reactor.protocol import Protocol

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.writer = Mock(return_value=[True])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    list(protocol.new_keepalive('test comment'))

    assert mock_connection.writer.called


def test_protocol_read_open_wrong_message(mock_peer):
    """Test read_open() when first message is not OPEN."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message import Message, Notify

    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.reader = Mock(return_value=[
        (19, Message.CODE.KEEPALIVE, b'\xff' * 19, b'', None)
    ])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    with pytest.raises(Notify) as exc_info:
        list(protocol.read_open('192.0.2.1'))

    assert exc_info.value.code == 5  # FSM Error
    assert exc_info.value.subcode == 1


def test_protocol_read_keepalive_wrong_message(mock_peer):
    """Test read_keepalive() when message is not KEEPALIVE."""
    from exabgp.reactor.protocol import Protocol
    from exabgp.bgp.message import Message, Notify
    import struct

    protocol = Protocol(mock_peer)

    # Mock connection that returns UPDATE instead of KEEPALIVE
    mock_connection = Mock()
    mock_connection.reader = Mock(return_value=[
        (23, Message.CODE.UPDATE, b'\xff' * 19, struct.pack('!HH', 0, 0), None)
    ])
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    with pytest.raises(Notify) as exc_info:
        list(protocol.read_keepalive())

    assert exc_info.value.code == 5  # FSM Error
    assert exc_info.value.subcode == 2
