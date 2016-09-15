# encoding: utf-8
"""
check.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# common

import traceback

from exabgp.bgp.message import Update
from exabgp.bgp.message import Open
from exabgp.bgp.message.open import Version
from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.open import RouterID
from exabgp.bgp.message.open import HoldTime
from exabgp.bgp.message.open.capability import Capabilities
from exabgp.bgp.message.open.capability import Capability
from exabgp.bgp.message.open.capability import Negotiated
from exabgp.bgp.message import Notify
from exabgp.bgp.message.update.nlri import NLRI

from exabgp.logger import Logger

# check_neighbor

from exabgp.util.od import od
from exabgp.rib.change import Change

# check_update

from exabgp.reactor.api.response import Response

# check_notification

from exabgp.bgp.message import Notification

# JSON version

from exabgp.version import json as json_version


# =============================================================== check_neighbor
# ...


def check_neighbor (neighbors):
	logger = Logger()
	logger._option.parser = True

	logger.parser('\ndecoding routes in configuration')

	for name in neighbors.keys():
		neighbor = neighbors[name]

		path = {}
		for f in NLRI.known_families():
			if neighbor.add_path:
				path[f] = neighbor.add_path

		capa = Capabilities().new(neighbor,False)
		if path:
			capa[Capability.CODE.ADD_PATH] = path
		capa[Capability.CODE.MULTIPROTOCOL] = neighbor.families()

		routerid_1 = str(neighbor.router_id)
		routerid_2 = '.'.join(str((int(_)+1) % 250) for _ in str(neighbor.router_id).split('.',-1))

		o1 = Open(Version(4),ASN(neighbor.local_as),HoldTime(180),RouterID(routerid_1),capa)
		o2 = Open(Version(4),ASN(neighbor.peer_as),HoldTime(180),RouterID(routerid_2),capa)
		negotiated = Negotiated(neighbor)
		negotiated.sent(o1)
		negotiated.received(o2)
		# grouped = False

		for _ in neighbor.rib.outgoing.updates(False):
			pass

		for change1 in neighbor.rib.outgoing.sent_changes():
			str1 = change1.extensive()
			packed = list(Update([change1.nlri],change1.attributes).messages(negotiated))
			pack1 = packed[0]

			logger.parser('parsed route requires %d updates' % len(packed))
			logger.parser('update size is %d' % len(pack1))

			logger.parser('parsed route %s' % str1)
			logger.parser('parsed hex   %s' % od(pack1))

			# This does not take the BGP header - let's assume we will not break that :)
			try:
				logger.parser('')  # new line

				pack1s = pack1[19:] if pack1.startswith('\xFF'*16) else pack1
				update = Update.unpack_message(pack1s,negotiated)

				change2 = Change(update.nlris[0],update.attributes)
				str2 = change2.extensive()
				pack2 = list(Update([update.nlris[0]],update.attributes).messages(negotiated))[0]

				logger.parser('recoded route %s' % str2)
				logger.parser('recoded hex   %s' % od(pack2))

				str1 = str1.replace('attribute [ 0x04 0x80 0x00000064 ]','med 100')
				str1r = str1.lower().replace(' med 100','').replace(' local-preference 100','').replace(' origin igp','')
				str2r = str2.lower().replace(' med 100','').replace(' local-preference 100','').replace(' origin igp','')

				if 'next-hop self' in str1r:
					if ':' in str1r:
						str1r = str1r.replace('next-hop self','next-hop ::1')
					else:
						str1r = str1r.replace('next-hop self','next-hop %s' % neighbor.local_address)

				if ' name ' in str1r:
					parts = str1r.split(' ')
					pos = parts.index('name')
					str1r = ' '.join(parts[:pos] + parts[pos+2:])

				skip = False

				if str1r != str2r:
					if 'attribute [' in str1r and ' 0x00 ' in str1r:
						# we do not decode non-transitive attributes
						logger.parser('skipping string check on update with non-transitive attribute(s)')
						skip = True
					else:
						logger.parser('strings are different:')
						logger.parser('[%s]' % (str1r))
						logger.parser('[%s]' % (str2r))
						return False
				else:
					logger.parser('strings are fine')

				if skip:
					logger.parser('skipping encoding for update with non-transitive attribute(s)')
				elif pack1 != pack2:
					logger.parser('encoding are different')
					logger.parser('[%s]' % (od(pack1)))
					logger.parser('[%s]' % (od(pack2)))
					return False
				else:
					logger.parser('encoding is fine')
					logger.parser('----------------------------------------')

				logger.parser('JSON nlri %s' % change1.nlri.json())
				logger.parser('JSON attr %s' % change1.attributes.json())

			except Notify,exc:
				logger.parser('----------------------------------------')
				logger.parser(str(exc))
				logger.parser('----------------------------------------')
				return False
		neighbor.rib.clear()

	return True


# ================================================================ check_message
#

def check_message (neighbor, message):
	message = message.replace(':','')
	raw = ''.join(chr(int(_,16)) for _ in (message[i*2:(i*2)+2] for i in range(len(message)/2)))

	if raw.startswith('\xff'*16):
		kind = ord(raw[18])
		# XXX: FIXME: check size
		# size = (ord(raw[16]) << 16) + (ord(raw[17]))

		if kind == 1:
			return check_open(neighbor,raw[18:])
		elif kind == 2:
			return check_update(neighbor,raw)
		elif kind == 3:
			return check_notification(raw)
	else:
		return check_update(neighbor,raw)


# ================================================================= check_update
#

def check_open (neighbor, raw):
	pass


# ================================================================= check_update
#

def check_update (neighbor, raw):
	logger = Logger()
	logger._option.parser = True
	logger.parser('\ndecoding routes in configuration')

	neighbor = neighbor[neighbor.keys()[0]]

	path = {}
	for f in NLRI.known_families():
		if neighbor.add_path:
			path[f] = neighbor.add_path

	capa = Capabilities().new(neighbor,False)
	capa[Capability.CODE.ADD_PATH] = path
	capa[Capability.CODE.MULTIPROTOCOL] = neighbor.families()
	# capa[Capability.CODE.FOUR_BYTES_ASN] = True

	routerid_1 = str(neighbor.router_id)
	routerid_2 = '.'.join(str((int(_)+1) % 250) for _ in str(neighbor.router_id).split('.',-1))

	o1 = Open(Version(4),ASN(neighbor.local_as),HoldTime(180),RouterID(routerid_1),capa)
	o2 = Open(Version(4),ASN(neighbor.peer_as),HoldTime(180),RouterID(routerid_2),capa)
	negotiated = Negotiated(neighbor)
	negotiated.sent(o1)
	negotiated.received(o2)
	# grouped = False

	while raw:
		if raw.startswith('\xff'*16):
			kind = ord(raw[18])
			size = (ord(raw[16]) << 16) + (ord(raw[17]))

			injected,raw = raw[19:size],raw[size:]

			if kind == 2:
				logger.parser('the message is an update')
				decoding = 'update'
			else:
				logger.parser('the message is not an update (%d) - aborting' % kind)
				return False
		else:
			logger.parser('header missing, assuming this message is ONE update')
			decoding = 'update'
			injected,raw = raw,''

		try:
			# This does not take the BGP header - let's assume we will not break that :)
			update = Update.unpack_message(injected,negotiated)
		except KeyboardInterrupt:
			raise
		except Notify:
			logger.parser('could not parse the message','error')
			logger.parser(traceback.format_exc(),'error')
			return False
		except StandardError:
			logger.parser('could not parse the message','error')
			logger.parser(traceback.format_exc(),'error')
			return False

		logger.parser('')  # new line
		for number in range(len(update.nlris)):
			change = Change(update.nlris[number],update.attributes)
			logger.parser('decoded %s %s %s' % (decoding,change.nlri.action,change.extensive()))
		logger.parser('update json %s' % Response.JSON(json_version).update(neighbor,'in',update,'',''))

	return True


# ================================================================= check_update
#

def check_notification (raw):
	notification = Notification.unpack_message(raw[18:],None)
	# XXX: FIXME: should be using logger here
	print notification
	return True
