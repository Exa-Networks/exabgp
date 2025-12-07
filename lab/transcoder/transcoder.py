from __future__ import annotations


import sys
import json
import string

from typing import Callable, cast

from exabgp.util import hexbytes
from exabgp.util import hexstring

from exabgp.bgp.message import Message
from exabgp.bgp.message import Open
from exabgp.bgp.message import Notification
from exabgp.bgp.message.update import UpdateCollection
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.bgp.message.message_type import MessageType
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.neighbor import Neighbor

from exabgp.version import json as json_version
from exabgp.reactor.api.response import Response, ResponseEncoder

from exabgp.protocol.ip import IPv4


# Dummy negotiated for decoding OPEN/NOTIFICATION (parameter unused but required by API)
_DUMMY_NEGOTIATED: Negotiated | None = None


def _get_dummy_negotiated() -> Negotiated:
    """Get or create a dummy Negotiated instance for decoding OPEN/NOTIFICATION messages."""
    global _DUMMY_NEGOTIATED
    if _DUMMY_NEGOTIATED is None:
        _DUMMY_NEGOTIATED = Negotiated(Neighbor.EMPTY, Direction.IN)
    return _DUMMY_NEGOTIATED


# BGP NOTIFICATION Shutdown Communication constants (RFC 8203)
MAX_SHUTDOWN_COMM_LENGTH = 128  # Maximum length of shutdown communication message


def _make_transcoder_neighbor(local: str, remote: str, local_asn: int, peer_asn: int) -> Neighbor:
    """Create a minimal Neighbor for transcoding JSON responses."""
    neighbor = Neighbor()
    neighbor.session.local_address = IPv4(local)
    neighbor.session.peer_address = IPv4(remote)
    neighbor.session.local_as = ASN(local_asn)
    neighbor.session.peer_as = ASN(peer_asn)
    return neighbor


