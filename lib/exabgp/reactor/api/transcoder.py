from __future__ import print_function

import sys
import json
import string

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes_i
from exabgp.util import hexstring

from exabgp.bgp.message import Message
from exabgp.bgp.message import Open
from exabgp.bgp.message import Notification
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability import Negotiated

from exabgp.version import json as json_version
from exabgp.reactor.api.response import Response

from exabgp.protocol.ip import IPv4


class _FakeNeighbor(object):
    def __init__(self, local, remote, asn, peer):
        self.local_address = IPv4(local)
        self.peer_address = IPv4(remote)
        self.peer_as = ASN(asn)
        self.local_as = ASN(peer)


class Transcoder(object):
    seen_open = {
        'send': None,
        'receive': None,
    }
    negotiated = None

    json = Response.JSON(json_version)

    def __init__(self, src='json', dst='json'):
        if src != 'json':
            raise RuntimeError('left as an exercise to the reader')

        if dst != 'json':
            raise RuntimeError('left as an exercise to the reader')

        self.convert = self._from_json
        self.encoder = self.json

    def _state(self):
        self.seen_open['send'] = None
        self.seen_open['receive'] = None
        self.negotiated = None

    def _open(self, direction, message):
        self.seen_open[direction] = message

        if all(self.seen_open.values()):
            self.negotiated = Negotiated(None)
            self.negotiated.sent(self.seen_open['send'])
            self.negotiated.received(self.seen_open['receive'])

    def _from_json(self, json_string):
        try:
            parsed = json.loads(json_string)
        except ValueError:
            print('invalid JSON message', file=sys.stderr)
            sys.exit(1)

        if parsed.get('exabgp', '0.0.0') != json_version:
            print('invalid json version', json_string, file=sys.stderr)
            sys.exit(1)

        content = parsed.get('type', '')

        if not content:
            print('invalid json content', json_string, file=sys.stderr)
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
        data = concat_bytes_i(character(int(body[_ : _ + 2], 16)) for _ in range(0, len(body), 2))

        if content == 'open':
            message = Open.unpack_message(data)
            self._open(direction, message)
            return self.encoder.open(neighbor, direction, message, None, header, body)

        if content == 'keepalive':
            return self.encoder.keepalive(neighbor, direction, None, header, body)

        if content == 'notification':
            # XXX: Use the code of the Notifcation class here ..
            message = Notification.unpack_message(data)

            if (message.code, message.subcode) != (6, 2):
                message.data = data if not len([_ for _ in data if _ not in string.printable]) else hexstring(data)
                return self.encoder.notification(neighbor, direction, message, None, header, body)

            if len(data) == 0:
                # shutdown without shutdown communication (the old fashioned way)
                message.data = ''
                return self.encoder.notification(neighbor, direction, message, None, header, body)

            # draft-ietf-idr-shutdown or the peer was using 6,2 with data

            shutdown_length = ordinal(data[0])
            data = data[1:]

            if shutdown_length == 0:
                message.data = "empty Shutdown Communication."
                # move offset past length field
                return self.encoder.notification(neighbor, direction, message, None, header, body)

            if len(data) < shutdown_length:
                message.data = "invalid Shutdown Communication (buffer underrun) length : %i [%s]" % (
                    shutdown_length,
                    hexstring(data),
                )
                return self.encoder.notification(neighbor, direction, message, None, header, body)

            if shutdown_length > 128:
                message.data = "invalid Shutdown Communication (too large) length : %i [%s]" % (
                    shutdown_length,
                    hexstring(data),
                )
                return self.encoder.notification(neighbor, direction, message, None, header, body)

            try:
                message.data = 'Shutdown Communication: "%s"' % data[:shutdown_length].decode('utf-8').replace(
                    '\r', ' '
                ).replace('\n', ' ')
            except UnicodeDecodeError:
                message.data = "invalid Shutdown Communication (invalid UTF-8) length : %i [%s]" % (
                    shutdown_length,
                    hexstring(data),
                )
                return self.encoder.notification(neighbor, direction, message, None, header, body)

            trailer = data[shutdown_length:]
            if trailer:
                message.data += ", trailing data: " + hexstring(trailer)

            return self.encoder.notification(neighbor, direction, message, None, header, body)

        if not self.negotiated:
            print('invalid message sequence, open not exchange not complete', json_string, file=sys.stderr)
            sys.exit(1)

        message = Message.unpack(category, data, self.negotiated)

        if content == 'update':
            return self.encoder.update(neighbor, direction, message, None, header, body)

        if content == 'eor':  # XXX: Should not be required
            return self.encoder.update(neighbor, direction, message, None, header, body)

        if content == 'refresh':
            return self.json.refresh(neighbor, direction, message, None, header, body)

        if content == 'operational':
            return self.json.refresh(neighbor, direction, message, None, header, body)

        raise RuntimeError('the programer is a monkey and forgot a JSON message type')
