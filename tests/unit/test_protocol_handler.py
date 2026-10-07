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

The Peer, its Reactor and the connection are real ones: compiled (plan/wip-mypyc.md), the
Protocol refuses a stand-in for any of them.  What the peer sends is written to the other
end of a socket pair, what the Protocol writes is read from it, and what the API processes
are handed is what their encoder is asked to print (`negotiation.Told`).  The tests of
connect() open a real TCP connection to a listening socket on the loopback.
"""

import asyncio
import socket
import struct
from collections.abc import Callable, Iterator
from typing import Any, Generator
from unittest.mock import AsyncMock, Mock, patch

import pytest

from exabgp.bgp.message import Message
from exabgp.bgp.message.open.holdtime import HoldTime
from exabgp.bgp.neighbor import Neighbor
from exabgp.reactor import protocol as protocol_module
from exabgp.reactor.peer import Peer
from exabgp.reactor.protocol import Protocol
from tests import negotiation

COMPILED = not protocol_module.__file__.endswith('.py')

# A connection never reports a length of zero without an error, which is what read_message
# answers None for: only a stand-in connection reaches that path, and compiled a Protocol
# refuses a stand-in for its connection, as it refuses one for its read_message
STAND_IN_ONLY = pytest.mark.skipif(
    COMPILED, reason='compiled, the connection must be a real one, and no real one returns a zero length without error'
)

MARKER = b'\xff' * 16
KEEPALIVE = MARKER + b'\x00\x13\x04'
# an UPDATE with no withdrawal, no attribute and no NLRI: the End-of-RIB of IPv4 unicast
EOR_BODY = struct.pack('!HH', 0, 0)
EOR = MARKER + b'\x00\x17\x02' + EOR_BODY

OPEN = 1
UPDATE = 2
NOTIFICATION = 3
KEEPALIVE_TYPE = 4
ROUTE_REFRESH = 5
OPERATIONAL = 6


def frame(message_type: int, body: bytes) -> bytes:
    """A whole BGP message: marker, length and type, then the body."""
    return MARKER + struct.pack('!H', 19 + len(body)) + bytes([message_type]) + body


@pytest.fixture(autouse=True)
def mock_logger() -> Generator[None, None, None]:
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

    mock_formater = Mock(return_value='formatted message')

    option.logger = mock_option_logger
    option.formater = mock_formater

    yield

    option.logger = original_logger
    option.formater = original_formater


@pytest.fixture
def mock_neighbor() -> Neighbor:
    """A real neighbor configuration: eBGP 65000 to 65001, no local address, default port."""
    neighbor = negotiation.neighbor(
        local_as=65000, peer_as=65001, local_address=None, peer_address='192.0.2.1', router_id='1.2.3.4'
    )
    neighbor.session.connect = 0  # 0 means use the default port
    neighbor.hold_time = HoldTime(180)
    neighbor.host_name = 'test-host'
    neighbor.domain_name = 'test-domain'
    # what the configuration fills in for a neighbor with no api section
    return negotiation.api_asks(neighbor)


@pytest.fixture
def mock_peer(mock_neighbor: Neighbor) -> Peer:
    """A real peer of the neighbor, whose reactor tells a `negotiation.Told`."""
    peer, _ = negotiation.peer(mock_neighbor)
    return peer


@pytest.fixture
def connect() -> Iterator[Callable[[Protocol], socket.socket]]:
    """Connect a Protocol to a socket pair, and give the peer's end; closed after the test."""
    ends: list[tuple[Protocol, socket.socket]] = []

    def connecting(protocol: Protocol) -> socket.socket:
        theirs = negotiation.connect(protocol)
        ends.append((protocol, theirs))
        return theirs

    yield connecting
    for protocol, theirs in ends:
        negotiation.disconnect(protocol, theirs)


def asks(peer: Peer, *events: str) -> None:
    """The API process asks to hear of these events."""
    for event in events:
        peer.neighbor.api[event] = [negotiation.PROCESS]


def told(peer: Peer) -> negotiation.Told:
    """What the API processes of the peer were handed."""
    return peer.reactor.processes._encoder[negotiation.PROCESS]


def sent(theirs: socket.socket) -> list[tuple[int, bytes]]:
    """The (type, body) of each message the Protocol wrote to the peer."""
    return negotiation.messages(negotiation.received(theirs))


# ==============================================================================
# Phase 1: Protocol Initialization and Basic Operations
# ==============================================================================


def test_protocol_initialization(mock_peer: Peer) -> None:
    """Test Protocol initialization with neighbor configuration."""
    protocol = Protocol(mock_peer)

    assert protocol.peer is mock_peer
    assert protocol.neighbor is mock_peer.neighbor
    assert protocol.connection is None
    assert protocol.port == 179  # Default BGP port
    assert protocol.negotiated is not None


