# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.util import concat_strs

from exabgp.protocol.ip import NoNextHop
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.direction import IN
from exabgp.bgp.message.direction import OUT
from exabgp.bgp.message.message import Message
from exabgp.bgp.message.update.eor import EOR

from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import MPRNLRI
from exabgp.bgp.message.update.attribute import EMPTY_MPRNLRI
from exabgp.bgp.message.update.attribute import MPURNLRI
from exabgp.bgp.message.update.attribute import EMPTY_MPURNLRI

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.logger import Logger
from exabgp.logger import LazyFormat

# ======================================================================= Update

# +-----------------------------------------------------+
# |   Withdrawn Routes Length (2 octets)                |
# +-----------------------------------------------------+
# |   Withdrawn Routes (variable)                       |
# +-----------------------------------------------------+
# |   Total Path Attribute Length (2 octets)            |
# +-----------------------------------------------------+
# |   Path Attributes (variable)                        |
# +-----------------------------------------------------+
# |   Network Layer Reachability Information (variable) |
# +-----------------------------------------------------+

# Withdrawn Routes:

# +---------------------------+
# |   Length (1 octet)        |
# +---------------------------+
# |   Prefix (variable)       |
# +---------------------------+

@Message.register
class Update (Message):
	ID = Message.CODE.UPDATE
	TYPE = chr(Message.CODE.UPDATE)
	EOR = False

	def __init__ (self, nlris, attributes):
		self.nlris = nlris
		self.attributes = attributes

	# message not implemented we should use messages below.

	def __str__ (self):
		return '\n'.join(['%s%s' % (str(self.nlris[n]),str(self.attributes)) for n in range(len(self.nlris))])

	@staticmethod
	def prefix (data):
		# This function needs renaming
		return concat_strs(pack('!H',len(data)),data)

	@staticmethod
	def split (data):
		length = len(data)

		len_withdrawn = unpack('!H',data[0:2])[0]
		withdrawn = data[2:len_withdrawn+2]

		if len(withdrawn) != len_withdrawn:
			raise Notify(3,1,'invalid withdrawn routes length, not enough data available')

		start_attributes = len_withdrawn+4
		len_attributes = unpack('!H',data[len_withdrawn+2:start_attributes])[0]
		start_announced = len_withdrawn+len_attributes+4
		attributes = data[start_attributes:start_announced]
		announced = data[start_announced:]

		if len(attributes) != len_attributes:
			raise Notify(3,1,'invalid total path attribute length, not enough data available')

		if 2 + len_withdrawn + 2 + len_attributes + len(announced) != length:
			raise Notify(3,1,'error in BGP message length, not enough data for the size announced')

		return withdrawn,attributes,announced

	# The routes MUST have the same attributes ...
	# XXX: FIXME: calculate size progressively to not have to do it every time
	# XXX: FIXME: we could as well track when packed_del, packed_mp_del, etc
	# XXX: FIXME: are emptied and therefore when we can save calculations
	def messages (self, negotiated, include_withdraw=True):
		# sort the nlris

		nlris = []
		mp_nlris = {}

		for nlri in self.nlris:
			if nlri.family() in negotiated.families:
				if nlri.afi == AFI.ipv4 and nlri.safi in [SAFI.unicast, SAFI.multicast]:
					nlris.append(nlri)
				else:
					mp_nlris.setdefault(nlri.family(), {}).setdefault(nlri.action, []).append(nlri)

		if not nlris and not mp_nlris:
			return

		attr = self.attributes.pack(negotiated, True)

		# Withdraws/NLRIS (IPv4 unicast and multicast)
		msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr) # 2 bytes for each of the two prefix() header
		withdraws = b''
		announced = b''
		for nlri in nlris:
			packed = nlri.pack(negotiated)
			if len(announced + withdraws + packed) > msg_size:
				if not withdraws and not announced:
					raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
				yield self._message(Update.prefix(withdraws) + Update.prefix(attr) + announced)
				if nlri.action == OUT.ANNOUNCE:
					announced = packed
					withdraws = b''
				elif include_withdraw:
					withdraws = packed
					announced = b''
			else:
				if nlri.action == OUT.ANNOUNCE:
					announced += packed
				elif include_withdraw:
					withdraws += packed

		if mp_nlris:
			for family in mp_nlris.keys():
				afi, safi = family
				mp_reach = b''
				mp_unreach = b''
				mp_announce = MPRNLRI(afi, safi, mp_nlris[family].get(OUT.ANNOUNCE, []))
				mp_withdraw = MPURNLRI(afi, safi, mp_nlris[family].get(OUT.WITHDRAW, []))

				for mprnlri in mp_announce.packed_attributes(negotiated, msg_size - len(withdraws + announced)):
					if mp_reach:
						yield self._message(Update.prefix(withdraws) + Update.prefix(attr + mp_reach) + announced)
						announced = b''
						withdraws = b''
					mp_reach = mprnlri

				if include_withdraw:
					for mpurnlri in mp_withdraw.packed_attributes(negotiated, msg_size - len(withdraws + announced + mp_reach)):
						if mp_unreach:
							yield self._message(Update.prefix(withdraws) + Update.prefix(attr + mp_unreach + mp_reach) + announced)
							mp_reach = b''
							announced = b''
							withdraws = b''
						mp_unreach = mpurnlri

				yield self._message(Update.prefix(withdraws) + Update.prefix(attr + mp_unreach + mp_reach) + announced) # yield mpr/mpur per family
				withdraws = b''
				announced = b''
		else:
			yield self._message(Update.prefix(withdraws) + Update.prefix(attr) + announced)

	# XXX: FIXME: this can raise ValueError. IndexError,TypeError, struct.error (unpack) = check it is well intercepted
	@classmethod
	def unpack_message (cls, data, negotiated):
		logger = Logger()

		logger.parser(LazyFormat("parsing UPDATE",data))

		length = len(data)

		# This could be speed up massively by changing the order of the IF
		if length == 4 and data == b'\x00\x00\x00\x00':
			return EOR(AFI(AFI.ipv4),SAFI(SAFI.unicast))  # pylint: disable=E1101
		if length == 11 and data.startswith(EOR.NLRI.PREFIX):
			return EOR.unpack_message(data,negotiated)

		withdrawn, _attributes, announced = cls.split(data)

		if not withdrawn:
			logger.parser("withdrawn NLRI none")

		attributes = Attributes.unpack(_attributes,negotiated)

		if not announced:
			logger.parser("announced NLRI none")

		# Is the peer going to send us some Path Information with the route (AddPath)
		addpath = negotiated.addpath.receive(AFI(AFI.ipv4),SAFI(SAFI.unicast))

		# empty string for NoNextHop, the packed IP otherwise (without the 3/4 bytes of attributes headers)
		nexthop = attributes.get(Attribute.CODE.NEXT_HOP,NoNextHop)
		# nexthop = NextHop.unpack(_nexthop.ton())

		# XXX: NEXTHOP MUST NOT be the IP address of the receiving speaker.

		nlris = []
		while withdrawn:
			nlri,left = NLRI.unpack_nlri(AFI.ipv4,SAFI.unicast,withdrawn,IN.WITHDRAWN,addpath)
			logger.parser("withdrawn NLRI %s" % nlri)
			withdrawn = left
			nlris.append(nlri)

		while announced:
			nlri,left = NLRI.unpack_nlri(AFI.ipv4,SAFI.unicast,announced,IN.ANNOUNCED,addpath)
			nlri.nexthop = nexthop
			logger.parser("announced NLRI %s" % nlri)
			announced = left
			nlris.append(nlri)

		unreach = attributes.pop(MPURNLRI.ID,None)
		reach = attributes.pop(MPRNLRI.ID,None)

		if unreach is not None:
			nlris.extend(unreach.nlris)

		if reach is not None:
			nlris.extend(reach.nlris)

		if not attributes and not nlris:
			# Careful do not use == or != as the comparaison does not work
			if unreach is None and reach is None:
				return EOR(AFI(AFI.ipv4),SAFI(SAFI.unicast))
			if unreach is not None:
				return EOR(unreach.afi,unreach.safi)
			if reach is not None:
				return EOR(reach.afi,reach.safi)
			raise RuntimeError('This was not expected')

		return Update(nlris,attributes)
