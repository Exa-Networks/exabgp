import os
import socket
from struct import pack
from struct import unpack
from struct import calcsize
from collections import namedtuple

from exabgp.netlink import NetLinkError
from exabgp.netlink.sequence import Sequence
from exabgp.netlink.attributes import Attributes

try:
	getattr(socket,'AF_NETLINK')
except AttributeError:
	raise ImportError('This module only works on unix version with netlink support')


class NetLinkRouteError (Exception):
	pass


class NetLinkRoute (object):
	_IGNORE_SEQ_FAULTS = True

	NETLINK_ROUTE = 0

	format = namedtuple('Message','type flags seq pid data')
	pid = os.getpid()
	netlink = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, NETLINK_ROUTE)

	class Header (object):
		# linux/netlink.h
		PACK  = 'IHHII'
		LEN = calcsize(PACK)

	class Command (object):
		NLMSG_NOOP    = 0x01
		NLMSG_ERROR   = 0x02
		NLMSG_DONE    = 0x03
		NLMSG_OVERRUN = 0x04

	class Flags (object):
		NLM_F_REQUEST = 0x01  # It is query message.
		NLM_F_MULTI   = 0x02  # Multipart message, terminated by NLMSG_DONE
		NLM_F_ACK     = 0x04  # Reply with ack, with zero or error code
		NLM_F_ECHO    = 0x08  # Echo this query

		# Modifiers to GET query
		NLM_F_ROOT   = 0x100  # specify tree root
		NLM_F_MATCH  = 0x200  # return all matching
		NLM_F_DUMP   = NLM_F_ROOT | NLM_F_MATCH
		NLM_F_ATOMIC = 0x400  # atomic GET

		# Modifiers to NEW query
		NLM_F_REPLACE = 0x100  # Override existing
		NLM_F_EXCL    = 0x200  # Do not touch, if it exists
		NLM_F_CREATE  = 0x400  # Create, if it does not exist
		NLM_F_APPEND  = 0x800  # Add to end of list

	errors = {
		Command.NLMSG_ERROR:   'netlink error',
		Command.NLMSG_OVERRUN: 'netlink overrun',
	}

	@classmethod
	def encode (cls, dtype, seq, flags, body, attributes):
		attrs = Attributes.encode(attributes)
		length = cls.Header.LEN + len(attrs) + len(body)
		return pack(cls.Header.PACK, length, dtype, flags, seq, cls.pid) + body + attrs

	@classmethod
	def decode (cls, data):
		while data:
			length, ntype, flags, seq, pid = unpack(cls.Header.PACK,data[:cls.Header.LEN])
			if len(data) < length:
				raise NetLinkRouteError("Buffer underrun")
			yield cls.format(ntype, flags, seq, pid, data[cls.Header.LEN:length])
			data = data[length:]

	@classmethod
	def send (cls, dtype, hflags, family=socket.AF_UNSPEC):
		sequence = Sequence()

		message = cls.encode(
			dtype,
			sequence,
			hflags,
			pack('Bxxx', family),
			{}
		)

		cls.netlink.send(message)

		while True:
			data = cls.netlink.recv(640000)
			for mtype, flags, seq, pid, data in cls.decode(data):
				if seq != sequence:
					if cls._IGNORE_SEQ_FAULTS:
						continue
					raise NetLinkError("netlink seq mismatch")
				if mtype == NetLinkRoute.Command.NLMSG_DONE:
					raise StopIteration()
				elif dtype in cls.errors:
					raise NetLinkError(cls.errors[mtype])
				else:
					yield data

	# def change (self, dtype, family=socket.AF_UNSPEC):
	# 	for _ in self.send(dtype, self.Flags.NLM_F_REQUEST | self.Flags.NLM_F_CREATE,family):
	# 		yield _