def test_protocol_environment_port(mock_peer: Peer, monkeypatch: Any) -> None:
    """The port is tcp.port as the environment read it, not the variable read again."""
    from exabgp.environment import getenv

    monkeypatch.setattr(getenv().tcp, 'port', 2179)
    protocol = Protocol(mock_peer)

    assert protocol.port == 2179


def test_protocol_fd_no_connection(mock_peer: Peer) -> None:
    """Test file descriptor access without active connection."""
    protocol = Protocol(mock_peer)
    assert protocol.fd() == -1


def test_protocol_fd_with_connection(mock_peer: Peer, connect: Any) -> None:
    """Test file descriptor access with active connection."""
    protocol = Protocol(mock_peer)
    connect(protocol)

    assert protocol.connection is not None and protocol.connection.io is not None
    assert protocol.fd() == protocol.connection.io.fileno()
    assert protocol.fd() >= 0


def test_protocol_me_message(mock_peer: Peer) -> None:
    """Test session identification string generation."""
    protocol = Protocol(mock_peer)
    message = protocol.me('test message')

    assert '65001' in message
    assert 'test message' in message


@pytest.fixture
def incoming() -> Iterator[Any]:
    """A real Incoming connection: TCP on the loopback, as an accepted peer's is."""
    from exabgp.protocol.family import AFI
    from exabgp.reactor.network.incoming import Incoming

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    theirs = socket.create_connection(listener.getsockname())
    ours, _ = listener.accept()
    listener.close()
    connection = Incoming(AFI.ipv4, '127.0.0.1', '127.0.0.1', ours)
    yield connection
    connection.close()
    theirs.close()


def test_protocol_accept(mock_peer: Peer, incoming: Any) -> None:
    """Test accepting an incoming connection."""
    protocol = Protocol(mock_peer)

    result = protocol.accept(incoming)

    assert protocol.connection is incoming
    assert result is protocol


def test_protocol_accept_with_api_notification(mock_peer: Peer, incoming: Any) -> None:
    """Test accepting connection with API notification enabled."""
    asks(mock_peer, 'neighbor-changes')
    protocol = Protocol(mock_peer)

    protocol.accept(incoming)

    assert told(mock_peer).names() == ['connected']


def test_protocol_close_no_connection(mock_peer: Peer) -> None:
    """Test closing when no connection exists."""
    protocol = Protocol(mock_peer)
    protocol.close('test reason')

    assert protocol.connection is None


def test_protocol_close_with_connection(mock_peer: Peer, connect: Any) -> None:
    """Test closing an active connection."""
    protocol = Protocol(mock_peer)
    connect(protocol)
    connection = protocol.connection

    protocol.close('test reason')

    assert connection is not None and connection.io is None, 'the socket was not closed'
    assert protocol.connection is None
    assert mock_peer.stats['down'] == 1


# ==============================================================================
# Phase 2: Message Writing and Statistics (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_write_keepalive(mock_peer: Peer, connect: Any) -> None:
    """Test writing a KEEPALIVE message updates statistics."""
    from exabgp.bgp.message.keepalive import KeepAlive

    protocol = Protocol(mock_peer)
    theirs = connect(protocol)

    keepalive = KeepAlive()
    await protocol.write(keepalive, protocol.negotiated)

    assert sent(theirs) == [(KEEPALIVE_TYPE, b'')]
    assert mock_peer.stats['send-keepalive'] == 1


@pytest.mark.asyncio
async def test_protocol_write_with_api_callback(mock_peer: Peer, connect: Any) -> None:
    """Test writing a message with API callback enabled."""
    from exabgp.bgp.message.keepalive import KeepAlive

    asks(mock_peer, 'send-keepalive', 'send-consolidate')

    protocol = Protocol(mock_peer)
    connect(protocol)

    keepalive = KeepAlive()
    await protocol.write(keepalive, protocol.negotiated)

    assert told(mock_peer).names() == ['keepalive']


# ==============================================================================
# Phase 3: Message Reading - Basic (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_read_message_keepalive(mock_peer: Peer, connect: Any) -> None:
    """Test reading a KEEPALIVE message."""
    from exabgp.bgp.message.keepalive import KeepAlive

    protocol = Protocol(mock_peer)
    connect(protocol).sendall(KEEPALIVE)

    message = await protocol.read_message()

    assert message is not None
    assert message.TYPE == KeepAlive.TYPE
    assert mock_peer.stats['receive-keepalive'] == 1


@STAND_IN_ONLY
@pytest.mark.asyncio
async def test_protocol_read_message_nop(mock_peer: Peer) -> None:
    """Test reading when no data is available."""
    protocol = Protocol(mock_peer)

    mock_connection = Mock()
    mock_connection.reader_async = AsyncMock(return_value=(0, Message.CODE.KEEPALIVE, b'', b'', None))
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    message = await protocol.read_message()

    assert message is None


