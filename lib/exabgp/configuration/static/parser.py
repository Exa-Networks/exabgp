# encoding: utf-8
"""
inet/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import IPSelf
from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI

from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.nlri import CIDR
from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import IPVPN

from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.open import RouterID
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.attribute import NextHopSelf
from exabgp.bgp.message.update.attribute import Origin
from exabgp.bgp.message.update.attribute import MED
from exabgp.bgp.message.update.attribute import ASPath
from exabgp.bgp.message.update.attribute import LocalPreference
from exabgp.bgp.message.update.attribute import AtomicAggregate
from exabgp.bgp.message.update.attribute import Aggregator
from exabgp.bgp.message.update.attribute import Aggregator4
from exabgp.bgp.message.update.attribute import OriginatorID
from exabgp.bgp.message.update.attribute import ClusterID
from exabgp.bgp.message.update.attribute import ClusterList
from exabgp.bgp.message.update.attribute import AIGP
from exabgp.bgp.message.update.attribute import GenericAttribute

from exabgp.bgp.message.update.attribute.community.community import Community
from exabgp.bgp.message.update.attribute.community.communities import Communities
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities

from exabgp.bgp.message.update.nlri.qualifier import PathInfo

from exabgp.rib.change import Change


# XXX: The IP and CIDR class API is totally broken, fix it.
# XXX: Then add a similar class to the lot
# XXX: I could also say this from many of the NLRI classes constructor which need correct @classmethods


class Range (IP):  # XXX:  we do not need this class anymore and should just use CIDR
	def __init__ (self, ip, packed, mask):
		IP.init(self,ip,packed)
		self.mask = mask

	def __repr__ (self):
		return '%s/%d' % (self.top(),self.mask)


def prefix (tokeniser):
	# XXX: could raise
	ip = tokeniser()
	try:
		ip,mask = ip.split('/')
		mask = int(mask)
	except ValueError:
		mask = 32

	tokeniser.afi = IP.toafi(ip)
	return Range(ip,IP.pton(ip),mask)


def path_information (tokeniser):
	pi = tokeniser()
	if pi.isdigit():
		return PathInfo(integer=int(pi))
	else:
		return PathInfo(ip=pi)


def next_hop (tokeniser):
	value = tokeniser()

	if value.lower() == 'self':
		return IPSelf(tokeniser.afi),NextHopSelf(tokeniser.afi)
	else:
		ip = IP.create(value)
		if ip.afi == AFI.ipv4:
			return ip,NextHop(ip.top())
		return ip,None


def inet (tokeniser):
	ipmask = prefix(tokeniser)
	inet = INET(
		afi=IP.toafi(ipmask.top()),
		safi=IP.tosafi(ipmask.top()),
		action=OUT.UNSET
	)
	inet.cidr = CIDR(ipmask.ton(),ipmask.mask)

	return Change(
		inet,
		Attributes()
	)


def mpls (tokeniser):
	ipmask = prefix(tokeniser)
	mpls = IPVPN(
		afi=IP.toafi(ipmask.top()),
		safi=IP.tosafi(ipmask.top()),
		action=OUT.UNSET
	)
	mpls.cidr = CIDR(ipmask.ton(),ipmask.mask)

	return Change(
		mpls,
		Attributes()
	)


def attribute (tokeniser):
	start = tokeniser()
	if start != '[':
		raise ValueError('invalid attribute, does not starts with [')

	code = tokeniser().lower()
	if not code.startswith('0x'):
		raise ValueError('invalid attribute, code is not 0x hexadecimal')
	try:
		code = int(code,16)
	except ValueError:
		raise ValueError('invalid attribute, code is not 0x hexadecimal')

	flag = tokeniser().lower()
	if not flag.startswith('0x'):
		raise ValueError('invalid attribute, flag is not 0x hexadecimal')
	try:
		flag = int(flag,16)
	except ValueError:
		raise ValueError('invalid attribute, flag is not 0x hexadecimal')

	data = tokeniser().lower()
	if not data.startswith('0x'):
		raise ValueError('invalid attribute, data is not 0x hexadecimal')
	if len(data) % 2:
		raise ValueError('invalid attribute, data is not 0x hexadecimal')
	data = ''.join(chr(int(data[_:_+2],16)) for _ in range(2,len(data),2))

	end = tokeniser()
	if end != ']':
		raise ValueError('invalid attribute, does not ends with ]')

	return GenericAttribute(code,flag,data)

	# for ((ID,flag),klass) in Attribute.registered_attributes.iteritems():
	# 	length = len(data)
	# 	if code == ID and flag | Attribute.Flag.EXTENDED_LENGTH == klass.FLAG | Attribute.Flag.EXTENDED_LENGTH:
	# 		# if length > 0xFF or flag & Attribute.Flag.EXTENDED_LENGTH:
	# 		# 	raw = pack('!BBH',flag,code,length & (0xFF-Attribute.Flag.EXTENDED_LENGTH)) + data
	# 		# else:
	# 		# 	raw = pack('!BBB',flag,code,length) + data
	# 		return klass.unpack(data,None)


def aigp (tokeniser):
	if not tokeniser.tokens:
		raise ValueError('aigp requires number (decimal or hexadecimal 0x prefixed)')
	value = tokeniser()
	base = 16 if value.lower().startswith('0x') else 10
	try:
		number = int(value,base)
	except ValueError:
		raise ValueError('aigp requires number (decimal or hexadecimal 0x prefixed)')

	return AIGP('\x01\x00\x0b' + pack('!Q',number))


def origin (tokeniser):
	value = tokeniser().lower()
	if value == 'igp':
		return Origin(Origin.IGP)
	if value == 'egp':
		return Origin(Origin.EGP)
	if value == 'incomplete':
		return Origin(Origin.INCOMPLETE)
	raise ValueError('unknown origin %s' % value)


def med (tokeniser):
	value = tokeniser()
	if not value.isdigit():
		raise ValueError('invalid MED %s' % value)
	return MED(int(value))


def as_path (tokeniser):
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
						as_set.append(ASN.from_string(value))
				if value == ')':
					inset = False
					continue
				if value == ']':
					if inset:
						inset = False
						continue
					break
				as_seq.append(ASN.from_string(value))
		else:
			as_seq.append(ASN.from_string(value))
	except ValueError:
		raise ValueError('could not parse as-path')
	return ASPath(as_seq,as_set)


def local_preference (tokeniser):
	value = tokeniser()
	if not value.isdigit():
		raise ValueError('invalid local preference %s' % value)
	return LocalPreference(int(value))


def atomic_aggregate (tokeniser):
	return AtomicAggregate()


def aggregator (tokeniser):
	first = tokeniser.peek()
	eat = True if first == '(' else False

	if eat:
		tokeniser()

	try:
		as_number,address = tokeniser().split(':')
		local_as = ASN.from_string(as_number)
		local_address = RouterID(address)
	except (ValueError,IndexError):
		raise ValueError('invalid aggregator')

	if eat:
		if tokeniser() != ')':
			raise ValueError('invalid aggregator')

	# XXX: This could be buggy - check it
	if local_as.asn4():
		return Aggregator4(local_as,local_address)
	return Aggregator(local_as,local_address)


def originator_id (tokeniser):
	value = tokeniser()
	if value.count('.') != 3:
		raise ValueError('invalid Originator ID %s' % value)
	if not all(_.isdigit() for _ in value.split('.')):
		raise ValueError('invalid Originator ID %s' % value)
	return OriginatorID(value)


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

# XXX: Community does does not cache anymore .. we SHOULD really do it !


def _community (value):
	separator = value.find(':')
	if separator > 0:
		prefix = value[:separator]
		suffix = value[separator+1:]

		if not prefix.isdigit() or not suffix.isdigit():
			raise ValueError('invalid community %s' % value)

		prefix, suffix = int(prefix), int(suffix)

		if prefix > Community.MAX:
			raise ValueError('invalid community %s (prefix too large)' % value)

		if suffix > Community.MAX:
			raise ValueError('invalid community %s (suffix too large)' % value)

		return Community(pack('!L',(prefix << 16) + suffix))

	elif value[:2].lower() == '0x':
		number = long(value,16)
		if number > Community.MAX:
			raise ValueError('invalid community %s (too large)' % value)
		return Community(pack('!L',number))

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
		elif value.isdigit():
			number = int(value)
			if number > Community.MAX:
				raise ValueError('invalid community %s (too large)' % value)
			return Community(pack('!L',number))
		else:
			raise ValueError('invalid community name %s' % value)


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


_HEADER = {
	# header and subheader
	'target':              chr(0x00)+chr(0x02),
	'target4':             chr(0x02)+chr(0x02),
	'origin':              chr(0x00)+chr(0x03),
	'origin4':             chr(0x02)+chr(0x03),
	'redirect':            chr(0x80)+chr(0x08),
	'l2info':              chr(0x80)+chr(0x0A),
	'redirect-to-nexthop': chr(0x08)+chr(0x00),
}

_SIZE = {
	'target':              2,
	'target4':             2,
	'origin':              2,
	'origin4':             2,
	'redirect':            2,
	'l2info':              4,
	'redirect-to-nexthop': 0,
}

_SIZE_H = 0xFFFF


def _extended_community (value):
	if value[:2].lower() == '0x':
		# we could raise if the length is not 8 bytes (16 chars)
		if len(value) % 2:
			raise ValueError('invalid extended community %s' % value)
		raw = ''.join([chr(int(value[_:_+2],16)) for _ in range(2,len(value),2)])
		return ExtendedCommunity.unpack(raw)
	elif value.count(':'):
		components = value.split(':')
		command = 'target' if len(components) == 2 else components.pop(0)

		if command not in _HEADER:
			raise ValueError('invalid extended community %s (only origin,target or l2info are supported) ' % command)

		if len(components) != _SIZE[command]:
			raise ValueError('invalid extended community %s, expecting %d fields ' % (command,len(components)))

		header = _HEADER.get(command,None)

		if header is None:
			raise ValueError('unknown extended community %s' % command)

		if command == 'l2info':
			# encaps, control, mtu, site
			return ExtendedCommunity.unpack(header+pack('!BBHH',*[int(_) for _ in components]))

		_ga,_la = components
		ga,la = _ga.upper(),_la.upper()

		if command in ('target','origin'):
			# global admin, local admin
			if '.' in ga or '.' in la:
				gc = ga.count('.')
				lc = la.count('.')
				if gc == 0 and lc == 3:
					# ASN first, IP second
					return ExtendedCommunity.unpack(header+pack('!HBBBB',int(ga),*[int(_) for _ in la.split('.')]))
				if gc == 3 and lc == 0:
					# IP first, ASN second
					return ExtendedCommunity.unpack(header+pack('!BBBBH',*[int(_) for _ in ga.split('.')]+[int(la)]))

		iga = int(ga[:-1]) if 'L' in ga else int(ga)
		ila = int(la[:-1]) if 'L' in la else int(la)

		if command == 'target':
			if ga.endswith('L') or iga > _SIZE_H:
				return ExtendedCommunity.unpack(_HEADER['target4']+pack('!LH',iga,ila),None)
			else:
				return ExtendedCommunity.unpack(header+pack('!HI',iga,ila),None)
		if command == 'origin':
			if ga.endswith('L') or iga > _SIZE_H:
				return ExtendedCommunity.unpack(_HEADER['origin4']+pack('!LH',iga,ila),None)
			else:
				return ExtendedCommunity.unpack(header+pack('!HI',iga,ila),None)

		if command == 'target4':
			return ExtendedCommunity.unpack(_HEADER['target4']+pack('!LH',iga,ila),None)

		if command == 'orgin4':
			return ExtendedCommunity.unpack(_HEADER['origin4']+pack('!LH',iga,ila),None)

		if command in ('redirect',):
			return ExtendedCommunity.unpack(header+pack('!HL',iga,ila),None)

		raise ValueError('invalid extended community %s' % command)
	elif value == 'redirect-to-nexthop':
		header = _HEADER[value]
		return ExtendedCommunity.unpack(header+pack('!HL',0,0),None)
	else:
		raise ValueError('invalid extended community %s - lc+gc' % value)


# The previous code was extracting the extended-community class from the attributes
# And adding to it.

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


# Duck class, faking part of the Attribute interface
# We add this to routes when when need o split a route in smaller route
# The value stored is the longer netmask we want to use
# As this is not a real BGP attribute this stays in the configuration file


def name (tokeniser):
	class Name (str):
		ID = Attribute.CODE.INTERNAL_NAME

	return Name(tokeniser())


def split (tokeniser):
	class Split (int):
		ID = Attribute.CODE.INTERNAL_SPLIT

	cidr = tokeniser()

	if not cidr or cidr[0] != '/':
		raise ValueError('split /<number>')

	size = cidr[1:]

	if not size.isdigit():
		raise ValueError('split /<number>')

	return Split(int(size))


def watchdog (tokeniser):
	class Watchdog (str):
		ID = Attribute.CODE.INTERNAL_WATCHDOG

	command = tokeniser()
	if command.lower() in ['announce','withdraw']:
		raise ValueError('invalid watchdog name %s' % command)
	return Watchdog(command)


def withdraw (tokeniser=None):
	class Withdrawn (object):
		ID = Attribute.CODE.INTERNAL_WITHDRAW

	return Withdrawn()
