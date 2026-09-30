"""The paths of Protocol.read_message which the existing tests do not reach.

The tests which call read_message (the RFC 4271 header tests, flow validation, OTC, the
peer loop) were measured with branch coverage on 2026-09-29.  They never ran a header
error with an API process asking for parsed messages or for raw packets rather than
consolidated ones, nor a decoder raising something other than Notify.  Nor did any of them
say in which order the API is told, the statistics counted and the errors raised.  These
tests pin all of it before the method is split into helpers
(plan-large-function-decomposition): what is returned, what is raised with which code,
subcode, text and data, what the API processes are handed, and what is logged.

The message is written to one end of a socket pair and read by the real connection at the
other, the Peer and its Reactor are real, and what the API processes are handed is what
their encoder is asked to print (`negotiation.Told`).  Compiled (plan/wip-mypyc.md), none of
them can be a stand-in.  A decoder is replaced where the reactor looks it up, in
`Message.registered_message`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import Mock, patch

import pytest

from exabgp.bgp.message import KeepAlive, Message, NotificationReceived, Notify, Update
from exabgp.bgp.message.open.capability.role import RoleValue
from exabgp.bgp.message.update.attribute import Attribute, AttributeCollection
from exabgp.bgp.message.update.collection import RoutedNLRI, UpdateCollection
from exabgp.bgp.message.update.nlri.flow import Flow, Flow4Destination
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.protocol.family import AFI, SAFI
from exabgp.reactor import protocol as protocol_module
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB
from exabgp.rib.route import Route
from tests import negotiation

COMPILED = not protocol_module.__file__.endswith('.py')

CONFIGURATION = """
neighbor 192.0.2.1 {
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65001;
    family { ipv4 unicast; }
}
"""

FLOW_CONFIGURATION = """
neighbor 192.0.2.1 {
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65001;
    flow-validation enable;
    family { ipv4 unicast; ipv4 flow; }
}
"""

IPV4_FLOW = (AFI.ipv4, SAFI.flow_ip)
FLOW = 'flow destination-ipv4 10.0.0.0/24'

MARKER = b'\xff' * 16
KEEPALIVE_HEADER = MARKER + b'\x00\x13\x04'
NOTIFICATION_BODY = b'\x06\x02'
NOTIFICATION_HEADER = MARKER + b'\x00\x15\x03'
# an UPDATE with no withdrawal, no attribute and no NLRI: the End-of-RIB of IPv4 unicast
EOR_BODY = b'\x00\x00\x00\x00'
EOR_HEADER = MARKER + b'\x00\x17\x02'
# a KEEPALIVE header whose Length field says 5: the connection refuses it, RFC 4271 6.1
BAD_LENGTH_HEADER = MARKER + b'\x00\x05\x04'
BAD_LENGTH_REPORT = 'KEEPALIVE has an invalid message length of 5'
# a header whose marker is not all ones
BAD_MARKER_REPORT = 'The packet received does not contain a BGP marker'
# the type the connection reports with a header it refused: it read no type
UNREAD = 0

LOGGED: list[tuple[str, str]] = []


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour(configuration: str = CONFIGURATION) -> Neighbor:
    parsed = Configuration([configuration], text=True)
    assert parsed.reload(), str(parsed.error)
    return next(iter(parsed.neighbors.values()))


def protocol(configuration: str = CONFIGURATION, **api: bool) -> tuple[Protocol, negotiation.Told]:
    """A Protocol whose API asks for what is given, and what the API processes are handed.

    The process also asks for neighbor-changes, which is where Processes.notification looks
    for who to tell of a NOTIFICATION answering a malformed header: read_message decides
    whether to tell by `receive-notification`, and does not look at neighbor-changes.
    """
    neighbor = neighbour(configuration)
    asked = [key.replace('_', '-') for key, value in api.items() if value]
    negotiation.api_asks(neighbor, 'neighbor-changes', *asked)
    proto, told = negotiation.protocol(neighbor)
    proto.negotiated, _ = _negotiated(neighbor)
    return proto, told


async def read(proto: Protocol, wire: bytes) -> tuple[Message | None, list[tuple[str, str]]]:
    """Have the peer send `wire`, read one message, return it and the debug lines logged.

    The session of each debug line is given as 'session'.
    """
    theirs = negotiation.connect(proto)
    assert proto.connection is not None
    session = proto.connection.session()
    theirs.sendall(wire)
    LOGGED.clear()
    try:
        with patch.object(protocol_module, 'log') as log:
            try:
                message = await proto.read_message()
            finally:
                LOGGED.extend(
                    (call.args[0](), 'session' if call.args[1] == session else call.args[1])
                    for call in log.debug.call_args_list
                )
    finally:
        negotiation.disconnect(proto, theirs)
    return message, list(LOGGED)


def last_logged() -> list[tuple[str, str]]:
    """The debug lines logged by the last read, even when it raised."""
    return list(LOGGED)


def calls(told: negotiation.Told) -> list[tuple[Any, ...]]:
    """What the API processes were handed, in order, as (encoder method, arguments)."""
    return [(name, *args) for name, args in told.calls if name != 'unpack']


def decoder(unpack: Callable[[Any, Any], Message]) -> type:
    """A KEEPALIVE decoder calling `unpack`, to put in Message.registered_message.

    The header check reads the length bounds of the registered class, so it has KeepAlive's.
    """
    return type(
        'Decoder',
        (),
        {
            'ID': KeepAlive.ID,
            'HEADER_CHECKS_LENGTH': KeepAlive.HEADER_CHECKS_LENGTH,
            'LENGTH_MIN': KeepAlive.LENGTH_MIN,
            'LENGTH_MAX': KeepAlive.LENGTH_MAX,
            'unpack_message': staticmethod(unpack),
        },
    )


def failing(failure: BaseException) -> Any:
    """The KEEPALIVE decoder replaced by one raising `failure`."""

    def unpack(data: Any, negotiated: Any) -> Message:
        raise failure

    return patch.dict(Message.registered_message, {KeepAlive.ID.value: decoder(unpack)})


class TestHeaderError:
    """The connection found the header malformed: the peer is told, the API may be too."""

    async def _raised(self, proto: Protocol) -> Notify:
        with pytest.raises(Notify) as raised:
            await read(proto, BAD_LENGTH_HEADER)
        return raised.value

    @pytest.mark.asyncio
    async def test_the_notify_carries_the_code_subcode_text_and_data(self) -> None:
        proto, told = protocol()
        notify = await self._raised(proto)
        assert (notify.code, notify.subcode, notify.data) == (1, 2, b'\x00\x05')
        assert str(notify) == Notify(1, 2, BAD_LENGTH_REPORT, data=b'\x00\x05').__str__()
        assert calls(told) == []
        assert last_logged() == []
        assert {key: value for key, value in proto.peer.stats.items() if key.startswith('receive-') and value} == {}

    @pytest.mark.asyncio
    async def test_without_data_the_text_is_the_data(self) -> None:
        # empty data is handed to Notify as None, and Notify then sends its text instead
        proto, _ = protocol()
        with pytest.raises(Notify) as raised:
            await read(proto, b'\x00' * 16 + b'\x00\x13\x04')
        assert (raised.value.code, raised.value.subcode, raised.value.data) == (1, 1, BAD_MARKER_REPORT.encode())

    @pytest.mark.asyncio
    async def test_notification_not_asked_for_tells_nobody(self) -> None:
        proto, told = protocol(receive_consolidate=True, receive_parsed=True, receive_packets=True)
        await self._raised(proto)
        assert calls(told) == []

    @pytest.mark.asyncio
    async def test_consolidate_is_given_header_and_body(self) -> None:
        proto, told = protocol(
            receive_notification=True, receive_consolidate=True, receive_parsed=True, receive_packets=True
        )
        notify = await self._raised(proto)
        assert calls(told) == [
            (
                'notification',
                proto.peer.neighbor,
                'receive',
                notify.notification,
                BAD_LENGTH_HEADER,
                b'',
                proto.negotiated,
            )
        ]

    @pytest.mark.asyncio
    async def test_parsed_is_given_no_bytes(self) -> None:
        proto, told = protocol(receive_notification=True, receive_parsed=True, receive_packets=True)
        notify = await self._raised(proto)
        assert calls(told) == [
            ('notification', proto.peer.neighbor, 'receive', notify.notification, b'', b'', proto.negotiated)
        ]

    @pytest.mark.asyncio
    async def test_packets_is_given_the_raw_message_with_its_type(self) -> None:
        proto, told = protocol(receive_notification=True, receive_packets=True)
        await self._raised(proto)
        assert calls(told) == [
            ('packets', proto.peer.neighbor, 'receive', UNREAD, BAD_LENGTH_HEADER, b'', proto.negotiated)
        ]

    @pytest.mark.asyncio
    async def test_notification_asked_for_without_a_format_tells_nobody(self) -> None:
        proto, told = protocol(receive_notification=True)
        await self._raised(proto)
        assert calls(told) == []

    @pytest.mark.asyncio
    async def test_header_error_wins_over_an_unknown_type(self) -> None:
        proto, _ = protocol()
        with pytest.raises(Notify) as raised:
            await read(proto, MARKER + b'\x00\x05\xc8')
        assert (raised.value.code, raised.value.subcode) == (1, 2)


class TestTypeAndLength:
    @pytest.mark.asyncio
    async def test_an_unknown_type_is_bad_message_type_with_the_octet(self) -> None:
        proto, told = protocol(receive_packets=True)
        with pytest.raises(Notify) as raised:
            await read(proto, MARKER + b'\x00\x13\xc8')
        assert (raised.value.code, raised.value.subcode, raised.value.data) == (1, 3, b'\xc8')
        assert str(raised.value) == str(Notify(1, 3, 'type 200', data=b'\xc8'))
        assert calls(told) == []
        assert last_logged() == []


# A connection never reports a length of zero without an error: only a stand-in reaches the
# two paths below, and compiled a Protocol refuses a stand-in for its connection
STAND_IN_ONLY = pytest.mark.skipif(
    COMPILED, reason='compiled, the connection must be a real one, and no real one returns a zero length without error'
)


async def read_from_stand_in(proto: Protocol, msg_id: int) -> Message | None:
    """What read_message does when the connection says it read nothing, and no error."""
    from unittest.mock import AsyncMock

    proto.connection = Mock(
        reader_async=AsyncMock(return_value=(0, Message.CODE.of(msg_id), b'', b'', None)),
        session=Mock(return_value='session'),
    )
    return await proto.read_message()


class TestNoLength:
    @STAND_IN_ONLY
    @pytest.mark.asyncio
    async def test_an_unknown_type_is_refused_even_without_length(self) -> None:
        proto, _ = protocol()
        with pytest.raises(Notify) as raised:
            await read_from_stand_in(proto, 200)
        assert (raised.value.code, raised.value.subcode) == (1, 3)

    @STAND_IN_ONLY
    @pytest.mark.asyncio
    async def test_no_length_is_nothing_to_process(self) -> None:
        proto, told = protocol(receive_keepalive=True, receive_packets=True)
        with patch.object(protocol_module, 'log') as log:
            message = await read_from_stand_in(proto, Message.CODE.KEEPALIVE.value)
        assert message is None
        assert log.debug.call_args_list == []
        assert calls(told) == []
        assert proto.peer.stats['receive-keepalive'] == 0


def flow_update(neighbor: Neighbor, route: Route) -> bytes:
    """The UPDATE a peer on this iBGP session would send for one route."""
    _, negotiated = _negotiated(neighbor)
    collection = UpdateCollection([RoutedNLRI(route.nlri, route.nexthop)], [], route.attributes)
    return next(collection.messages(negotiated))


def flow_route() -> Route:
    flow = Flow.make_flow(AFI.ipv4, SAFI.flow_ip)
    flow.add(Flow4Destination.make_prefix4(bytes([10, 0, 0, 0]), 24))
    return Route(flow, AttributeCollection())


def unicast_route() -> Route:
    configuration = Configuration([''], text=True)
    assert configuration.partial('static', 'route 10.0.0.0/16 next-hop 192.0.2.1', 'announce'), str(configuration.error)
    (route,) = configuration.pop_routes()
    return route


def flows(collection: UpdateCollection) -> list[str]:
    return [str(routed.nlri) for routed in collection.announces if routed.nlri.family().afi_safi() == IPV4_FLOW]


class TestDecoded:
    @pytest.mark.asyncio
    async def test_a_keepalive_is_counted_logged_and_returned(self) -> None:
        proto, told = protocol()
        before = proto.peer.stats['receive-keepalive']
        message, logged = await read(proto, KEEPALIVE_HEADER)
        assert isinstance(message, KeepAlive)
        assert proto.peer.stats['receive-keepalive'] == before + 1
        assert logged == [('message.received type=KEEPALIVE', 'session')]
        assert calls(told) == []

    @pytest.mark.asyncio
    async def test_packets_are_told_before_the_message_is_decoded(self) -> None:
        proto, told = protocol(receive_keepalive=True, receive_packets=True)

        def unpack(data: Any, negotiated: Any) -> Message:
            told.calls.append(('unpack', ()))
            return KeepAlive.unpack_message(data, negotiated)

        with patch.dict(Message.registered_message, {KeepAlive.ID.value: decoder(unpack)}):
            message, _ = await read(proto, KEEPALIVE_HEADER)
        assert isinstance(message, KeepAlive)
        assert told.names() == ['packets', 'unpack']
        assert calls(told) == [
            ('packets', proto.peer.neighbor, 'receive', Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'', proto.negotiated)
        ]

    @pytest.mark.asyncio
    async def test_consolidate_is_told_the_decoded_message_not_the_packets(self) -> None:
        proto, told = protocol(receive_keepalive=True, receive_packets=True, receive_consolidate=True)
        await read(proto, KEEPALIVE_HEADER)
        # Processes.message hands a KEEPALIVE to the encoder with its bytes, not the object
        assert calls(told) == [('keepalive', proto.peer.neighbor, 'receive', KEEPALIVE_HEADER, b'', proto.negotiated)]

    @pytest.mark.asyncio
    async def test_parsed_is_told_without_bytes(self) -> None:
        proto, told = protocol(receive_keepalive=True, receive_parsed=True)
        await read(proto, KEEPALIVE_HEADER)
        assert calls(told) == [('keepalive', proto.peer.neighbor, 'receive', b'', b'', proto.negotiated)]

    @pytest.mark.asyncio
    async def test_the_api_entries_are_lists_of_processes(self) -> None:
        # the configuration files the names of the processes which asked, not a flag
        proto, told = protocol()
        proto.neighbor.api.update(
            {'receive-keepalive': [negotiation.PROCESS], 'receive-packets': [negotiation.PROCESS]}
        )
        proto.neighbor.api['receive-consolidate'] = []
        await read(proto, KEEPALIVE_HEADER)
        assert [call[0] for call in calls(told)] == ['packets']

    @pytest.mark.asyncio
    async def test_packets_of_a_type_not_asked_for_are_not_told(self) -> None:
        proto, told = protocol(receive_packets=True, receive_update=True)
        await read(proto, KEEPALIVE_HEADER)
        assert calls(told) == []

    @pytest.mark.asyncio
    async def test_an_update_is_classified_and_its_flows_revalidated(self) -> None:
        """The flows an UPDATE made feasible are told after it, and the infeasible ones withheld."""
        proto, told = protocol(FLOW_CONFIGURATION, receive_update=True, receive_parsed=True)
        held, _ = await read(proto, flow_update(proto.neighbor, flow_route()))
        assert isinstance(held, Update)
        assert flows(held.data) == [], 'the infeasible flow was not withheld'

        message, logged = await read(proto, flow_update(proto.neighbor, unicast_route()))
        assert isinstance(message, Update)
        told_updates = [args[2] for args in told.called('update')]
        # the flow UPDATE, withheld; the unicast UPDATE; the flow it made feasible
        assert [flows(collection) for collection in told_updates] == [[], [], [FLOW]]
        assert told_updates[1] is message.data
        assert logged == [('message.received type=UPDATE', 'session')]
        assert proto.peer.stats['receive-update'] == 2

    @pytest.mark.asyncio
    async def test_an_update_not_asked_for_is_still_revalidated(self) -> None:
        proto, told = protocol(FLOW_CONFIGURATION)
        await read(proto, flow_update(proto.neighbor, flow_route()))
        assert list(proto.neighbor.rib.incoming.cached_routes([IPV4_FLOW])) == []

        await read(proto, flow_update(proto.neighbor, unicast_route()))

        assert [str(route.nlri) for route in proto.neighbor.rib.incoming.cached_routes([IPV4_FLOW])] == [FLOW]
        assert calls(told) == []

    @pytest.mark.asyncio
    async def test_the_otc_classification_runs_before_the_api_is_told(self) -> None:
        """RFC 9234 5: an UPDATE from a provider without OTC is told with the OTC it was given."""
        proto, told = protocol(receive_update=True, receive_parsed=True)
        proto.negotiated.role = RoleValue.CUSTOMER
        proto.negotiated.peer_role = RoleValue.PROVIDER
        message, _ = await read(proto, flow_update(proto.neighbor, unicast_route()))
        assert isinstance(message, Update)
        ((_, _, collection, *_),) = told.called('update')
        assert collection.attributes.get(Attribute.CODE.OTC) is not None

    @pytest.mark.asyncio
    async def test_a_keepalive_is_not_revalidated(self) -> None:
        proto, _ = protocol(FLOW_CONFIGURATION)
        await read(proto, flow_update(proto.neighbor, flow_route()))
        await read(proto, KEEPALIVE_HEADER)
        assert [str(route.nlri) for route in proto.neighbor.rib.incoming.pending_flows(IPV4_FLOW)] == [FLOW]
        assert list(proto.neighbor.rib.incoming.cached_routes([IPV4_FLOW])) == []


class TestNotificationReceived:
    @pytest.mark.asyncio
    async def test_the_api_is_told_then_it_is_raised(self) -> None:
        proto, told = protocol(receive_notification=True, receive_parsed=True)
        with pytest.raises(NotificationReceived) as raised:
            await read(proto, NOTIFICATION_HEADER + NOTIFICATION_BODY)
        assert (raised.value.code, raised.value.subcode) == (6, 2)
        ((name, neighbor, direction, message, header, body, negotiated),) = calls(told)
        assert (name, neighbor, direction, header, body, negotiated) == (
            'notification',
            proto.peer.neighbor,
            'receive',
            b'',
            b'',
            proto.negotiated,
        )
        assert (message.code, message.subcode) == (6, 2)
        assert proto.peer.stats['receive-notification'] == 1
        assert last_logged() == [('message.received type=NOTIFICATION', 'session')]


class TestDecoderFailure:
    @pytest.mark.asyncio
    async def test_a_python_exception_becomes_a_generic_header_error(self) -> None:
        proto, told = protocol(receive_keepalive=True, receive_packets=True)
        with failing(ValueError('broken decoder')):
            with pytest.raises(Notify) as raised:
                await read(proto, KEEPALIVE_HEADER)
        notify = raised.value
        assert (notify.code, notify.subcode) == (1, 0)
        assert str(notify) == str(Notify(1, 0, 'can not decode update message of type "4"'))
        assert notify.__cause__ is None
        logged = last_logged()
        assert [text.split(' ')[0] for text, _ in logged] == [
            'message.received',
            'message.decode.failed',
            'message.decode.error',
            'message.decode.traceback',
        ]
        # the type is logged by name, the Notify text has it as a number
        assert logged[1] == ('message.decode.failed type=KEEPALIVE', 'session')
        assert logged[2] == ('message.decode.error error=broken decoder', 'session')
        assert 'ValueError: broken decoder' in logged[3][0]
        assert {session for _, session in logged} == {'session'}
        # the packets were told before the decoder ran, and nothing after
        assert [call[0] for call in calls(told)] == ['packets']
        assert proto.peer.stats['receive-keepalive'] == 1

    @pytest.mark.skipif(COMPILED, reason='compiled, mypyc does not set __suppress_context__ for raise ... from None')
    @pytest.mark.asyncio
    async def test_the_python_exception_is_not_chained_to_the_header_error(self) -> None:
        proto, _ = protocol()
        with failing(ValueError('broken decoder')):
            with pytest.raises(Notify) as raised:
                await read(proto, KEEPALIVE_HEADER)
        assert raised.value.__suppress_context__ is True

    @pytest.mark.asyncio
    async def test_a_notify_from_the_decoder_is_raised_as_it_is(self) -> None:
        proto, _ = protocol()
        failure = Notify(3, 1, 'malformed attribute list')
        with failing(failure):
            with pytest.raises(Notify) as raised:
                await read(proto, KEEPALIVE_HEADER)
        assert raised.value is failure
        assert len(last_logged()) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize('failure', [KeyboardInterrupt(), SystemExit(3)])
    async def test_an_interrupt_is_not_converted(self, failure: BaseException) -> None:
        proto, _ = protocol()
        with failing(failure):
            with pytest.raises(type(failure)) as raised:
                await read(proto, KEEPALIVE_HEADER)
        assert raised.value is failure