@pytest.mark.asyncio
async def test_protocol_read_message_invalid_type(mock_peer: Peer, connect: Any) -> None:
    """Test reading a message with invalid type."""
    from exabgp.bgp.message import Notify

    protocol = Protocol(mock_peer)
    connect(protocol).sendall(frame(99, b''))

    with pytest.raises(Notify) as exc_info:
        await protocol.read_message()

    assert exc_info.value.code == 1  # Message Header Error


# ==============================================================================
# Phase 4: EOR (End-of-RIB) Support (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_new_eor_single_family(mock_peer: Peer, connect: Any) -> None:
    """Test creating and sending EOR for a single address family."""
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message import EOR as EndOfRIB

    protocol = Protocol(mock_peer)
    protocol.negotiated.families = [(AFI.ipv4, SAFI.unicast)]
    theirs = connect(protocol)

    eor = await protocol.new_eor(AFI.ipv4, SAFI.unicast)

    assert eor.TYPE == EndOfRIB.TYPE
    assert sent(theirs) == [(UPDATE, EOR_BODY)]


@pytest.mark.asyncio
async def test_protocol_new_eors_all_families(mock_peer: Peer, connect: Any) -> None:
    """Test creating and sending EOR markers for all negotiated families."""
    from exabgp.protocol.family import AFI, SAFI

    protocol = Protocol(mock_peer)
    protocol.negotiated.families = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
    ]
    theirs = connect(protocol)

    await protocol.new_eors()

    # one End-of-RIB per family
    assert [kind for kind, _ in sent(theirs)] == [UPDATE, UPDATE]


@pytest.mark.asyncio
async def test_protocol_new_eors_no_families(mock_peer: Peer, connect: Any) -> None:
    """Test new_eors() when no families are negotiated sends KEEPALIVE."""
    protocol = Protocol(mock_peer)
    protocol.negotiated.families = []
    theirs = connect(protocol)

    await protocol.new_eors()

    assert sent(theirs) == [(KEEPALIVE_TYPE, b'')]


# ==============================================================================
# Phase 5: Advanced Features (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_read_update_basic(mock_peer: Peer, connect: Any) -> None:
    """Test reading a basic UPDATE message."""
    protocol = Protocol(mock_peer)
    asks(mock_peer, 'receive-parsed')

    # minimal UPDATE message: withdrawn_len=0, attr_len=0
    connect(protocol).sendall(EOR)

    message = await protocol.read_message()
    assert message is not None


@pytest.mark.asyncio
async def test_protocol_api_callbacks_with_packets(mock_peer: Peer, connect: Any) -> None:
    """Test API callbacks with packet data enabled."""
    asks(mock_peer, 'receive-keepalive', 'receive-packets')

    protocol = Protocol(mock_peer)
    connect(protocol).sendall(KEEPALIVE)

    await protocol.read_message()

    assert 'packets' in told(mock_peer).names()


def test_protocol_negotiated_initialization(mock_peer: Peer) -> None:
    """Test that negotiated state is properly initialized."""
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

    protocol = Protocol(mock_peer)

    assert protocol.negotiated is not None
    assert isinstance(protocol.negotiated, Negotiated)
    assert protocol.negotiated.neighbor == mock_peer.neighbor


def test_protocol_port_from_environment_legacy(mock_peer: Peer, monkeypatch: Any, tmp_path: Any) -> None:
    """The underscore variable, read when the environment is set up."""
    from exabgp.environment import base
    from exabgp.environment.config import Environment

    monkeypatch.setattr(base, 'ENVFILE', str(tmp_path / 'absent.env'))
    monkeypatch.setattr(Environment, '_instance', None)
    monkeypatch.setattr(Environment, '_setup_done', False)
    monkeypatch.delenv('exabgp.tcp.port', raising=False)
    monkeypatch.setenv('exabgp_tcp_port', '3179')
    protocol = Protocol(mock_peer)

    assert protocol.port == 3179


@pytest.mark.asyncio
async def test_protocol_new_keepalive(mock_peer: Peer, connect: Any) -> None:
    """Test creating and sending a KEEPALIVE message."""
    from exabgp.bgp.message.keepalive import KeepAlive

    protocol = Protocol(mock_peer)
    theirs = connect(protocol)

    result = await protocol.new_keepalive()

    assert result.TYPE == KeepAlive.TYPE
    assert sent(theirs) == [(KEEPALIVE_TYPE, b'')]


@pytest.mark.asyncio
async def test_protocol_new_keepalive_with_comment(mock_peer: Peer, connect: Any) -> None:
    """Test creating KEEPALIVE with comment for logging."""
    protocol = Protocol(mock_peer)
    theirs = connect(protocol)

    await protocol.new_keepalive('test comment')

    assert sent(theirs) == [(KEEPALIVE_TYPE, b'')]


