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

class Update (Message):
	TYPE = chr(0x02)

	def __init__ (self,nlris,attributes):
		self.nlris = nlris
		self.attributes = attributes

	def __str__ (self):
		return '\n'.join(['%s%s' % (str(self.nlris[n]),str(self.attributes)) for n in range(len(self.nlris))])


# The routes MUST have the same attributes ...
# XXX: FIXME: calculate size progressively to not have to do it every time
# XXX: FIXME: we could as well track when packed_del, packed_mp_del, etc
# XXX: FIXME: are emptied and therefore when we can save calculations
def messages (update,negotiated):
	attributes = ''

	asn4 = negotiated.asn4
	local_as = negotiated.local_as
	peer_as = negotiated.peer_as

	msg_size = negotiated.msg_size - 2 - 2  # 2 bytes for each of the two prefix() header

	# sort the nlris

	add_nlri = []
	del_nlri = []
	add_mp = {}
	del_mp = {}

	for nlri in update.nlris:
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

	if add_nlri:
		attr = update.attributes.pack(asn4,local_as,peer_as,True)
	elif add_mp:
		add_default = False
		for afi,safi in add_mp:
			if safi not in (SAFI.flow_ip,SAFI.flow_vpn):
				add_default = True
		attr = update.attributes.pack(asn4,local_as,peer_as,add_default)
	else:
		attr = ''

	# generate the message

	packed_del = ''
	packed_mp_del = ''
	packed_mp_add = ''
	packed_add = ''


	# withdrawn IPv4

	addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)

	while del_nlri:
		nlri = del_nlri.pop()
		packed = nlri.pack(addpath)
		if len(packed_del + packed) > msg_size:
			if not packed_del:
				raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
			yield update.message(prefix(packed_del))
			packed_del = packed
		else:
			packed_del += packed


	# withdrawn MP

	families = del_mp.keys()
	while families:
		family = families.pop()
		mps = del_mp[family]
		addpath = negotiated.addpath.send(*family)
		mp_packed_generator = MPURNLRI(mps).packed_attributes(addpath)
		try:
			while True:
				packed = mp_packed_generator.next()
				if len(packed_del + packed_mp_del + packed) > msg_size:
					if not packed_mp_del and not packed_del:
						raise Notify(6,0,'attributes size is so large we can not even pack one MPURNLRI')
					yield update.message(prefix(packed_del) + prefix(packed_mp_del))
					packed_del = ''
					packed_mp_del = packed
				else:
					packed_mp_del += packed
		except StopIteration:
			pass

	# we have some MPRNLRI so we need to add the attributes, recalculate
	# and make sure we do not overflow

	if add_mp:
		msg_size = negotiated.msg_size - 2 - 2 - len(attr)  # 2 bytes for each of the two prefix() header
	if len(packed_del + packed_mp_del) > msg_size:
		yield update.message(prefix(packed_del) + prefix(packed_mp_del))
		packed_del = ''
		packed_mp_del = ''

	# add MP

	families = add_mp.keys()
	while families:
		family = families.pop()
		mps = add_mp[family]
		addpath = negotiated.addpath.send(*family)
		mp_packed_generator = MPRNLRI(mps).packed_attributes(addpath)
		try:
			while True:
				packed = mp_packed_generator.next()
				if len(packed_del + packed_mp_del + packed_mp_add + packed) > msg_size:
					if not packed_mp_add and not packed_mp_del and not packed_del:
						raise Notify(6,0,'attributes size is so large we can not even pack on MPURNLRI')
					yield update.message(prefix(packed_del) + prefix(attributes + packed_mp_del + packed_mp_add))
					packed_del = ''
					packed_mp_del = ''
					packed_mp_add = packed
					if family not in ((AFI.ipv4,SAFI.flow_ip),(AFI.ipv4,SAFI.flow_vpn)):
						attributes = attr
					else:
						attributes = ''
				else:
					packed_mp_add += packed
					attributes = attr
		except StopIteration:
			pass

	# recalculate size if we do not have any more attributes to send

	if not packed_mp_add:
		msg_size = negotiated.msg_size - 2 - 2  # 2 bytes for each of the two prefix() header

	# ADD Ipv4

	addpath = negotiated.addpath.send(AFI.ipv4,SAFI.unicast)
	while add_nlri:
		nlri = add_nlri.pop()
		packed = nlri.pack(addpath)
		if len(packed_del + packed_mp_del + packed_mp_add + packed_add + packed) > msg_size:
			if not packed_add and not packed_mp_add and not packed_mp_del and not packed_del:
				raise Notify(6,0,'attributes size is so large we can not even pack one NLRI')
			if packed_mp_add:
				yield update.message(prefix(packed_del) + prefix(attributes + packed_mp_del + packed_mp_add) + packed_add)
				msg_size = negotiated.msg_size - 2 - 2  # 2 bytes for each of the two prefix() header
			else:
				yield update.message(prefix(packed_del) + prefix(packed_mp_del) + packed_add)
			packed_del = ''
			packed_mp_del = ''
			packed_mp_add = ''
			packed_add = packed
			attributes = attr
		else:
			packed_add += packed
			attributes = attr

	yield update.message(prefix(packed_del) + prefix(attributes + packed_mp_del + packed_mp_add) + packed_add)
