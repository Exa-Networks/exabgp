# encoding: utf-8
"""
parser.py

Created by Thomas Mangin on 2014-07-01.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# Generic ======================================================================
#

# As long as pack or unpack is needed here it means our API cleanup is not complete
from struct import pack
from struct import unpack

from socket import error as SocketError
from exabgp.protocol.ip import IP
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.routerid import RouterID
from exabgp.bgp.message.open.holdtime import HoldTime


def string (tokeniser):
	return tokeniser()


def boolean (tokeniser, default):
	value = tokeniser()
	status = value.lower()
	if status in ('true','enable','enabled'):
		value = True
	elif status in ('false','disable','disabled'):
		value = False
	elif status in ('unset',):
		value = None
	else:
		tokeniser.rewind(value)
		return default
	return value


def md5 (tokeniser):
	value = tokeniser()
	if len(value) > 80:
		raise ValueError('MD5 password must be no larger than 80 characters')
	if not value:
		raise ValueError('value requires the value password as an argument (quoted or unquoted).  FreeBSD users should use "kernel" as the argument.')
	return value


def ttl (tokeniser):
	value = tokeniser()

	# XXX: FIXME: Should it be a subclass of int ?
	try:
		attl = int(value)
	except ValueError:
		if value in ('false','disable','disabled'):
			return None
		raise ValueError('invalid ttl-security "%s"' % value)

	if attl < 0:
		raise ValueError('ttl-security can not be negative')
	if attl >= 255:
		raise ValueError('ttl must be smaller than 256')
	return attl


def asn (tokeniser, value=None):
	value = tokeniser() if value is None else value
	try:
		if value.count('.'):
			high,low = value.split('.',1)
			as_number = (int(high) << 16) + int(low)
		else:
			as_number = int(value)
		return ASN(as_number)
	except ValueError:
		raise ValueError('"%s" is an invalid ASN' % value)


def ip (tokeniser):
	value = tokeniser()
	try:
		return IP.create(value)
	except (IndexError,ValueError,SocketError):
		raise ValueError('"%s" is an invalid IP address' % value)


def routerid (tokeniser):
	return RouterID(tokeniser())


def holdtime (tokeniser):
	value = tokeniser()
	try:
		hold_time = HoldTime(value)
	except ValueError:
		raise ValueError ('"%s" is an invalid hold-time' % value)

	if hold_time < 3 and hold_time != 0:
		raise ValueError('holdtime must be zero or at least three seconds')
	# XXX: FIXME: add HoldTime.MAX and reference it ( pow -1 )
	if hold_time >= pow(2,16):
		raise ValueError('holdtime must be smaller than %d' % pow(2,16))
	return hold_time


# Attributes ===================================================================
#


# ==================================================================== Attribute
#

from exabgp.bgp.message.update.attribute.attribute import Attribute


def attribute (tokeniser):
	start = tokeniser()
	if start != '[':
		raise ValueError('invalid attribute, does not starts with [')

	code = tokeniser().lower()
	if not code.startswith('0x'):
		raise ValueError('invalid attribute, code is not 0x hexadecimal')
	try:
		code = int(code[2:],16)
	except ValueError:
		raise ValueError('invalid attribute, code is not 0x hexadecimal')

	flag = tokeniser().lower()
	if not flag.startswith('0x'):
		raise ValueError('invalid attribute, flag is not 0x hexadecimal')
	try:
		flag = int(flag[2:],16)
	except ValueError:
		raise ValueError('invalid attribute, flag is not 0x hexadecimal')

	data = tokeniser().lower()
	if not data.startswith('0x'):
		raise ValueError('invalid attribute, data is not 0x hexadecimal')
	if not len(data) % 2:
		raise ValueError('invalid attribute, data is not 0x hexadecimal')
	data = ''.join(chr(int(data[_:_+2],16)) for _ in range(2,len(data),2))

	end = tokeniser()
	if end != ']':
		raise ValueError('invalid attribute, does not ends with ]')

	# XXX: FIXME: class Attribute should have an unpack function which does that
	from exabgp.bgp.message.update.attribute.generic import GenericAttribute

	for ((ID,flag),klass) in Attribute.registered_attributes.iteritems():
		if code == ID and flag == klass.FLAG:
			return klass(data)
	return GenericAttribute(code,flag,data)


# ====================================================================== NextHop
#

from exabgp.bgp.message.update.attribute.nexthop import NextHop


def next_hop (tokeniser):
	value = tokeniser()
	if value.lower() == 'self':
		# next-hop self is unsupported yet
		raise ValueError('unsupported yet on new format')
	else:
		return NextHop(value)


# ======================================================================= Origin
#

from exabgp.bgp.message.update.attribute.origin import Origin


def origin (tokeniser):
	value = tokeniser().lower()
	if value == 'igp':
		return Origin(Origin.IGP)
	if value == 'egp':
		return Origin(Origin.EGP)
	if value == 'incomplete':
		return Origin(Origin.INCOMPLETE)
	raise ValueError('unknown origin %s' % value)


# ========================================================================== MED
#

from exabgp.bgp.message.update.attribute.med import MED


def med (tokeniser):
	value = tokeniser()
	if not value.isdigit():
		raise ValueError('invalid MED %s' % value)
	return MED(value)


# ======================================================================= ASPath
#

from exabgp.bgp.message.update.attribute.aspath import ASPath


def aspath (tokeniser):
	as_seq = []
	as_set = []
	value = tokeniser()
	inset = False
	try:
		if value == '[':
			while True:
				value = tokeniser()
				if value == ',':
					continue
				if value in ('(','['):
					inset = True
					while True:
						value = tokeniser()
						if value == ')':
							break
						as_set.append(asn(tokeniser,value))
				if value == ')':
					inset = False
					continue
				if value == ']':
					if inset:
						inset = False
						continue
					break
				as_seq.append(ASN(tokeniser,value))
		else:
			as_seq.append(asn(tokeniser,value))
	except ValueError:
		raise ValueError('could not parse as-path')
	return ASPath(as_seq,as_set)


# ============================================================== LocalPreference
#

from exabgp.bgp.message.update.attribute.localpref import LocalPreference


def local_preference (tokeniser):
	value = tokeniser()
	if not value.isdigit():
		raise ValueError('invalid local preference %s' % value)
	return LocalPreference(value)


# ==================================================================== Community
#

from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate


def atomic_aggregate (tokeniser):
	return AtomicAggregate()


# =================================================================== Aggregator
#

from exabgp.bgp.message.update.attribute.aggregator import Aggregator


def aggregator (tokeniser):
	value = tokeniser()
	if value != '(':
		tokeniser.rewind(value)
		return None

	try:
		as_number,address = tokeniser().split(':')
	except (ValueError,IndexError):
		raise ValueError('invalid aggregator')

	value = tokeniser()
	if value != ')':
		raise ValueError('invalid aggregator')

	local_as = ASN(as_number)
	local_address = RouterID(address)

	# XXX: This is buggy it can be an Aggregator4
	return Aggregator(local_as,local_address)


# ================================================================= OriginatorID
#

from exabgp.bgp.message.update.attribute.originatorid import OriginatorID


def originator_id (tokeniser):
	value = tokeniser()
	if not value.isdigit():
		raise ValueError('invalid Originator ID %s' % value)
	return OriginatorID(value)


# ================================================================== ClusterList
#

from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
from exabgp.bgp.message.update.attribute.clusterlist import ClusterID


def cluster_list (tokeniser):
	clusterids = []
	value = tokeniser()
	try:
		if value == '[':
			while True:
				value = tokeniser()
				if value == ']':
					break
				clusterids.append(ClusterID(value))
		else:
			clusterids.append(ClusterID(value))
		if not clusterids:
			raise ValueError('no cluster-id in the cluster list')
		return ClusterList(clusterids)
	except ValueError:
		raise ValueError('invalud cluster list')


# ==================================================================== Community
#

from exabgp.bgp.message.update.attribute.community.community import Community


def _community (value):
	separator = value.find(':')
	if separator > 0:
		prefix = value[:separator]
		suffix = value[separator+1:]

		if not prefix.isdigit() or not suffix.isdigit():
			raise ValueError('invalid community %s' % value)

		prefix, suffix = int(prefix), int(suffix)

		# XXX: FIXME: add a Community.MAX to pow(2,16) -1
		if prefix >= pow(2,16):
			raise ValueError('invalid community %s (prefix too large)' % value)

		# XXX: FIXME: add a Community.MAX to pow(2,16) -1
		if suffix >= pow(2,16):
			raise ValueError('invalid community %s (suffix too large)' % value)

		return Community(pack('!L',(prefix << 16) + suffix))

	elif value[:2].lower() == '0x':
		value = long(value,16)
		# XXX: FIXME: add a Community.MAX to pow(2,16) -1
		if value >= pow(2,32):
			raise ValueError('invalid community %s (too large)' % value)
		return Community(pack('!L',value))
	else:
		low = value.lower()
		if low == 'no-export':
			return Community(Community.NO_EXPORT)
		elif low == 'no-advertise':
			return Community(Community.NO_ADVERTISE)
		elif low == 'no-export-subconfed':
			return Community(Community.NO_EXPORT_SUBCONFED)
		# no-peer is not a correct syntax but I am sure someone will make the mistake :)
		elif low == 'nopeer' or low == 'no-peer':
			return Community(Community.NO_PEER)
		elif low == 'blackhole':
			return Community(Community.BLACKHOLE)
		elif value.isdigit():
			value = unpack('!L',value)[0]
			if value >= pow(2,32):
				raise ValueError('invalid community %s (too large)' % value)
			return Community(pack('!L',value))
		else:
			raise ValueError('invalid community name %s' % value)


from exabgp.bgp.message.update.attribute.community.communities import Communities


def community (tokeniser):
	communities = Communities()

	value = tokeniser()
	if value == '[':
		while True:
			value = tokeniser()
			if value == ']':
				break
			communities.add(_community(value))
	else:
		communities.add(_community(value))

	return communities


# ========================================================== ExtendedCommunities
#

from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunity


def _extended_community (value):
	if value[:2].lower() == '0x':
		if not len(value) % 2:
			raise ValueError('invalid extended community %s' % value)
		try:
			raw = ''
			for i in range(2,len(value),2):
				raw += chr(int(value[i:i+2],16))
		except ValueError:
			raise ValueError('invalid extended community %s' % value)
		if len(raw) != 8:
			raise ValueError('invalid extended community %s' % value)
		return ExtendedCommunity.unpack(raw)
	elif value.count(':'):
		_known_community = {
			# header and subheader
			'target':  chr(0x00)+chr(0x02),
			'target4': chr(0x02)+chr(0x02),
			'origin':  chr(0x00)+chr(0x03),
			'origin4': chr(0x02)+chr(0x03),
			'l2info':  chr(0x80)+chr(0x0A),
		}

		_size_community = {
			'target':  2,
			'target4': 2,
			'origin':  2,
			'origin4': 2,
			'l2info':  4,
		}

		components = value.split(':')
		command = 'target' if len(components) == 2 else components.pop(0)

		if command not in _known_community:
			raise ValueError('invalid extended community %s (only origin,target or l2info are supported) ' % command)

		if len(components) != _size_community[command]:
			raise ValueError('invalid extended community %s, expecting %d fields ' % (command,len(components)))

		header = _known_community[command]

		if command == 'l2info':
			# encaps, control, mtu, site
			return ExtendedCommunity.unpack(header+pack('!BBHH',*[int(_) for _ in components]))

		if command in ('target','origin'):
			# global admin, local admin
			ga,la = components

			if '.' in ga or '.' in la:
				gc = ga.count('.')
				lc = la.count('.')
				if gc == 0 and lc == 3:
					# ASN first, IP second
					return ExtendedCommunity.unpack(header+pack('!HBBBB',int(ga),*[int(_) for _ in la.split('.')]))
				if gc == 3 and lc == 0:
					# IP first, ASN second
					return ExtendedCommunity.unpack(header+pack('!BBBBH',*[int(_) for _ in ga.split('.')]+[int(la)]))
			else:
				if command == 'target':
					if ga.upper().endswith('L'):
						return ExtendedCommunity.unpack(_known_community['target4']+pack('!LH',int(ga[:-1]),int(la)))
					else:
						return ExtendedCommunity.unpack(header+pack('!HI',int(ga),int(la)))
				if command == 'origin':
					if ga.upper().endswith('L'):
						return ExtendedCommunity.unpack(_known_community['origin4']+pack('!LH',int(ga),int(la)))
					else:
						return ExtendedCommunity.unpack(header+pack('!HI',int(ga),int(la)))

			if command == 'target4':
				return ExtendedCommunity.unpack(_known_community['target4']+pack('!LH',int(ga[:-1]),int(la)),None)

			if command == 'orgin4':
				return ExtendedCommunity.unpack(_known_community['origin4']+pack('!LH',int(ga[:-1]),int(la)),None)

		raise ValueError('invalid extended community %s' % command)
	else:
		raise ValueError('invalid extended community %s - lc+gc' % value)


# This is the same code as community with a different parser, should be factored

from exabgp.bgp.message.update.attribute.community.extended.communities import ExtendedCommunities


def extended_community (tokeniser):
	communities = ExtendedCommunities()

	value = tokeniser()
	if value == '[':
		while True:
			value = tokeniser()
			if value == ']':
				break
			communities.add(_extended_community(value))
	else:
		communities.add(_extended_community(value))

	return communities


# ===================================================== Fake Attribute: Watchdog
#

def watchdog (tokeniser):
	class Watchdog (str):
		ID = Attribute.CODE.INTERNAL_WATCHDOG

	command = tokeniser()
	if command.lower() in ['announce','withdraw']:
		raise ValueError('invalid watchdog name %s' % command)
	return Watchdog(command)


# ===================================================== Fake Attribute: Withdraw
#

def withdraw (tokeniser=None):
	class Withdrawn (object):
		ID = Attribute.CODE.INTERNAL_WITHDRAW
	return Withdrawn()


# Qualifiers ===================================================================
#


# =========================================================== RouteDistinguisher
#

from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher


def rd (tokeniser):
	try:
		value = tokeniser()

		separator = value.find(':')
		if separator > 0:
			prefix = value[:separator]
			suffix = int(value[separator+1:])

		# XXX: FIXME: we need much more checks here instead that the blank try/except...

		if '.' in prefix:
			data = [chr(0),chr(1)]
			data.extend([chr(int(_)) for _ in prefix.split('.')])
			data.extend([chr(suffix >> 8),chr(suffix & 0xFF)])
			distinguisher = ''.join(data)
		else:
			number = int(prefix)
			if number < pow(2,16) and suffix < pow(2,32):
				distinguisher = chr(0) + chr(0) + pack('!H',number) + pack('!L',suffix)
			elif number < pow(2,32) and suffix < pow(2,16):
				distinguisher = chr(0) + chr(2) + pack('!L',number) + pack('!H',suffix)
			else:
				raise ValueError('invalid route-distinguisher %s' % value)
	except ValueError:
		raise ValueError('invalid route-distinguisher %s' % value)

	return RouteDistinguisher(distinguisher)


# ============================================================== PathInformation
#

from exabgp.bgp.message.update.nlri.qualifier.path import PathInfo


def path_information (tokeniser):
	try:
		pi = tokeniser()
		if pi.isdigit():
			return PathInfo(integer=int(pi))
		return PathInfo(ip=pi)
	except ValueError:
		raise ValueError('invaluid path-information')


# ============================================================== PathInformation
#

from exabgp.bgp.message.update.nlri.qualifier.labels import Labels


def label (tokeniser):
	labels = []
	value = tokeniser()
	try:
		if value == '[':
			while True:
				value = tokeniser()
				if value == ']':
					break
				labels.append(int(value))
		else:
			labels.append(int(value))
	except ValueError:
		raise ValueError('invalid label %s' % value)

	return Labels(labels)