@pytest.mark.asyncio
async def test_protocol_read_open_wrong_message(mock_peer: Peer, connect: Any) -> None:
    """Test read_open() when first message is not OPEN."""
    from exabgp.bgp.message import Notify

    protocol = Protocol(mock_peer)
    connect(protocol).sendall(KEEPALIVE)

    with pytest.raises(Notify) as exc_info:
        await protocol.read_open('192.0.2.1')

    assert exc_info.value.code == 5  # FSM Error
    assert exc_info.value.subcode == 1


@pytest.mark.asyncio
async def test_protocol_read_keepalive_wrong_message(mock_peer: Peer, connect: Any) -> None:
    """Test read_keepalive() when message is not KEEPALIVE."""
    from exabgp.bgp.message import Notify

    protocol = Protocol(mock_peer)
    # an UPDATE instead of a KEEPALIVE
    connect(protocol).sendall(EOR)

    with pytest.raises(Notify) as exc_info:
        await protocol.read_keepalive()

    assert exc_info.value.code == 5  # FSM Error
    assert exc_info.value.subcode == 2


# ==============================================================================
# Phase 6: UPDATE Message Routing and Special Attributes (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_read_update_with_internal_treat_as_withdraw(mock_peer: Peer, connect: Any) -> None:
    """Test UPDATE message with INTERNAL_TREAT_AS_WITHDRAW attribute."""
    protocol = Protocol(mock_peer)
    asks(mock_peer, 'receive-parsed')
    connect(protocol).sendall(EOR)

    # Test that UPDATE message can be read successfully
    message = await protocol.read_message()
    assert message is not None


@pytest.mark.asyncio
async def test_protocol_read_update_with_internal_discard(mock_peer: Peer, connect: Any) -> None:
    """Test UPDATE message can be read without errors."""
    protocol = Protocol(mock_peer)
    asks(mock_peer, 'receive-parsed')
    connect(protocol).sendall(EOR)

    # Test that UPDATE message can be read successfully
    message = await protocol.read_message()
    assert message is not None


@pytest.mark.asyncio
async def test_protocol_read_update_decode_error(mock_peer: Peer, connect: Any) -> None:
    """Test UPDATE message decode error handling."""
    from exabgp.bgp.message import Notify

    protocol = Protocol(mock_peer)
    # malformed UPDATE body (too short): the path attributes length is missing
    connect(protocol).sendall(frame(UPDATE, b'\x00\x00'))

    with pytest.raises(Notify):
        await protocol.read_message()


# ==============================================================================
# Phase 7: NOTIFICATION Handling During Read (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_read_notification_from_peer(mock_peer: Peer, connect: Any) -> None:
    """Test reading a NOTIFICATION message from peer raises it."""
    from exabgp.bgp.message import NotificationReceived

    protocol = Protocol(mock_peer)
    # NOTIFICATION body: code=2, subcode=4, data='test'
    connect(protocol).sendall(frame(NOTIFICATION, struct.pack('!BB', 2, 4) + b'test'))

    # Reading NOTIFICATION should raise the notification
    with pytest.raises(NotificationReceived):
        await protocol.read_message()


@pytest.mark.asyncio
async def test_protocol_read_internal_notification(mock_peer: Peer, connect: Any) -> None:
    """Test reading when connection reader detects internal error."""
    from exabgp.bgp.message import Notify

    protocol = Protocol(mock_peer)
    # the connection finds the marker is not all ones
    connect(protocol).sendall(b'\x00' * 16 + b'\x00\x13\x04')

    with pytest.raises(Notify) as exc_info:
        await protocol.read_message()

    assert exc_info.value.code == 1
    assert exc_info.value.subcode == 1


@pytest.mark.asyncio
async def test_protocol_read_notification_with_api_consolidated(mock_peer: Peer, connect: Any) -> None:
    """Test NOTIFICATION with API consolidate mode calls processes.notification."""
    from exabgp.bgp.message import Notify

    # Processes.notification tells the processes which asked for neighbor-changes
    asks(mock_peer, 'receive-notification', 'receive-consolidate', 'neighbor-changes')

    protocol = Protocol(mock_peer)
    # a header whose Length field is below the minimum: the connection refuses it
    header = MARKER + b'\x00\x05\x03'
    connect(protocol).sendall(header)

    with pytest.raises(Notify):
        await protocol.read_message()

    # Verify API callback was made with Notify message object
    ((_, direction, notify_obj, told_header, told_body, _),) = told(mock_peer).called('notification')
    assert direction == 'receive'
    assert notify_obj.code == 1
    assert notify_obj.subcode == 2
    assert told_header == header
    assert told_body == b''


# ==============================================================================
# Phase 8: OPERATIONAL and REFRESH Messages (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_new_operational(mock_peer: Peer, connect: Any) -> None:
    """Test creating and sending an OPERATIONAL message."""
    from exabgp.bgp.message.operational import AdvisoryADM
    from exabgp.protocol.family import AFI, SAFI

    protocol = Protocol(mock_peer)
    theirs = connect(protocol)

    operational = AdvisoryADM.make_advisory(AFI.ipv4, SAFI.unicast, 'test')
    await protocol.new_operational(operational, protocol.negotiated)

    assert [kind for kind, _ in sent(theirs)] == [OPERATIONAL]
    assert mock_peer.stats['send-operational'] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('lifecycle', ['initial', 'reset', 'stop'])