class Transcoder:
    seen_open: dict[str, Open | None] = {
        'send': None,
        'receive': None,
    }
    negotiated: Negotiated | None = None

    json: ResponseEncoder = Response.JSON(json_version)

    def __init__(self, src: str = 'json', dst: str = 'json') -> None:
        if src != 'json':
            raise RuntimeError('left as an exercise to the reader')

        if dst != 'json':
            raise RuntimeError('left as an exercise to the reader')

        self.convert: Callable[[str], str | None] = self._from_json
        self.encoder: ResponseEncoder = self.json

    def _state(self) -> None:
        self.seen_open['send'] = None
        self.seen_open['receive'] = None
        self.negotiated_in: Negotiated | None = None
        self.negotiated_out: Negotiated | None = None

    def _open(self, direction: str, message: Open) -> None:
        self.seen_open[direction] = message

        if all(self.seen_open.values()):
            self.negotiated_in = Negotiated(Neighbor.EMPTY, Direction.IN)
            self.negotiated_out = Negotiated(Neighbor.EMPTY, Direction.OUT)
            self.negotiated_in.sent(self.seen_open['send'])
            self.negotiated_in.received(self.seen_open['receive'])
            self.negotiated_out.sent(self.seen_open['send'])
            self.negotiated_out.received(self.seen_open['receive'])

    def _from_json(self, json_string: str, direction: str = '') -> str | None:
        try:
            parsed = json.loads(json_string)
        except ValueError:
            sys.stderr.write('invalid JSON message' + '\n')
            sys.exit(1)

        if parsed.get('exabgp', '0.0.0') != json_version:
            sys.stderr.write('invalid json version: ' + json_string + '\n')
            sys.exit(1)

        type_str = parsed.get('type', '')
        if not type_str:
            sys.stderr.write('missing message type: ' + json_string + '\n')
            sys.exit(1)

        try:
            content = MessageType.from_str(type_str)
        except ValueError:
            sys.stderr.write(f'invalid message type "{type_str}": ' + json_string + '\n')
            sys.exit(1)

        neighbor = _make_transcoder_neighbor(
            parsed['neighbor']['address']['local'],
            parsed['neighbor']['address']['peer'],
            parsed['neighbor']['asn']['local'],
            parsed['neighbor']['asn']['peer'],
        )

        if content == MessageType.STATE:
            self._state()
            return json_string

        direction = parsed['neighbor']['direction']
        category = parsed['neighbor']['message']['category']
        header_hex = parsed['neighbor']['message']['header']
        body_hex = parsed['neighbor']['message']['body']
        # Convert hex strings to bytes for encoder methods
        header = bytes.fromhex(header_hex) if header_hex else b''
        body = bytes.fromhex(body_hex) if body_hex else b''
        data = body  # body is already the message data as bytes

        if content == MessageType.OPEN:
            open_msg = Open.unpack_message(data, _get_dummy_negotiated())
            self._open(direction, open_msg)
            return self.encoder.open(neighbor, direction, open_msg, header, body, Negotiated.UNSET)

        if content == MessageType.KEEPALIVE:
            return self.encoder.keepalive(neighbor, direction, header, body, Negotiated.UNSET)

        if content == MessageType.NOTIFICATION:
            notif_msg = Notification.unpack_message(data, _get_dummy_negotiated())

            # Check for CEASE/Administrative Shutdown (code 6, subcode 2) which has special handling
            if (notif_msg.code, notif_msg.subcode) != (6, 2):
                # Use hexbytes for non-printable data (returns bytes, matching Notification.data type)
                notif_msg.data = (
                    data if not len([_ for _ in str(data) if _ not in string.printable]) else hexbytes(data)
                )
                return self.encoder.notification(neighbor, direction, notif_msg, header, body, Negotiated.UNSET)

            if len(data) == 0:
                # shutdown without shutdown communication (the old fashioned way)
                notif_msg.data = b''
                return self.encoder.notification(neighbor, direction, notif_msg, header, body, Negotiated.UNSET)

            # draft-ietf-idr-shutdown or the peer was using 6,2 with data

            shutdown_length = data[0]
            data = data[1:]

            if shutdown_length == 0:
                notif_msg.data = b'empty Shutdown Communication.'
                # move offset past length field
                return self.encoder.notification(neighbor, direction, notif_msg, header, body, Negotiated.UNSET)

            if len(data) < shutdown_length:
                notif_msg.data = (
                    f'invalid Shutdown Communication (buffer underrun) length : {shutdown_length} [{hexstring(data)}]'
                ).encode()
                return self.encoder.notification(neighbor, direction, notif_msg, header, body, Negotiated.UNSET)

            if shutdown_length > MAX_SHUTDOWN_COMM_LENGTH:
                notif_msg.data = (
                    f'invalid Shutdown Communication (too large) length : {shutdown_length} [{hexstring(data)}]'
                ).encode()
                return self.encoder.notification(neighbor, direction, notif_msg, header, body, Negotiated.UNSET)

            try:
                # NOTE: Do not convert to f-string! The chained method calls with multiline
                # formatting is more readable with % formatting.
                notif_msg.data = 'Shutdown Communication: "{}"'.format(
                    data[:shutdown_length]
                    .decode('utf-8')
                    .replace(
                        '\r',
                        ' ',
                    )
                    .replace('\n', ' ')
                ).encode()
            except UnicodeDecodeError:
                notif_msg.data = (
                    f'invalid Shutdown Communication (invalid UTF-8) length : {shutdown_length} [{hexstring(data)}]'
                ).encode()
                return self.encoder.notification(neighbor, direction, notif_msg, header, body, Negotiated.UNSET)

            trailer = data[shutdown_length:]
            if trailer:
                notif_msg.data += (', trailing data: ' + hexstring(trailer)).encode()

            return self.encoder.notification(neighbor, direction, notif_msg, header, body, Negotiated.UNSET)

        if not self.negotiated_in or not self.negotiated_out:
            sys.stderr.write('invalid message sequence, open exchange not complete: ' + json_string + '\n')
            sys.exit(1)

        negotiated = self.negotiated_in if direction == 'receive' else self.negotiated_out
        message = Message.unpack(category, data, negotiated)

        if content == MessageType.UPDATE:
            return self.encoder.update(neighbor, direction, cast(UpdateCollection, message), header, body, negotiated)

        if content == MessageType.EOR:
            # EOR (End of RIB) is encoded as a special UPDATE message
            return self.encoder.update(neighbor, direction, cast(UpdateCollection, message), header, body, negotiated)

        if content == MessageType.REFRESH:
            return self.json.refresh(neighbor, direction, cast(RouteRefresh, message), header, body, negotiated)

        if content == MessageType.OPERATIONAL:
            return self.json.refresh(neighbor, direction, cast(RouteRefresh, message), header, body, negotiated)

        raise RuntimeError('the programer is a monkey and forgot a JSON message type')
