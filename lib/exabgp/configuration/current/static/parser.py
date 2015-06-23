# encoding: utf-8
"""
inet/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI

from exabgp.bgp.message import OUT
from exabgp.bgp.message.update.nlri import INET

from exabgp.bgp.message.open import ASN
from exabgp.bgp.message.open import RouterID
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.attribute import Origin
from exabgp.bgp.message.update.attribute import MED
from exabgp.bgp.message.update.attribute import ASPath
from exabgp.bgp.message.update.attribute import LocalPreference
from exabgp.bgp.message.update.attribute import AtomicAggregate
from exabgp.bgp.message.update.attribute import Aggregator
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


class Range (IP):
	def __init__ (self, ip, packed, mask):
		IP.init(self,ip,packed)
		self.mask = mask


def prefix (tokeniser):
	# XXX: could raise
	ip = tokeniser()
	try:
		ip,mask = ip.split('/')
		mask = int(mask)
	except ValueError:
		mask = 32

	return Range(ip,IP.pton(ip),mask)


def path_information (tokeniser):
	pi = tokeniser()
	if pi.isdigit():
		return PathInfo(integer=int(pi))
	else:
		return PathInfo(ip=pi)


def next_hop (tokeniser,nexthopself=None):
	value = tokeniser()

	if value.lower() == 'self' and nexthopself is None:
		raise ValueError('unsupported yet on new format')
	else:
		ip = IP.create(value)
		if ip.afi == AFI.ipv4:
			return ip,NextHop(ip.string)
		return ip,None


def inet (tokeniser):
	ipmask = prefix(tokeniser)
	return Change(
		INET(
			afi=IP.toafi(ipmask.string),
			safi=IP.tosafi(ipmask.string),
			packed=IP.pton(ipmask.string),
			mask=ipmask.mask,
			nexthop=None,
			action=OUT.ANNOUNCE
		),
		Attributes()
	)


# def aigp (self, name, command, tokens):
# 	try:
# 		number = tokens.pop(0)
# 		base = 16 if number.lower().startswith('0x') else 10
# 		self.scope.content[-1]['announce'][-1].attributes.add(AIGP('\x01\x00\x0b' + pack('!Q',int(number,base))))
# 		return True
# 	except (IndexError,ValueError):
# 		return self.error.set(self.syntax)

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
	if len(data) % 2:
		raise ValueError('invalid attribute, data is not 0x hexadecimal')
	data = ''.join(chr(int(data[_:_+2],16)) for _ in range(2,len(data),2))

	end = tokeniser()
	if end != ']':
		raise ValueError('invalid attribute, does not ends with ]')

	for ((ID,flag),klass) in Attribute.registered_attributes.iteritems():
		if code == ID and flag == klass.FLAG:
			return klass(data)
	return GenericAttribute(code,flag,data)


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
	eat = True if tokeniser.tokens[0] == '(' else False

	if eat:
		tokeniser()

	value = tokeniser()
	if value != '(':
		tokeniser.rewind(value)
		return None

	try:
		as_number,address = tokeniser().split(':')
		local_as = ASN.from_string(as_number)
		local_address = RouterID(address)
	except (ValueError,IndexError):
		raise ValueError('invalid aggregator')

	if eat:
		value = tokeniser()
		if value != ')':
			raise ValueError('invalid aggregator')

	# XXX: This is buggy it can be an Aggregator4
	return Aggregator(local_as,local_address)


def originator_id (tokeniser):
	value = tokeniser()
	if value.count('.') != 3:
		raise ValueError('invalid Originator ID %s' % value)
	if not all(_.isdigit() for _ in value.split('.')):
		raise ValueError('invalid Originator ID %s' % value)
	return OriginatorID(value)



# def cluster_list (self, name, command, tokens):
# 	_list = []
# 	clusterid = tokens.pop(0)
# 	try:
# 		if clusterid == '[':
# 			while True:
# 				try:
# 					clusterid = tokens.pop(0)
# 				except IndexError:
# 					return self.error.set(self.syntax)
# 				if clusterid == ']':
# 					break
# 				_list.append(ClusterID(clusterid))
# 		else:
# 			_list.append(ClusterID(clusterid))
# 		if not _list:
# 			return self.error.set('no cluster-id in the cluster-list')
# 		clusterlist = ClusterList(_list)
# 	except ValueError:
# 		return self.error.set(self.syntax)
# 	self.scope.content[-1]['announce'][-1].attributes.add(clusterlist)
# 	return True


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


# def _parse_community (self,data):
# 	separator = data.find(':')
# 	if separator > 0:
# 		prefix = int(data[:separator])
# 		suffix = int(data[separator+1:])
# 		if prefix >= pow(2,16):
# 			raise ValueError('invalid community %s (prefix too large)' % data)
# 		if suffix >= pow(2,16):
# 			raise ValueError('invalid community %s (suffix too large)' % data)
# 		return Community.cached(pack('!L',(prefix << 16) + suffix))
# 	elif len(data) >= 2 and data[1] in 'xX':
# 		value = long(data,16)
# 		if value >= pow(2,32):
# 			raise ValueError('invalid community %s (too large)' % data)
# 		return Community.cached(pack('!L',value))
# 	else:
# 		low = data.lower()
# 		if low == 'no-export':
# 			return Community.cached(Community.NO_EXPORT)
# 		elif low == 'no-advertise':
# 			return Community.cached(Community.NO_ADVERTISE)
# 		elif low == 'no-export-subconfed':
# 			return Community.cached(Community.NO_EXPORT_SUBCONFED)
# 		# no-peer is not a correct syntax but I am sure someone will make the mistake :)
# 		elif low == 'nopeer' or low == 'no-peer':
# 			return Community.cached(Community.NO_PEER)
# 		elif data.isdigit():
# 			value = long(data)
# 			if value >= pow(2,32):
# 				raise ValueError('invalid community %s (too large)' % data)
# 				# return Community.cached(pack('!L',value))
# 			return Community.cached(pack('!L',value))
# 		else:
# 			raise ValueError('invalid community name %s' % data)


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



# def community (self, name, command, tokens):
# 	communities = Communities()
# 	community = tokens.pop(0)
# 	try:
# 		if community == '[':
# 			while True:
# 				try:
# 					community = tokens.pop(0)
# 				except IndexError:
# 					return self.error.set(self.syntax)
# 				if community == ']':
# 					break
# 				communities.add(self._parse_community(community))
# 		else:
# 			communities.add(self._parse_community(community))
# 	except ValueError:
# 		return self.error.set(self.syntax)
# 	self.scope.content[-1]['announce'][-1].attributes.add(communities)
# 	return True


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


# def _parse_extended_community (self,data):
# 	SIZE_H = 0xFFFF
#
# 	if data[:2].lower() == '0x':
# 		try:
# 			raw = ''
# 			for i in range(2,len(data),2):
# 				raw += chr(int(data[i:i+2],16))
# 		except ValueError:
# 			raise ValueError('invalid extended community %s' % data)
# 		if len(raw) != 8:
# 			raise ValueError('invalid extended community %s' % data)
# 		return ExtendedCommunity.unpack(raw,None)
# 	elif data.count(':'):
# 		_known_community = {
# 			# header and subheader
# 			'target':   chr(0x00)+chr(0x02),
# 			'target4':  chr(0x02)+chr(0x02),
# 			'origin':   chr(0x00)+chr(0x03),
# 			'origin4':  chr(0x02)+chr(0x03),
# 			'redirect': chr(0x80)+chr(0x08),
# 			'l2info':   chr(0x80)+chr(0x0A),
# 		}
#
# 		_size_community = {
# 			'target':   2,
# 			'target4':  2,
# 			'origin':   2,
# 			'origin4':  2,
# 			'redirect': 2,
# 			'l2info':   4,
# 		}
#
# 		components = data.split(':')
# 		command = 'target' if len(components) == 2 else components.pop(0)
#
# 		if command not in _known_community:
# 			raise ValueError('invalid extended community %s (only origin,target or l2info are supported) ' % command)
#
# 		if len(components) != _size_community[command]:
# 			raise ValueError('invalid extended community %s, expecting %d fields ' % (command,len(components)))
#
# 		header = _known_community[command]
#
# 		if command == 'l2info':
# 			# encaps, control, mtu, site
# 			return ExtendedCommunity.unpack(header+pack('!BBHH',*[int(_) for _ in components]),None)
#
# 		if command in ('target','origin'):
# 			# global admin, local admin
# 			_ga,_la = components
# 			ga,la = _ga.upper(),_la.upper()
#
# 			if '.' in ga or '.' in la:
# 				gc = ga.count('.')
# 				lc = la.count('.')
# 				if gc == 0 and lc == 3:
# 					# ASN first, IP second
# 					return ExtendedCommunity.unpack(header+pack('!HBBBB',int(ga),*[int(_) for _ in la.split('.')]),None)
# 				if gc == 3 and lc == 0:
# 					# IP first, ASN second
# 					return ExtendedCommunity.unpack(header+pack('!BBBBH',*[int(_) for _ in ga.split('.')]+[int(la)]),None)
# 			else:
# 				iga = int(ga[:-1]) if 'L' in ga else int(ga)
# 				ila = int(la[:-1]) if 'L' in la else int(la)
# 				if command == 'target':
# 					if ga.endswith('L') or iga > SIZE_H:
# 						return ExtendedCommunity.unpack(_known_community['target4']+pack('!LH',iga,ila),None)
# 					else:
# 						return ExtendedCommunity.unpack(header+pack('!HI',iga,ila),None)
# 				if command == 'origin':
# 					if ga.endswith('L') or iga > SIZE_H:
# 						return ExtendedCommunity.unpack(_known_community['origin4']+pack('!LH',iga,ila),None)
# 					else:
# 						return ExtendedCommunity.unpack(header+pack('!HI',iga,ila),None)
#
# 		if command == 'target4':
# 			iga = int(ga[:-1]) if 'L' in ga else int(ga)
# 			ila = int(la[:-1]) if 'L' in la else int(la)
# 			return ExtendedCommunity.unpack(_known_community['target4']+pack('!LH',iga,ila),None)
#
# 		if command == 'orgin4':
# 			iga = int(ga[:-1]) if 'L' in ga else int(ga)
# 			ila = int(la[:-1]) if 'L' in la else int(la)
# 			return ExtendedCommunity.unpack(_known_community['origin4']+pack('!LH',iga,ila),None)
#
# 		if command in ('redirect',):
# 			ga,la = components
# 			return ExtendedCommunity.unpack(header+pack('!HL',int(ga),long(la)),None)
#
# 		raise ValueError('invalid extended community %s' % command)
# 	else:
# 		raise ValueError('invalid extended community %s - lc+gc' % data)


def _extended_community (value):
	if value[:2].lower() == '0x':
		if len(value) % 2:
			raise ValueError('invalid extended community %s' % value)
		raw = ''.join([chr(int(value[_:_+2],16)) for _ in range(2,len(value),2)])
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

# def extended_community (self, name, command, tokens):
# 	attributes = self.scope.content[-1]['announce'][-1].attributes
# 	if Attribute.CODE.EXTENDED_COMMUNITY in attributes:
# 		extended_communities = attributes[Attribute.CODE.EXTENDED_COMMUNITY]
# 	else:
# 		extended_communities = ExtendedCommunities()
# 		attributes.add(extended_communities)
#
# 	extended_community = tokens.pop(0)
# 	try:
# 		if extended_community == '[':
# 			while True:
# 				try:
# 					extended_community = tokens.pop(0)
# 				except IndexError:
# 					return self.error.set(self.syntax)
# 				if extended_community == ']':
# 					break
# 				extended_communities.add(self._parse_extended_community(extended_community))
# 		else:
# 			extended_communities.add(self._parse_extended_community(extended_community))
# 	except ValueError:
# 		return self.error.set(self.syntax)
# 	return True
#

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

# def watchdog (self, name, command, tokens):
# 	try:
# 		w = tokens.pop(0)
# 		if w.lower() in ['announce','withdraw']:
# 			raise ValueError('invalid watchdog name %s' % w)
# 	except IndexError:
# 		return self.error.set(self.syntax)
#
# 	try:
# 		self.scope.content[-1]['announce'][-1].attributes.add(Watchdog(w))
# 		return True
# 	except ValueError:
# 		return self.error.set(self.syntax)


def withdraw (tokeniser=None):
	class Withdrawn (object):
		ID = Attribute.CODE.INTERNAL_WITHDRAW

	return Withdrawn()