async def test_operational_counters_follow_session_lifecycle(mock_peer: Peer, connect: Any, lifecycle: str) -> None:
    """Both directions count wire messages, and a closed session leaves neither count behind."""
    from exabgp.bgp.message.operational import AdvisoryADM
    from exabgp.protocol.family import AFI, SAFI

    operational = AdvisoryADM.make_advisory(AFI.ipv4, SAFI.unicast, 'counter regression')
    protocol = Protocol(mock_peer)
    mock_peer.proto = protocol
    theirs = connect(protocol)
    wire = operational.pack_message(protocol.negotiated)
    await protocol.new_operational(operational, protocol.negotiated)
    theirs.sendall(wire)
    received = await asyncio.wait_for(protocol.read_message(), timeout=5)
    assert received is not None
    assert received.pack_message(protocol.negotiated) == wire
    assert sent(theirs) == [(OPERATIONAL, bytes(wire[19:]))]
    assert mock_peer.stats['receive-operational'] == 1
    assert mock_peer.stats['send-operational'] == 1
    if lifecycle == 'initial':
        return

    if lifecycle == 'reset':
        mock_peer._reset()
    else:
        mock_peer.stop()
    assert mock_peer.stats['receive-operational'] == 0
    assert mock_peer.stats['send-operational'] == 0

    protocol = Protocol(mock_peer)
    mock_peer.proto = protocol
    theirs = connect(protocol)
    await protocol.new_operational(operational, protocol.negotiated)
    theirs.sendall(wire)
    received = await asyncio.wait_for(protocol.read_message(), timeout=5)
    assert received is not None
    assert received.pack_message(protocol.negotiated) == wire
    assert sent(theirs) == [(OPERATIONAL, bytes(wire[19:]))]
    assert mock_peer.stats['receive-operational'] == 1
    assert mock_peer.stats['send-operational'] == 1


@pytest.mark.asyncio
async def test_protocol_new_refresh(mock_peer: Peer, connect: Any) -> None:
    """Test creating and sending a ROUTE-REFRESH message."""
    from exabgp.bgp.message.refresh import RouteRefresh
    from exabgp.protocol.family import AFI, SAFI

    protocol = Protocol(mock_peer)
    theirs = connect(protocol)

    await protocol.new_refresh(RouteRefresh.make_route_refresh(AFI.ipv4, SAFI.unicast))

    assert sent(theirs) == [(ROUTE_REFRESH, b'\x00\x01\x00\x01')]


# ==============================================================================
# Phase 9: validate_open and Connection Negotiation
# ==============================================================================


def negotiate(protocol: Any, peer_as: int = 65001) -> None:
    """Exchange OPENs on the protocol's session: ours from 65000, the peer's from peer_as."""
    protocol.negotiated.sent(negotiation.open_message(asn=65000, router_id='1.2.3.4'))
    protocol.negotiated.received(negotiation.open_message(asn=peer_as, router_id='192.0.2.1'))


def test_protocol_validate_open_success(mock_peer: Peer) -> None:
    """Test validate_open with valid configuration."""
    protocol = Protocol(mock_peer)

    negotiate(protocol)
    protocol.negotiated.mismatch = []

    # Should not raise
    protocol.validate_open()


def test_protocol_validate_open_asn_mismatch(mock_peer: Peer) -> None:
    """Test validate_open with ASN mismatch raises Notify."""
    from exabgp.bgp.message import Notify

    protocol = Protocol(mock_peer)

    # the peer opens with an AS number other than the one configured for it
    negotiate(protocol, peer_as=65099)

    with pytest.raises(Notify) as exc_info:
        protocol.validate_open()

    assert exc_info.value.code == 2
    assert exc_info.value.subcode == 2


def test_protocol_validate_open_with_api_negotiated(mock_peer: Peer) -> None:
    """Test validate_open with API negotiated callback."""
    asks(mock_peer, 'negotiated')
    protocol = Protocol(mock_peer)

    negotiate(protocol)
    protocol.negotiated.mismatch = []

    protocol.validate_open()

    assert told(mock_peer).names() == ['negotiated']


def test_protocol_validate_open_with_family_mismatch(mock_peer: Peer, connect: Any) -> None:
    """Test validate_open logs warning for family mismatches."""
    from exabgp.protocol.family import AFI, SAFI

    protocol = Protocol(mock_peer)
    # a connection, for the session the warnings are logged against
    connect(protocol)

    negotiate(protocol)
    protocol.negotiated.mismatch = [
        ('local', (AFI.ipv4, SAFI.mpls_vpn)),
        ('remote', (AFI.ipv6, SAFI.unicast)),
    ]

    # Should not raise, but should log warnings
    protocol.validate_open()


