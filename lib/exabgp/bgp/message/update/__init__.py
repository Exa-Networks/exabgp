# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack
from struct import unpack

from exabgp.protocol.ip import NoIP
from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message import Message
from exabgp.bgp.message import IN
from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.eor import EOR

from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mprnlri import EMPTY_MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import EMPTY_MPURNLRI

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI

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
		return '%s%s' % (pack('!H',len(data)),data)

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
	def messages (self, negotiated):
		# sort the nlris

		add_nlri = []
		del_nlri = []
		add_mp = {}
		del_mp = {}

		for nlri in self.nlris:
			if nlri.family() in negotiated.families:
				if nlri.afi == AFI.ipv4 and nlri.safi in [SAFI.unicast, SAFI.multicast]:
					if nlri.action == OUT.ANNOUNCE:
						add_nlri.append(nlri)
					else:
						del_nlri.append(nlri)
				else:
					if nlri.action == OUT.ANNOUNCE:
						add_mp.setdefault(nlri.family(),[]).append(nlri)
					else:
						del_mp.setdefault(nlri.family(),[]).append(nlri)

		if not add_nlri and not del_nlri and not add_mp and not del_mp:
			return

		if add_nlri or add_mp:
			attr = self.attributes.pack(negotiated,True)
		else:
			attr = ''

		# withdrawn IPv4

		packed_del = ''
		msg_size = negotiated.msg_size - 19 - 2 - 2  # 2 bytes for each of the two prefix() header
		addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)

		while del_nlri:
			nlri = del_nlri.pop()
			packed = nlri.pack(addpath)
			seen_size = len(packed_del + packed)
			if seen_size > msg_size:
				if not packed_del:
					raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
				yield self._message(Update.prefix(packed_del) + Update.prefix(''))
				packed_del = packed
			else:
				packed_del += packed

		# withdrawn MP

		packed_mp_del = ''

		families = del_mp.keys()
		while families:
			family = families.pop()
			afi,safi = family
			mps = del_mp[family]
			addpath = negotiated.addpath.send(*family)
			seen_size = len(packed_del + packed_mp_del)
			mp_packed_generator = MPURNLRI(afi,safi,mps).packed_attributes(addpath,msg_size-seen_size)
			try:
				while True:
					packed = mp_packed_generator.next()
					seen_size = len(packed_del + packed_mp_del + packed)
					if seen_size > msg_size:
						if not packed_mp_del and not packed_del:
							raise Notify(6,0,'attributes size is so large we can not even pack one MPURNLRI')
						yield self._message(Update.prefix(packed_del) + Update.prefix(packed_mp_del))
						packed_del = ''
						packed_mp_del = packed
					else:
						packed_mp_del += packed
			except StopIteration:
				pass

		# add MP

		# we have some MPRNLRI so we need to add the attributes, recalculate
		# and make sure we do not overflow

		packed_mp_add = ''

		if add_mp:
			msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr)  # 2 bytes for each of the two prefix() header
		seen_size = len(packed_del + packed_mp_del)
		if seen_size > msg_size:
			yield self._message(Update.prefix(packed_del) + Update.prefix(packed_mp_del))
			packed_del = ''
			packed_mp_del = ''

		families = add_mp.keys()
		while families:
			family = families.pop()
			afi,safi = family
			mps = add_mp[family]
			addpath = negotiated.addpath.send(*family)
			seen_size = len(packed_del + packed_mp_del + packed_mp_add)
			mp_packed_generator = MPRNLRI(afi,safi,mps).packed_attributes(addpath,msg_size-seen_size)
			try:
				while True:
					packed = mp_packed_generator.next()
					seen_size = len(packed_del + packed_mp_del + packed_mp_add + packed)
					if seen_size > msg_size:
						if not packed_mp_add and not packed_mp_del and not packed_del:
							raise Notify(6,0,'attributes size is so large we can not even pack on MPURNLRI')
						yield self._message(Update.prefix(packed_del) + Update.prefix(attr + packed_mp_del + packed_mp_add))
						packed_del = ''
						packed_mp_del = ''
						packed_mp_add = packed
					else:
						packed_mp_add += packed
			except StopIteration:
				pass

		# ADD Ipv4

		packed_add = ''

		if add_nlri:
			msg_size = negotiated.msg_size - 19 - 2 - 2 - len(attr)  # 2 bytes for each of the two prefix() header
		seen_size = len(packed_del + packed_mp_del + packed_mp_add)
		if seen_size > msg_size:
			yield self._message(Update.prefix(packed_del) + Update.prefix(packed_mp_del))
			packed_del = ''
			packed_mp_del = ''

		addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)

		while add_nlri:
			nlri = add_nlri.pop()
			packed = nlri.pack(addpath)
			seen_size = len(packed_del + packed_mp_del + packed_mp_add + packed_add + packed)
			if seen_size > msg_size:
				if not packed_add and not packed_mp_add and not packed_mp_del and not packed_del:
					raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
				if packed_mp_add:
					yield self._message(Update.prefix(packed_del) + Update.prefix(attr + packed_mp_del + packed_mp_add) + packed_add)
					msg_size = negotiated.msg_size - 19 - 2 - 2  # 2 bytes for each of the two prefix() header
				else:
					yield self._message(Update.prefix(packed_del) + Update.prefix(attr + packed_mp_del) + packed_add)
				packed_del = ''
				packed_mp_del = ''
				packed_mp_add = ''
				packed_add = packed
			else:
				packed_add += packed

		yield self._message(Update.prefix(packed_del) + Update.prefix(attr + packed_mp_del + packed_mp_add) + packed_add)

	# XXX: FIXME: this can raise ValueError. IndexError,TypeError, struct.error (unpack) = check it is well intercepted
	@classmethod
	def unpack_message (cls, data, negotiated):
		logger = Logger()

		length = len(data)

		# This could be speed up massively by changing the order of the IF
		if length == 4 and data == '\x00\x00\x00\x00':
			return EOR(AFI.ipv4,SAFI.unicast,IN.ANNOUNCED)  # pylint: disable=E1101
		if length == 11 and data.startswith(EOR.NLRI.PREFIX):
			return EOR.unpack_message(data,negotiated)

		withdrawn, _attributes, announced = cls.split(data)
		attributes = Attributes.unpack(_attributes,negotiated)

		if not withdrawn:
			logger.parser("no withdrawn NLRI")
		if not announced:
			logger.parser("no announced NLRI")

		# Is the peer going to send us some Path Information with the route (AddPath)
		addpath = negotiated.addpath.receive(AFI(AFI.ipv4),SAFI(SAFI.unicast))

		# empty string for NoIP, the packed IP otherwise (without the 3/4 bytes of attributes headers)
		_nexthop = attributes.get(Attribute.CODE.NEXT_HOP,NoIP)
		nexthop = _nexthop.packed

		# XXX: NEXTHOP MUST NOT be the IP address of the receiving speaker.

		nlris = []
		while withdrawn:
			length,nlri = NLRI.unpack(AFI.ipv4,SAFI.unicast,withdrawn,addpath,nexthop,IN.WITHDRAWN)
			logger.parser(LazyFormat("parsed withdraw nlri %s payload " % nlri,withdrawn[:len(nlri)]))
			withdrawn = withdrawn[length:]
			nlris.append(nlri)

		while announced:
			length,nlri = NLRI.unpack(AFI.ipv4,SAFI.unicast,announced,addpath,nexthop,IN.ANNOUNCED)
			logger.parser(LazyFormat("parsed announce nlri %s payload " % nlri,announced[:len(nlri)]))
			announced = announced[length:]
			nlris.append(nlri)

		# required for 'is' comparaison
		UNREACH = [EMPTY_MPURNLRI,]
		REACH = [EMPTY_MPRNLRI,]

		unreach = attributes.pop(MPURNLRI.ID,UNREACH)
		reach = attributes.pop(MPRNLRI.ID,REACH)

		for mpr in unreach:
			nlris.extend(mpr.nlris)

		for mpr in reach:
			nlris.extend(mpr.nlris)

		if not attributes and not nlris:
			# Careful do not use == or != as the comparaison does not work
			if unreach is UNREACH and reach is REACH:
				return EOR(AFI(AFI.ipv4),SAFI(SAFI.unicast))
			if unreach is not UNREACH:
				return EOR(unreach[0].afi,unreach[0].safi)
			if reach is not REACH:
				return EOR(reach[0].afi,reach[0].safi)
			raise RuntimeError('This was not expected')

		return Update(nlris,attributes)
