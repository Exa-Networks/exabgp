from __future__ import annotations


import sys
import json
import string

from typing import Callable, Dict, cast

from exabgp.util import hexbytes
from exabgp.util import hexstring

from exabgp.bgp.message import Message
from exabgp.bgp.message import Open
from exabgp.bgp.message import Notification
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.neighbor import Neighbor

from exabgp.version import json as json_version
from exabgp.reactor.api.response import Response

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


class _FakeNeighbor(dict):
    def __init__(self, local: str, remote: str, asn: int, peer: int) -> None:
        self['local-address'] = IPv4(local)
        self['peer_address'] = IPv4(remote)
        self['peer-as'] = ASN(asn)
        self['local-as'] = ASN(peer)
        self['capability'] = {
            'asn4': True,
        }


class Transcoder:
    seen_open: Dict[str, Open | None] = {
        'send': None,
        'receive': None,
    }
    negotiated: Negotiated | None = None

    json: Response.JSON = Response.JSON(json_version)

    def __init__(self, src: str = 'json', dst: str = 'json') -> None:
        if src != 'json':
            raise RuntimeError('left as an exercise to the reader')

        if dst != 'json':
            raise RuntimeError('left as an exercise to the reader')

        self.convert: Callable[[str], str | None] = self._from_json
        self.encoder: Response.JSON = self.json

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

        content = parsed.get('type', '')

        if not content:
            sys.stderr.write('invalid json content: ' + json_string + '\n')
            sys.exit(1)

        neighbor = _FakeNeighbor(
            parsed['neighbor']['address']['local'],
            parsed['neighbor']['address']['peer'],
            parsed['neighbor']['asn']['local'],
            parsed['neighbor']['asn']['peer'],
        )

        if content == 'state':
            self._state()
            return json_string

        direction = parsed['neighbor']['direction']
        category = parsed['neighbor']['message']['category']
        header = parsed['neighbor']['message']['header']
        body = parsed['neighbor']['message']['body']
        data = b''.join(bytes([int(body[_ : _ + 2], 16)]) for _ in range(0, len(body), 2))

        if content == 'open':
            open_msg = Open.unpack_message(data, _get_dummy_negotiated())
            self._open(direction, open_msg)
            return cast(str, self.encoder.open(neighbor, direction, open_msg, None, header, body))

        if content == 'keepalive':
            return cast(str, self.encoder.keepalive(neighbor, direction, None, header, body))

        if content == 'notification':
            notif_msg = Notification.unpack_message(data, _get_dummy_negotiated())

            # Check for CEASE/Administrative Shutdown (code 6, subcode 2) which has special handling
            if (notif_msg.code, notif_msg.subcode) != (6, 2):
                # Use hexbytes for non-printable data (returns bytes, matching Notification.data type)
                notif_msg.data = (
                    data if not len([_ for _ in str(data) if _ not in string.printable]) else hexbytes(data)
                )
                return cast(str, self.encoder.notification(neighbor, direction, notif_msg, None, header, body))

            if len(data) == 0:
                # shutdown without shutdown communication (the old fashioned way)
                notif_msg.data = b''
                return cast(str, self.encoder.notification(neighbor, direction, notif_msg, None, header, body))

            # draft-ietf-idr-shutdown or the peer was using 6,2 with data

            shutdown_length = data[0]
            data = data[1:]

            if shutdown_length == 0:
                notif_msg.data = b'empty Shutdown Communication.'
                # move offset past length field
                return cast(str, self.encoder.notification(neighbor, direction, notif_msg, None, header, body))

            if len(data) < shutdown_length:
                notif_msg.data = (
                    f'invalid Shutdown Communication (buffer underrun) length : {shutdown_length} [{hexstring(data)}]'
                ).encode()
                return cast(str, self.encoder.notification(neighbor, direction, notif_msg, None, header, body))

            if shutdown_length > MAX_SHUTDOWN_COMM_LENGTH:
                notif_msg.data = (
                    f'invalid Shutdown Communication (too large) length : {shutdown_length} [{hexstring(data)}]'
                ).encode()
                return cast(str, self.encoder.notification(neighbor, direction, notif_msg, None, header, body))

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
                return cast(str, self.encoder.notification(neighbor, direction, notif_msg, None, header, body))

            trailer = data[shutdown_length:]
            if trailer:
                notif_msg.data += (', trailing data: ' + hexstring(trailer)).encode()

            return cast(str, self.encoder.notification(neighbor, direction, notif_msg, None, header, body))

        if not self.negotiated_in or not self.negotiated_out:
            sys.stderr.write('invalid message sequence, open exchange not complete: ' + json_string + '\n')
            sys.exit(1)

        negotiated = self.negotiated_in if direction == 'receive' else self.negotiated_out
        message = Message.unpack(category, data, negotiated)

        if content == 'update':
            return cast(str, self.encoder.update(neighbor, direction, message, None, header, body))

        if content == 'eor':
            # EOR (End of RIB) is encoded as a special UPDATE message
            return cast(str, self.encoder.update(neighbor, direction, message, None, header, body))

        if content == 'refresh':
            return cast(str, self.json.refresh(neighbor, direction, message, None, header, body))

        if content == 'operational':
            return cast(str, self.json.refresh(neighbor, direction, message, None, header, body))

        raise RuntimeError('the programer is a monkey and forgot a JSON message type')
