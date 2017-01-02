import struct
import sys
import json

from exabgp.bgp.message import Message
from exabgp.bgp.message import Open
from exabgp.bgp.message import Notification
from exabgp.bgp.message.open.capability import Negotiated

from exabgp.version import json as json_version
from exabgp.reactor.api.response import Response

from exabgp.protocol.ip import IPv4
from exabgp.bgp.message.open.asn import ASN


class _FakeNeighbor (object):
	def __init__ (self,local,remote,asn,peer):
		self.local_address = IPv4(local)
		self.peer_address = IPv4(remote)
		self.peer_as = ASN(asn)
		self.local_as = ASN(peer)


class Transcoder (object):
	seen_open = {
		'send':    None,
		'receive': None,
	}
	negotiated = None

	json = Response.JSON(json_version)

	def __init__ (self, src='json', dst='json'):
		if src != 'json':
			raise RuntimeError('left as an exercise to the reader')

		if dst != 'json':
			raise RuntimeError('left as an exercise to the reader')

		self.convert = self._from_json
		self.encoder = self.json

	def _state (self):
		self.seen_open['send'] = None
		self.seen_open['receive'] = None
		self.negotiated = None

	def _open (self,direction,message):
		self.seen_open[direction] = message

		if all(self.seen_open.values()):
			self.negotiated = Negotiated(None)
			self.negotiated.sent(self.seen_open['send'])
			self.negotiated.received(self.seen_open['receive'])

	def _from_json (self, string):
		try:
			parsed = json.loads(string)
		except ValueError:
			print >> sys.stderr, 'invalid JSON message'
			sys.exit(1)

		if parsed.get('exabgp','0.0.0') != json_version:
			print >> sys.stderr, 'invalid json version', string
			sys.exit(1)

		content = parsed.get('type','')

		if not content:
			print >> sys.stderr, 'invalid json content', string
			sys.exit(1)

		neighbor = _FakeNeighbor(
			parsed['neighbor']['address']['local'],
			parsed['neighbor']['address']['peer'],
			parsed['neighbor']['asn']['local'],
			parsed['neighbor']['asn']['peer'],
		)

		if content == 'state':
			self._state()
			return string

		direction = parsed['neighbor']['direction']
		category = parsed['neighbor']['message']['category']
		header = parsed['neighbor']['message']['header']
		body = parsed['neighbor']['message']['body']
		raw = ''.join(chr(int(body[_:_+2],16)) for _ in range(0,len(body),2))

		if content == 'open':
			message = Open.unpack_message(raw)
			self._open(direction,message)
			return self.encoder.open(neighbor,direction,message,header,body)

		if content == 'keapalive':
			return self.encoder.keepalive(neighbor,direction,header,body)

		if content == 'notification':
			message = Notification.unpack_message(raw)

			# draft-ietf-idr-shutdown
			if (message.code, message.subcode) == (6, 2):
				if len(message.data):
					shutdown_length = struct.unpack('B', message.data[0])[0]
					remainder_offset = 0
					if shutdown_length == 0:
						message.data = "The peer sent an empty Shutdown Communication."
						# move offset past length field
						remainder_offset += 1
					if shutdown_length > 128:
						message.data = "The peer sent too long Shutdown Communication: %i octets: %s" \
							% (shutdown_length, hexstring(data))
					else:
						try:
							message.data = "Shutdown Communication: \"" \
								+ message.data[1:shutdown_length+1].decode('utf-8').replace('\r',' ').replace('\n',' ') \
								+ "\""
							# move offset past the shutdown communication
							remainder_offset += shutdown_length + 1
						except Exception:
							message.data = "The peer sent a invalid Shutdown Communication (invalid UTF-8)"
							# rewind the offset to before the invalid utf8, so we'll hexdump it later
							remainder_offset -= shutdown_length - 1

					# dump any trailing data (if any)
					if len(message.data) > remainder_offset:
						message.data += ", trailing data: " + hexstring(message.data[remainder_offset:])

			return self.encoder.notification(neighbor,direction,message,header,body)

		if not self.negotiated:
			print >> sys.stderr, 'invalid message sequence, open not exchange not complete', string
			sys.exit(1)

		message = Message.unpack(category,raw,self.negotiated)

		if content == 'update':
			return self.encoder.update(neighbor, direction, message, header,body)

		if content == 'eor':  # XXX: Should not be required
			return self.encoder.update(neighbor, direction, message, header,body)

		if content == 'refresh':
			return self.json.refresh(neighbor, direction, message, header,body)

		if content == 'operational':
			return self.json.refresh(neighbor, direction, message, header,body)

		raise RuntimeError('the programer is a monkey and forgot a JSON message type')