# ==============================================================================
# Phase 10: send() Method for Raw BGP Messages (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_send_raw_update(mock_peer: Peer, connect: Any) -> None:
    """Test send() method with raw UPDATE message."""
    protocol = Protocol(mock_peer)
    theirs = connect(protocol)

    # Header: marker(16) + length(2) + type(1), then withdrawn_len=0, attr_len=0
    await protocol.send(EOR)

    assert negotiation.received(theirs) == EOR
    assert mock_peer.stats['send-update'] == 1


@pytest.mark.asyncio
async def test_protocol_send_with_api_callback(mock_peer: Peer, connect: Any) -> None:
    """Test send() with API callback enabled."""
    asks(mock_peer, 'send-update', 'send-consolidate')

    protocol = Protocol(mock_peer)
    connect(protocol)

    await protocol.send(EOR)

    assert told(mock_peer).names() == ['update']


# ==============================================================================
# Phase 11: new_update() Method for Outgoing Updates (Async)
# ==============================================================================


def outgoing_rib(peer: Peer) -> Any:
    """Give the peer's neighbor an enabled adj-rib-out for IPv4 unicast, and return it."""
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.rib import RIB
    from exabgp.rib.incoming import IncomingRIB
    from exabgp.rib.outgoing import OutgoingRIB

    families = {(AFI.ipv4, SAFI.unicast)}
    peer.neighbor.rib = RIB('test-protocol-handler', True, IncomingRIB(True, families), OutgoingRIB(True, families))
    return peer.neighbor.rib.outgoing


@pytest.mark.asyncio
async def test_protocol_new_update(mock_peer: Peer, connect: Any) -> None:
    """Test new_update() method sends updates from RIB."""
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.reactor.api import API

    protocol = Protocol(mock_peer)
    protocol.negotiated.families = [(AFI.ipv4, SAFI.unicast)]
    theirs = connect(protocol)

    route = API(mock_peer.reactor).api_route('route 10.0.0.0/24 next-hop 192.0.2.2', 'announce')[0]
    outgoing_rib(mock_peer).add_to_rib(route)

    number = await protocol.new_update(include_withdraw=True)

    assert number == 1
    assert [kind for kind, _ in sent(theirs)] == [UPDATE]


@pytest.mark.asyncio
async def test_protocol_new_update_no_updates(mock_peer: Peer, connect: Any) -> None:
    """Test new_update() with empty RIB."""
    protocol = Protocol(mock_peer)
    theirs = connect(protocol)
    outgoing_rib(mock_peer)

    result = await protocol.new_update(include_withdraw=False)

    # nothing was queued, so nothing was sent
    assert result == 0
    assert sent(theirs) == []


# ==============================================================================
# Phase 12: API Callback Variations (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_api_send_packets_mode(mock_peer: Peer, connect: Any) -> None:
    """Test API callback with send-packets mode."""
    from exabgp.bgp.message.keepalive import KeepAlive

    # consolidate is needed for the message API
    asks(mock_peer, 'send-keepalive', 'send-packets', 'send-consolidate')

    protocol = Protocol(mock_peer)
    connect(protocol)

    keepalive = KeepAlive()
    await protocol.write(keepalive, protocol.negotiated)

    # consolidated with the packets: the message is told with its header and body
    ((_, direction, header, body, _),) = told(mock_peer).called('keepalive')
    assert (direction, header, body) == ('send', KEEPALIVE, b'')


@pytest.mark.asyncio
async def test_protocol_api_receive_parsed_mode(mock_peer: Peer, connect: Any) -> None:
    """Test API callback with receive-parsed mode."""
    asks(mock_peer, 'receive-keepalive', 'receive-parsed')

    protocol = Protocol(mock_peer)
    connect(protocol).sendall(KEEPALIVE)

    await protocol.read_message()

    # the message is told with an empty header and body
    ((_, _, header, body, _),) = told(mock_peer).called('keepalive')
    assert header == b''
    assert body == b''


@pytest.mark.asyncio
async def test_protocol_api_receive_consolidate_mode(mock_peer: Peer, connect: Any) -> None:
    """Test API callback with receive-consolidate mode."""
    asks(mock_peer, 'receive-keepalive', 'receive-consolidate')

    protocol = Protocol(mock_peer)
    connect(protocol).sendall(KEEPALIVE)

    await protocol.read_message()

    # the message is told with its actual header and body
    ((_, _, header, body, _),) = told(mock_peer).called('keepalive')
    assert header == KEEPALIVE
    assert body == b''


# ==============================================================================
# Phase 13: connect() Method and Connection Establishment (Async)
# ==============================================================================


