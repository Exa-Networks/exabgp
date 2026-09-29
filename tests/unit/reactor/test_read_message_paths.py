"""The paths of Protocol.read_message which the existing tests do not reach.

The tests which call read_message (the RFC 4271 header tests, flow validation, OTC, the
peer loop) were measured with branch coverage on 2026-09-29.  They never ran a header
error with an API process asking for parsed messages or for raw packets rather than
consolidated ones, nor a decoder raising something other than Notify.  Nor did any of them
say in which order the API is told, the statistics counted and the errors raised.  These
tests pin all of it before the method is split into helpers
(plan-large-function-decomposition): what is returned, what is raised with which code,
subcode, text and data, what the API processes are handed, and what is logged.

The connection is a stand-in whose reader_async hands back one message already framed,
the way Connection.reader_async does, so no socket is involved.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from exabgp.bgp.message import KeepAlive, Message, NotificationReceived, Notify
from exabgp.bgp.message.update.collection import UpdateCollection
from exabgp.bgp.neighbor import Neighbor
from exabgp.configuration.check import _negotiated
from exabgp.configuration.configuration import Configuration
from exabgp.reactor import protocol as protocol_module
from exabgp.reactor.network.error import NotifyError
from exabgp.reactor.peer.peer import Peer
from exabgp.reactor.protocol import Protocol
from exabgp.rib import RIB

CONFIGURATION = """
neighbor 192.0.2.1 {
    router-id 192.0.2.2;
    local-address 192.0.2.2;
    local-as 65001;
    peer-as 65001;
    family { ipv4 unicast; }
}
"""

MARKER = b'\xff' * 16
KEEPALIVE_HEADER = MARKER + b'\x00\x13\x04'
NOTIFICATION_BODY = b'\x06\x02'
NOTIFICATION_HEADER = MARKER + b'\x00\x15\x03'
# an UPDATE with no withdrawal, no attribute and no NLRI: the End-of-RIB of IPv4 unicast
EOR_BODY = b'\x00\x00\x00\x00'
EOR_HEADER = MARKER + b'\x00\x17\x02'

LOGGED: list[tuple[str, str]] = []

API_OFF = {'receive-packets': False, 'receive-consolidate': False, 'receive-parsed': False}


@pytest.fixture(autouse=True)
def isolated_ribs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(RIB, '_cache', {})


def neighbour() -> Neighbor:
    configuration = Configuration([CONFIGURATION], text=True)
    assert configuration.reload(), str(configuration.error)
    return next(iter(configuration.neighbors.values()))


def protocol(**api: bool) -> tuple[Protocol, Mock]:
    """A Protocol whose API settings are the ones given, and the reactor it reports to."""
    neighbor = neighbour()
    neighbor.api.update(API_OFF)
    neighbor.api.update({key.replace('_', '-'): value for key, value in api.items()})
    reactor = Mock()
    proto = Protocol(Peer(neighbor, reactor))
    proto.negotiated, _ = _negotiated(neighbor)
    return proto, reactor


async def read(
    proto: Protocol, length: int, msg_id: int, header: bytes, body: bytes, notify: NotifyError | None = None
) -> tuple[Message | None, list[tuple[str, str]]]:
    """Read one message from a stand-in connection, return it and the debug lines logged."""
    proto.connection = Mock(
        reader_async=AsyncMock(return_value=(length, msg_id, header, body, notify)),
        session=Mock(return_value='session'),
    )
    LOGGED.clear()
    with patch.object(protocol_module, 'log') as log:
        try:
            message = await proto.read_message()
        finally:
            LOGGED.extend((call.args[0](), call.args[1]) for call in log.debug.call_args_list)
    return message, list(LOGGED)


def last_logged() -> list[tuple[str, str]]:
    """The debug lines logged by the last read, even when it raised."""
    return list(LOGGED)


def calls(reactor: Mock) -> list[tuple[Any, ...]]:
    """What the API processes were handed, in order, as (method, arguments)."""
    return [(name, *args) for name, args, _ in reactor.processes.mock_calls]


def header_error() -> NotifyError:
    return NotifyError(1, 2, 'bad length 5', data=b'\x00\x05')


class TestHeaderError:
    """The connection found the header malformed: the peer is told, the API may be too."""

    async def _raised(self, proto: Protocol) -> Notify:
        with pytest.raises(Notify) as raised:
            await read(proto, 5, 0, b'H', b'B', header_error())
        return raised.value

    @pytest.mark.asyncio
    async def test_the_notify_carries_the_code_subcode_text_and_data(self) -> None:
        proto, reactor = protocol()
        notify = await self._raised(proto)
        assert (notify.code, notify.subcode, notify.data) == (1, 2, b'\x00\x05')
        assert str(notify) == Notify(1, 2, 'bad length 5', data=b'\x00\x05').__str__()
        assert calls(reactor) == []
        assert last_logged() == []
        assert {key: value for key, value in proto.peer.stats.items() if key.startswith('receive-') and value} == {}

    @pytest.mark.asyncio
    async def test_without_data_the_text_is_the_data(self) -> None:
        # empty data is handed to Notify as None, and Notify then sends its text instead
        proto, _ = protocol()
        with pytest.raises(Notify) as raised:
            await read(proto, 5, 0, b'H', b'B', NotifyError(1, 1, 'marker'))
        assert (raised.value.code, raised.value.subcode, raised.value.data) == (1, 1, b'marker')

    @pytest.mark.asyncio
    async def test_notification_not_asked_for_tells_nobody(self) -> None:
        proto, reactor = protocol(receive_consolidate=True, receive_parsed=True, receive_packets=True)
        await self._raised(proto)
        assert calls(reactor) == []

    @pytest.mark.asyncio
    async def test_consolidate_is_given_header_and_body(self) -> None:
        proto, reactor = protocol(
            receive_notification=True, receive_consolidate=True, receive_parsed=True, receive_packets=True
        )
        notify = await self._raised(proto)
        assert calls(reactor) == [
            ('notification', proto.peer.neighbor, 'receive', notify.notification, b'H', b'B', proto.negotiated)
        ]

    @pytest.mark.asyncio
    async def test_parsed_is_given_no_bytes(self) -> None:
        proto, reactor = protocol(receive_notification=True, receive_parsed=True, receive_packets=True)
        notify = await self._raised(proto)
        assert calls(reactor) == [
            ('notification', proto.peer.neighbor, 'receive', notify.notification, b'', b'', proto.negotiated)
        ]

    @pytest.mark.asyncio
    async def test_packets_is_given_the_raw_message_with_its_type(self) -> None:
        proto, reactor = protocol(receive_notification=True, receive_packets=True)
        await self._raised(proto)
        assert calls(reactor) == [('packets', proto.peer.neighbor, 'receive', 0, b'H', b'B', proto.negotiated)]

    @pytest.mark.asyncio
    async def test_notification_asked_for_without_a_format_tells_nobody(self) -> None:
        proto, reactor = protocol(receive_notification=True)
        await self._raised(proto)
        assert calls(reactor) == []

    @pytest.mark.asyncio
    async def test_header_error_wins_over_an_unknown_type(self) -> None:
        proto, _ = protocol()
        with pytest.raises(Notify) as raised:
            await read(proto, 0, 200, b'', b'', header_error())
        assert (raised.value.code, raised.value.subcode) == (1, 2)


class TestTypeAndLength:
    @pytest.mark.asyncio
    async def test_an_unknown_type_is_bad_message_type_with_the_octet(self) -> None:
        proto, reactor = protocol(receive_packets=True)
        with pytest.raises(Notify) as raised:
            await read(proto, 19, 200, MARKER + b'\x00\x13\xc8', b'')
        assert (raised.value.code, raised.value.subcode, raised.value.data) == (1, 3, b'\xc8')
        assert str(raised.value) == str(Notify(1, 3, 'type 200', data=b'\xc8'))
        assert calls(reactor) == []
        assert last_logged() == []

    @pytest.mark.asyncio
    async def test_an_unknown_type_is_refused_even_without_length(self) -> None:
        proto, _ = protocol()
        with pytest.raises(Notify) as raised:
            await read(proto, 0, 200, b'', b'')
        assert (raised.value.code, raised.value.subcode) == (1, 3)

    @pytest.mark.asyncio
    async def test_no_length_is_nothing_to_process(self) -> None:
        proto, reactor = protocol(receive_keepalive=True, receive_packets=True)
        message, logged = await read(proto, 0, Message.CODE.KEEPALIVE, b'', b'')
        assert message is None
        assert logged == []
        assert calls(reactor) == []
        assert proto.peer.stats['receive-keepalive'] == 0


class TestDecoded:
    @pytest.mark.asyncio
    async def test_a_keepalive_is_counted_logged_and_returned(self) -> None:
        proto, reactor = protocol()
        before = proto.peer.stats['receive-keepalive']
        message, logged = await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        assert isinstance(message, KeepAlive)
        assert proto.peer.stats['receive-keepalive'] == before + 1
        assert logged == [('message.received type=KEEPALIVE', 'session')]
        assert calls(reactor) == []

    @pytest.mark.asyncio
    async def test_packets_are_told_before_the_message_is_decoded(self) -> None:
        proto, reactor = protocol(receive_keepalive=True, receive_packets=True)
        order: list[str] = []
        reactor.processes.packets.side_effect = lambda *_: order.append('packets')
        real = Message.unpack

        def unpack(*args: Any) -> Message:
            order.append('unpack')
            return real(*args)

        with patch.object(Message, 'unpack', unpack):
            message, _ = await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        assert isinstance(message, KeepAlive)
        assert order == ['packets', 'unpack']
        assert calls(reactor) == [
            ('packets', proto.peer.neighbor, 'receive', Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'', proto.negotiated)
        ]

    @pytest.mark.asyncio
    async def test_consolidate_is_told_the_decoded_message_not_the_packets(self) -> None:
        proto, reactor = protocol(receive_keepalive=True, receive_packets=True, receive_consolidate=True)
        message, _ = await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        assert calls(reactor) == [
            ('message', Message.CODE.KEEPALIVE, proto.peer, 'receive', message, KEEPALIVE_HEADER, b'', proto.negotiated)
        ]

    @pytest.mark.asyncio
    async def test_parsed_is_told_without_bytes(self) -> None:
        proto, reactor = protocol(receive_keepalive=True, receive_parsed=True)
        message, _ = await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        assert calls(reactor) == [
            ('message', Message.CODE.KEEPALIVE, proto.peer, 'receive', message, b'', b'', proto.negotiated)
        ]

    @pytest.mark.asyncio
    async def test_the_api_entries_are_lists_of_processes(self) -> None:
        # the configuration files the names of the processes which asked, not a flag
        proto, reactor = protocol()
        proto.neighbor.api.update({'receive-keepalive': ['watcher'], 'receive-packets': ['watcher']})
        proto.neighbor.api['receive-consolidate'] = []
        await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        assert [call[0] for call in calls(reactor)] == ['packets']

    @pytest.mark.asyncio
    async def test_packets_of_a_type_not_asked_for_are_not_told(self) -> None:
        proto, reactor = protocol(receive_packets=True, receive_update=True)
        await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        assert calls(reactor) == []

    @pytest.mark.asyncio
    async def test_an_update_is_classified_and_its_flows_revalidated(self) -> None:
        proto, reactor = protocol(receive_update=True, receive_parsed=True)
        order: list[str] = []
        revalidated: list[Any] = []

        def validate(neighbor: Neighbor, collection: Any) -> list[Any]:
            order.append('validate')
            assert neighbor is proto.neighbor
            return revalidated

        told = Mock(side_effect=lambda *_: order.append('told'))
        with (
            patch.object(protocol_module, 'validate_flows', validate),
            patch.object(proto, '_tell_api_received', told),
        ):
            message, logged = await read(proto, 23, Message.CODE.UPDATE, EOR_HEADER, EOR_BODY)
        assert message is not None and message.ID == Message.CODE.UPDATE
        assert order == ['validate', 'told']
        assert told.call_args.args == (message, EOR_HEADER, EOR_BODY, revalidated)
        assert told.call_args.args[3] is revalidated
        assert logged == [('message.received type=UPDATE', 'session')]
        assert proto.peer.stats['receive-update'] == 1

    @pytest.mark.asyncio
    async def test_an_update_not_asked_for_is_still_revalidated(self) -> None:
        proto, reactor = protocol()
        validate = Mock(return_value=[])
        told = Mock()
        with (
            patch.object(protocol_module, 'validate_flows', validate),
            patch.object(proto, '_tell_api_received', told),
        ):
            await read(proto, 23, Message.CODE.UPDATE, EOR_HEADER, EOR_BODY)
        validate.assert_called_once()
        told.assert_not_called()

    @pytest.mark.asyncio
    async def test_the_otc_classification_runs_before_validation(self) -> None:
        proto, _ = protocol()
        order: list[Any] = []

        def classify(collection: UpdateCollection, negotiated: Any) -> None:
            order.append(('classify', negotiated))

        with (
            patch.object(UpdateCollection, 'classify_otc', classify),
            patch.object(protocol_module, 'validate_flows', lambda *_: order.append('validate') or []),
        ):
            await read(proto, 23, Message.CODE.UPDATE, EOR_HEADER, EOR_BODY)
        assert order == [('classify', proto.negotiated), 'validate']

    @pytest.mark.asyncio
    async def test_a_keepalive_is_not_revalidated(self) -> None:
        proto, _ = protocol()
        validate = Mock(return_value=[])
        with patch.object(protocol_module, 'validate_flows', validate):
            await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        validate.assert_not_called()


class TestNotificationReceived:
    @pytest.mark.asyncio
    async def test_the_api_is_told_then_it_is_raised(self) -> None:
        proto, reactor = protocol(receive_notification=True, receive_parsed=True)
        with pytest.raises(NotificationReceived) as raised:
            await read(proto, 21, Message.CODE.NOTIFICATION, NOTIFICATION_HEADER, NOTIFICATION_BODY)
        assert (raised.value.code, raised.value.subcode) == (6, 2)
        ((name, message_id, peer, direction, message, header, body, negotiated),) = calls(reactor)
        assert (name, message_id, peer, direction, header, body) == (
            'message',
            Message.CODE.NOTIFICATION,
            proto.peer,
            'receive',
            b'',
            b'',
        )
        assert (message.code, message.subcode) == (6, 2)
        assert proto.peer.stats['receive-notification'] == 1
        assert last_logged() == [('message.received type=NOTIFICATION', 'session')]


class TestDecoderFailure:
    @pytest.mark.asyncio
    async def test_a_python_exception_becomes_a_generic_header_error(self) -> None:
        proto, reactor = protocol(receive_keepalive=True, receive_packets=True)
        failure = ValueError('broken decoder')
        with patch.object(Message, 'unpack', Mock(side_effect=failure)):
            with pytest.raises(Notify) as raised:
                await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        notify = raised.value
        assert (notify.code, notify.subcode) == (1, 0)
        assert str(notify) == str(Notify(1, 0, 'can not decode update message of type "4"'))
        assert notify.__cause__ is None
        assert notify.__suppress_context__ is True
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
        assert [call[0] for call in calls(reactor)] == ['packets']
        assert proto.peer.stats['receive-keepalive'] == 1

    @pytest.mark.asyncio
    async def test_a_notify_from_the_decoder_is_raised_as_it_is(self) -> None:
        proto, _ = protocol()
        failure = Notify(3, 1, 'malformed attribute list')
        with patch.object(Message, 'unpack', Mock(side_effect=failure)):
            with pytest.raises(Notify) as raised:
                await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        assert raised.value is failure
        assert len(last_logged()) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize('failure', [KeyboardInterrupt(), SystemExit(3)])
    async def test_an_interrupt_is_not_converted(self, failure: BaseException) -> None:
        proto, _ = protocol()
        with patch.object(Message, 'unpack', Mock(side_effect=failure)):
            with pytest.raises(type(failure)) as raised:
                await read(proto, 19, Message.CODE.KEEPALIVE, KEEPALIVE_HEADER, b'')
        assert raised.value is failure
