# encoding: utf-8
"""
update/__init__.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI,SAFI

from exabgp.bgp.message import Message,prefix
from exabgp.bgp.message.direction import OUT
from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

from exabgp.bgp.message.notification import Notify

# =================================================================== Update

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
	TYPE = chr(Message.Type.UPDATE)

	def __init__ (self,nlris,attributes):
		self.nlris = nlris
		self.attributes = attributes

	# message not implemented we should use messages below.

	def __str__ (self):
		return '\n'.join(['%s%s' % (str(self.nlris[n]),str(self.attributes)) for n in range(len(self.nlris))])


	# The routes MUST have the same attributes ...
	# XXX: FIXME: calculate size progressively to not have to do it every time
	# XXX: FIXME: we could as well track when packed_del, packed_mp_del, etc
	# XXX: FIXME: are emptied and therefore when we can save calculations
	def messages (self,negotiated):
		# sort the nlris

		add_nlri = []
		del_nlri = []
		add_mp = {}
		del_mp = {}

		for nlri in self.nlris:
			if nlri.family() in negotiated.families:
				if nlri.afi == AFI.ipv4 and nlri.safi in [SAFI.unicast, SAFI.multicast]:
					if nlri.action == OUT.announce:
						add_nlri.append(nlri)
					else:
						del_nlri.append(nlri)
				else:
					if nlri.action == OUT.announce:
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
			if len(packed_del + packed) >= msg_size:
				if not packed_del:
					raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
				yield self._message(prefix(packed_del) + prefix(''))
				packed_del = packed
			else:
				packed_del += packed

		# withdrawn MP

		packed_mp_del = ''

		families = del_mp.keys()
		while families:
			family = families.pop()
			mps = del_mp[family]
			addpath = negotiated.addpath.send(*family)
			mp_packed_generator = MPURNLRI(mps).packed_attributes(addpath)
			try:
				while True:
					packed = mp_packed_generator.next()
					if len(packed_del + packed_mp_del + packed) >= msg_size:
						if not packed_mp_del and not packed_del:
							raise Notify(6,0,'attributes size is so large we can not even pack one MPURNLRI')
						yield self._message(prefix(packed_del) + prefix(packed_mp_del))
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
		if len(packed_del + packed_mp_del) >= msg_size:
			yield self._message(prefix(packed_del) + prefix(packed_mp_del))
			packed_del = ''
			packed_mp_del = ''

		families = add_mp.keys()
		while families:
			family = families.pop()
			mps = add_mp[family]
			addpath = negotiated.addpath.send(*family)
			mp_packed_generator = MPRNLRI(mps).packed_attributes(addpath)
			try:
				while True:
					packed = mp_packed_generator.next()
					if len(packed_del + packed_mp_del + packed_mp_add + packed) >= msg_size:
						if not packed_mp_add and not packed_mp_del and not packed_del:
							raise Notify(6,0,'attributes size is so large we can not even pack on MPURNLRI')
						yield self._message(prefix(packed_del) + prefix(attr + packed_mp_del + packed_mp_add))
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
		if len(packed_del + packed_mp_del + packed_mp_add) >= msg_size:
			yield self._message(prefix(packed_del) + prefix(packed_mp_del))
			packed_del = ''
			packed_mp_del = ''

		addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)

		while add_nlri:
			nlri = add_nlri.pop()
			packed = nlri.pack(addpath)
			if len(packed_del + packed_mp_del + packed_mp_add + packed_add + packed) >= msg_size:
				if not packed_add and not packed_mp_add and not packed_mp_del and not packed_del:
					raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
				if packed_mp_add:
					yield self._message(prefix(packed_del) + prefix(attr + packed_mp_del + packed_mp_add) + packed_add)
					msg_size = negotiated.msg_size - 19 - 2 - 2  # 2 bytes for each of the two prefix() header
				else:
					yield self._message(prefix(packed_del) + prefix(attr + packed_mp_del) + packed_add)
				packed_del = ''
				packed_mp_del = ''
				packed_mp_add = ''
				packed_add = packed
			else:
				packed_add += packed

		yield self._message(prefix(packed_del) + prefix(attr + packed_mp_del + packed_mp_add) + packed_add)