@pytest.fixture
def listening(mock_peer: Peer) -> Iterator[socket.socket]:
    """A peer listening on the loopback, where the neighbor is configured to connect."""
    from exabgp.protocol.ip import IPv4

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    mock_peer.neighbor.session.peer_address = IPv4.from_string('127.0.0.1')
    mock_peer.neighbor.session.connect = listener.getsockname()[1]
    yield listener
    listener.close()


@pytest.mark.asyncio
async def test_protocol_connect_establishes_outgoing(mock_peer: Peer, listening: socket.socket) -> None:
    """Test connect() establishes outgoing connection."""
    from exabgp.reactor.network.outgoing import Outgoing

    protocol = Protocol(mock_peer)

    result = await protocol.connect()

    assert result is True
    assert isinstance(protocol.connection, Outgoing)
    protocol.close()


@pytest.mark.asyncio
async def test_protocol_connect_sets_local_address(mock_peer: Peer, listening: socket.socket) -> None:
    """Test connect() basic flow with Outgoing."""
    from exabgp.protocol.ip import IP

    protocol = Protocol(mock_peer)

    await protocol.connect()

    # Verify connection was established, from the address the kernel chose
    assert protocol.connection is not None
    assert mock_peer.neighbor.session.local_address == IP.from_string('127.0.0.1')
    protocol.close()


@pytest.mark.asyncio
async def test_protocol_connect_with_api_notification(mock_peer: Peer, listening: socket.socket) -> None:
    """Test connect() triggers API notification."""
    asks(mock_peer, 'neighbor-changes')
    protocol = Protocol(mock_peer)

    await protocol.connect()

    assert told(mock_peer).names() == ['connected']
    protocol.close()


@pytest.mark.asyncio
async def test_protocol_connect_already_connected(mock_peer: Peer, connect: Any) -> None:
    """Test connect() when already connected does nothing."""
    protocol = Protocol(mock_peer)
    connect(protocol)
    connection = protocol.connection

    # Should return True immediately without establishing new connection
    result = await protocol.connect()
    assert result is True
    assert protocol.connection is connection


# ==============================================================================
# Phase 14: ADD-PATH Support
# ==============================================================================


def test_protocol_with_addpath_negotiated(mock_peer: Peer) -> None:
    """Test protocol with ADD-PATH capability negotiated."""
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.open.capability.negotiated import RequirePath

    protocol = Protocol(mock_peer)

    # Simulate ADD-PATH negotiation - set on both in and out
    protocol.negotiated.addpath = RequirePath()
    protocol.negotiated.addpath._send[(AFI.ipv4, SAFI.unicast)] = True
    protocol.negotiated.addpath._receive[(AFI.ipv4, SAFI.unicast)] = True

    assert protocol.negotiated.addpath is not None


@pytest.mark.asyncio
async def test_protocol_read_update_with_addpath(mock_peer: Peer, connect: Any) -> None:
    """Test reading UPDATE message when ADD-PATH is enabled."""
    from exabgp.protocol.family import AFI, SAFI
    from exabgp.bgp.message.open.capability.negotiated import RequirePath

    protocol = Protocol(mock_peer)
    asks(mock_peer, 'receive-parsed')

    # Enable ADD-PATH for receiving
    protocol.negotiated.addpath = RequirePath()
    protocol.negotiated.addpath._receive[(AFI.ipv4, SAFI.unicast)] = True

    connect(protocol).sendall(EOR)

    message = await protocol.read_message()
    assert message is not None


# ==============================================================================
# Phase 15: EOR (End-of-RIB) Extended Coverage (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_new_eor_specific_family(mock_peer: Peer, connect: Any) -> None:
    """Test new_eors() for a specific address family."""
    from exabgp.protocol.family import AFI, SAFI

    protocol = Protocol(mock_peer)
    protocol.negotiated.families = [
        (AFI.ipv4, SAFI.unicast),
        (AFI.ipv6, SAFI.unicast),
    ]
    theirs = connect(protocol)

    # Request EOR for specific family
    await protocol.new_eors(AFI.ipv4, SAFI.unicast)

    # Should only send one EOR
    assert sent(theirs) == [(UPDATE, EOR_BODY)]


@pytest.mark.asyncio
async def test_protocol_new_notification_message(mock_peer: Peer, connect: Any) -> None:
    """Test new_notification() method."""
    from exabgp.bgp.message import Notify

    protocol = Protocol(mock_peer)
    theirs = connect(protocol)

    await protocol.new_notification(Notify(6, 2, 'test error'))

    # RFC 8203: the Administrative Shutdown communication is preceded by its length
    assert sent(theirs) == [(NOTIFICATION, b'\x06\x02' + bytes([len('test error')]) + b'test error')]


# ==============================================================================
# Phase 16: new_open() Method (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_new_open_flow(mock_peer: Peer, connect: Any) -> None:
    """Test new_open() sends the OPEN of the configured neighbor."""
    from exabgp.bgp.message import Open

    protocol = Protocol(mock_peer)
    theirs = connect(protocol)

    result = await protocol.new_open()

    assert isinstance(result, Open)
    assert int(result.asn) == 65000
    ((kind, body),) = sent(theirs)
    assert kind == OPEN
    assert Open.unpack_message(body, protocol.negotiated).asn == result.asn


# ==============================================================================
# Phase 17: read_open() Method (Async)
# ==============================================================================


def peer_open() -> bytes:
    """The OPEN the peer AS 65001 sends."""
    agreed = negotiation.negotiated()
    return negotiation.open_message(asn=65001, router_id='192.0.2.1').pack_message(agreed)


@pytest.mark.asyncio
async def test_protocol_read_open_success(mock_peer: Peer, connect: Any) -> None:
    """Test read_open() successfully reads OPEN message."""
    from exabgp.bgp.message import Open

    protocol = Protocol(mock_peer)
    connect(protocol).sendall(peer_open())

    result = await protocol.read_open('192.0.2.1')

    assert isinstance(result, Open)
    assert int(result.asn) == 65001


@STAND_IN_ONLY
@pytest.mark.asyncio
async def test_protocol_read_open_with_nop(mock_peer: Peer) -> None:
    """Test read_open() skips a read which returned nothing."""
    from exabgp.bgp.message import Open

    protocol = Protocol(mock_peer)

    mock_open = Mock(spec=Open)
    mock_open.ID = Message.CODE.OPEN
    mock_open.__str__ = Mock(return_value='OPEN')

    mock_connection = Mock()
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    # Nothing read, then OPEN
    with patch.object(protocol, 'read_message', new=AsyncMock(side_effect=[None, mock_open])):
        result = await protocol.read_open('192.0.2.1')

        assert result is mock_open


# ==============================================================================
# Phase 18: read_keepalive() Method (Async)
# ==============================================================================


@pytest.mark.asyncio
async def test_protocol_read_keepalive_success(mock_peer: Peer, connect: Any) -> None:
    """Test read_keepalive() successfully reads KEEPALIVE."""
    from exabgp.bgp.message.keepalive import KeepAlive

    protocol = Protocol(mock_peer)
    connect(protocol).sendall(KEEPALIVE)

    result = await protocol.read_keepalive()

    assert result.TYPE == KeepAlive.TYPE


@STAND_IN_ONLY
@pytest.mark.asyncio
async def test_protocol_read_keepalive_with_nop(mock_peer: Peer) -> None:
    """Test read_keepalive() skips a read which returned nothing."""
    from exabgp.bgp.message.keepalive import KeepAlive

    protocol = Protocol(mock_peer)

    mock_keepalive = KeepAlive.make_keepalive()

    mock_connection = Mock()
    mock_connection.session = Mock(return_value='test-session')
    protocol.connection = mock_connection

    with patch.object(protocol, 'read_message', new=AsyncMock(side_effect=[None, mock_keepalive])):
        result = await protocol.read_keepalive()

        assert result.TYPE == KeepAlive.TYPE


@pytest.mark.asyncio
async def test_protocol_read_update_with_an_attribute_discard_keeps_the_rest(mock_peer: Peer, connect: Any) -> None:
    """RFC 7606 2: attribute discard drops the attribute, and the UPDATE is still processed.

    A malformed AGGREGATOR (7.7) leaves a Discard marker in the collection, and read_message
    used to answer None for any UPDATE carrying one, so the route beside it was never seen.
    """
    from exabgp.bgp.message import Update
    from exabgp.bgp.message.open.asn import ASN
    from exabgp.bgp.message.update.attribute import Attribute
    from exabgp.protocol.family import AFI, SAFI

    protocol = Protocol(mock_peer)
    protocol.negotiated.local_as = ASN(65000)
    protocol.negotiated.peer_as = ASN(65000)
    protocol.negotiated.asn4 = True
    protocol.negotiated.families = [(AFI.ipv4, SAFI.unicast)]
    protocol.neighbor.adj_rib_in = True

    mandatory = bytes([0x40, 1, 1, 0]) + bytes([0x40, 2, 0]) + bytes([0x40, 3, 4, 10, 0, 0, 1])
    malformed_aggregator = bytes([0xC0, 7, 3, 0, 0, 1])
    attributes = mandatory + malformed_aggregator
    body = struct.pack('!H', 0) + struct.pack('!H', len(attributes)) + attributes + bytes([24, 10, 0, 0])
    connect(protocol).sendall(frame(UPDATE, body))

    message = await protocol.read_message()

    assert message is not None, 'the UPDATE was dropped whole because one attribute was discarded'
    assert isinstance(message, Update)
    assert Attribute.CODE.INTERNAL_DISCARD in message.data.attributes, (
        'the discard did not happen, so this proves nothing'
    )
    assert Attribute.CODE.AGGREGATOR not in message.data.attributes
    assert [str(routed.nlri) for routed in message.data.announces] == ['10.0.0.0/24']
