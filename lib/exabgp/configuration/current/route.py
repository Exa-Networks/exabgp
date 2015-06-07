# encoding: utf-8
"""
parse_route.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from struct import pack

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.protocol.ip import IP
from exabgp.protocol.ip import NoNextHop

from exabgp.bgp.message import OUT
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.routerid import RouterID

from exabgp.bgp.message.update.nlri import INET
from exabgp.bgp.message.update.nlri import MPLS

from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import PathInfo

from exabgp.bgp.message.update.attribute import Attribute
from exabgp.bgp.message.update.attribute import Attributes

from exabgp.bgp.message.update.attribute import Origin
from exabgp.bgp.message.update.attribute import NextHop
from exabgp.bgp.message.update.attribute import ASPath
from exabgp.bgp.message.update.attribute import MED
from exabgp.bgp.message.update.attribute import LocalPreference
from exabgp.bgp.message.update.attribute import AtomicAggregate
from exabgp.bgp.message.update.attribute import Aggregator

from exabgp.bgp.message.update.attribute.community.community import Community
from exabgp.bgp.message.update.attribute.community.communities import Communities
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities

from exabgp.bgp.message.update.attribute import OriginatorID
from exabgp.bgp.message.update.attribute import ClusterID
from exabgp.bgp.message.update.attribute import ClusterList
from exabgp.bgp.message.update.attribute import AIGP
from exabgp.bgp.message.update.attribute import GenericAttribute

from exabgp.rib.change import Change

from exabgp.configuration.current.basic import Basic
from exabgp.configuration.current.basic import Split
from exabgp.configuration.current.basic import Withdrawn
from exabgp.configuration.current.basic import Watchdog
from exabgp.configuration.current.basic import Name


# Take an integer an created it networked packed representation for the right family (ipv4/ipv6)
def pack_int (afi, integer, mask):
	return ''.join([chr((integer >> (offset * 8)) & 0xff) for offset in range(IP.length(afi)-1,-1,-1)])


class ParseRoute (Basic):
	syntax = \
		'community, extended-communities and as-path can take a single community as parameter.\n' \
		'only next-hop is mandatory\n' \
		'\n' \
		'syntax:\n' \
		'route 10.0.0.1/22 {\n' \
		'   path-information 0.0.0.1;\n' \
		'   route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535' \
		'   next-hop 192.0.1.254;\n' \
		'   origin IGP|EGP|INCOMPLETE;\n' \
		'   as-path [ AS-SEQUENCE-ASN1 AS-SEQUENCE-ASN2 ( AS-SET-ASN3 )] ;\n' \
		'   med 100;\n' \
		'   local-preference 100;\n' \
		'   atomic-aggregate;\n' \
		'   community [ 65000 65001 65002 ];\n' \
		'   extended-community [ target:1234:5.6.7.8 target:1.2.3.4:5678 origin:1234:5.6.7.8 origin:1.2.3.4:5678 0x0002FDE800000001 ]\n' \
		'   originator-id 10.0.0.10;\n' \
		'   cluster-list [ 10.10.0.1 10.10.0.2 ];\n' \
		'   label [ 100 200 ];\n' \
		'   aggregator ( 65000:10.0.0.10 )\n' \
		'   aigp 100;\n' \
		'   split /24\n' \
		'   watchdog watchdog-name\n' \
		'   withdraw\n' \
		'}\n' \
		'\n' \
		'syntax:\n' \
		'route 10.0.0.1/22' \
		' path-information 0.0.0.1' \
		' route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535' \
		' next-hop 192.0.2.1' \
		' origin IGP|EGP|INCOMPLETE' \
		' as-path AS-SEQUENCE-ASN' \
		' med 100' \
		' local-preference 100' \
		' atomic-aggregate' \
		' community 65000' \
		' extended-community target:1234:5.6.7.8' \
		' originator-id 10.0.0.10' \
		' cluster-list 10.10.0.1' \
		' label 150' \
		' aggregator ( 65000:10.0.0.10 )' \
		' aigp 100' \
		' split /24' \
		' watchdog watchdog-name' \
		' withdraw' \
		' name what-you-want-to-remember-about-the-route' \
		';\n'

	def __init__ (self, error):
		self.error = error
		self._nexthopself = None

		self.command = {
			'origin':              self.origin,
			'as-path':             self.aspath,
			'med':                 self.med,
			'aigp':                self.aigp,
			'next-hop':            self.next_hop,
			'local-preference':    self.local_preference,
			'atomic-aggregate':    self.atomic_aggregate,
			'aggregator':          self.aggregator,
			'path-information':    self.path_information,
			'originator-id':       self.originator_id,
			'cluster-list':        self.cluster_list,
			'split':               self.split,
			'label':               self.label,
			'rd':                  self.rd,
			'route-distinguisher': self.rd,
			'watchdog':            self.watchdog,
			'withdraw':            self.withdraw,
			'name':                self.name,
			'community':           self.community,
			'extended-community':  self.extended_community,
			'attribute':           self.generic_attribute,
		}

	def clear (self):
		self._nexthopself = None

	def nexthop (self, nexthopself):
		self._nexthopself = nexthopself

	def watchdog (self, scope, command, tokens):
		try:
			w = tokens.pop(0)
			if w.lower() in ['announce','withdraw']:
				raise ValueError('invalid watchdog name %s' % w)
		except IndexError:
			return self.error.set(self.syntax)

		try:
			scope[-1]['announce'][-1].attributes.add(Watchdog(w))
			return True
		except ValueError:
			return self.error.set(self.syntax)

	def withdraw (self, scope, command, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(Withdrawn())
			return True
		except ValueError:
			return self.error.set(self.syntax)

	# Route name

	def name (self, scope, command, tokens):
		try:
			w = tokens.pop(0)
		except IndexError:
			return self.error.set(self.syntax)

		try:
			scope[-1]['announce'][-1].attributes.add(Name(w))
			return True
		except ValueError:
			return self.error.set(self.syntax)

	# Command Route

	def generic_attribute (self, scope, command, tokens):
		try:
			start = tokens.pop(0)
			code = tokens.pop(0).lower()
			flag = tokens.pop(0).lower()
			data = tokens.pop(0).lower()
			end = tokens.pop(0)

			if (start,end) != ('[',']'):
				return self.error.set(self.syntax)

			if not code.startswith('0x'):
				return self.error.set(self.syntax)
			code = int(code[2:],16)

			if not flag.startswith('0x'):
				return self.error.set(self.syntax)
			flag = int(flag[2:],16)

			if not data.startswith('0x'):
				return self.error.set(self.syntax)
			raw = ''
			for i in range(2,len(data),2):
				raw += chr(int(data[i:i+2],16))

			try:
				for ((ID,_),klass) in Attribute.registered_attributes.iteritems():
					if code == ID and flag == klass.FLAG:
						scope[-1]['announce'][-1].attributes.add(klass.unpack(raw,None))
						return True
			except Exception:
				pass

			scope[-1]['announce'][-1].attributes.add(GenericAttribute(code,flag,raw))
			return True
		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def next_hop (self, scope, command, tokens):
		if scope[-1]['announce'][-1].attributes.has(Attribute.CODE.NEXT_HOP):
			return self.error.set(self.syntax)

		try:
			# next-hop self is unsupported
			ip = tokens.pop(0)
			if ip.lower() == 'self':
				if 'local-address' in scope[-1]:
					la = scope[-1]['local-address']
				elif self._nexthopself:
					la = self._nexthopself
				else:
					return self.error.set('next-hop self can only be specified with a neighbor')
				nh = IP.unpack(la.pack())
			else:
				nh = IP.create(ip)

			change = scope[-1]['announce'][-1]
			nlri = change.nlri
			afi = nlri.afi
			safi = nlri.safi

			nlri.nexthop = nh

			if afi == AFI.ipv4 and safi in (SAFI.unicast,SAFI.multicast):
				change.attributes.add(Attribute.unpack(NextHop.ID,NextHop.FLAG,nh.packed,None))
				# NextHop(nh.ip,nh.packed) does not cache the result, using unpack does
				# change.attributes.add(NextHop(nh.ip,nh.packed))

			return True
		except Exception:
			return self.error.set(self.syntax)

	def origin (self, scope, command, tokens):
		try:
			data = tokens.pop(0).lower()
			if data == 'igp':
				scope[-1]['announce'][-1].attributes.add(Origin(Origin.IGP))
				return True
			if data == 'egp':
				scope[-1]['announce'][-1].attributes.add(Origin(Origin.EGP))
				return True
			if data == 'incomplete':
				scope[-1]['announce'][-1].attributes.add(Origin(Origin.INCOMPLETE))
				return True
			return self.error.set(self.syntax)
		except IndexError:
			return self.error.set(self.syntax)

	def aspath (self, scope, command, tokens):
		as_seq = []
		as_set = []
		asn = tokens.pop(0)
		inset = False
		try:
			if asn == '[':
				while True:
					try:
						asn = tokens.pop(0)
					except IndexError:
						return self.error.set(self.syntax)
					if asn == ',':
						continue
					if asn in ('(','['):
						inset = True
						while True:
							try:
								asn = tokens.pop(0)
							except IndexError:
								return self.error.set(self.syntax)
							if asn == ')':
								break
							as_set.append(Basic.newASN(asn))
					if asn == ')':
						inset = False
						continue
					if asn == ']':
						if inset:
							inset = False
							continue
						break
					as_seq.append(Basic.newASN(asn))
			else:
				as_seq.append(Basic.newASN(asn))
		except (IndexError,ValueError):
			return self.error.set(self.syntax)
		scope[-1]['announce'][-1].attributes.add(ASPath(as_seq,as_set))
		return True

	def med (self, scope, command, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(MED(int(tokens.pop(0))))
			return True
		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def aigp (self, scope, command, tokens):
		try:
			number = tokens.pop(0)
			base = 16 if number.lower().startswith('0x') else 10
			scope[-1]['announce'][-1].attributes.add(AIGP('\x01\x00\x0b' + pack('!Q',int(number,base))))
			return True
		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def local_preference (self, scope, command, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(LocalPreference(int(tokens.pop(0))))
			return True
		except (IndexError,ValueError):
			return self.error.set(self.syntax)

	def atomic_aggregate (self, scope, command, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(AtomicAggregate())
			return True
		except ValueError:
			return self.error.set(self.syntax)

	def aggregator (self, scope, command, tokens):
		try:
			if tokens:
				if tokens.pop(0) != '(':
					raise ValueError('invalid aggregator syntax')
				asn,address = tokens.pop(0).split(':')
				if tokens.pop(0) != ')':
					raise ValueError('invalid aggregator syntax')
				local_as = ASN(asn)
				local_address = RouterID(address)
			else:
				local_as = scope[-1]['local-as']
				local_address = scope[-1]['local-address']
		except (ValueError,IndexError):
			return self.error.set(self.syntax)
		except KeyError:
			return self.error('local-as and/or local-address missing from neighbor/group to make aggregator')
		except ValueError:
			return self.error.set(self.syntax)

		scope[-1]['announce'][-1].attributes.add(Aggregator(local_as,local_address))
		return True

	def path_information (self, scope, command, tokens):
		try:
			pi = tokens.pop(0)
			if pi.isdigit():
				scope[-1]['announce'][-1].nlri.path_info = PathInfo(integer=int(pi))
			else:
				scope[-1]['announce'][-1].nlri.path_info = PathInfo(ip=pi)
			return True
		except ValueError:
			return self.error.set(self.syntax)

	def _parse_community (self, scope, data):
		separator = data.find(':')
		if separator > 0:
			prefix = int(data[:separator])
			suffix = int(data[separator+1:])
			if prefix >= pow(2,16):
				raise ValueError('invalid community %s (prefix too large)' % data)
			if suffix >= pow(2,16):
				raise ValueError('invalid community %s (suffix too large)' % data)
			return Community.cached(pack('!L',(prefix << 16) + suffix))
		elif len(data) >= 2 and data[1] in 'xX':
			value = long(data,16)
			if value >= pow(2,32):
				raise ValueError('invalid community %s (too large)' % data)
			return Community.cached(pack('!L',value))
		else:
			low = data.lower()
			if low == 'no-export':
				return Community.cached(Community.NO_EXPORT)
			elif low == 'no-advertise':
				return Community.cached(Community.NO_ADVERTISE)
			elif low == 'no-export-subconfed':
				return Community.cached(Community.NO_EXPORT_SUBCONFED)
			# no-peer is not a correct syntax but I am sure someone will make the mistake :)
			elif low == 'nopeer' or low == 'no-peer':
				return Community.cached(Community.NO_PEER)
			elif data.isdigit():
				value = long(data)
				if value >= pow(2,32):
					raise ValueError('invalid community %s (too large)' % data)
					# return Community.cached(pack('!L',value))
				return Community.cached(pack('!L',value))
			else:
				raise ValueError('invalid community name %s' % data)

	def originator_id (self, scope, command, tokens):
		try:
			scope[-1]['announce'][-1].attributes.add(OriginatorID(tokens.pop(0)))
			return True
		except Exception:
			return self.error.set(self.syntax)

	def cluster_list (self, scope, command, tokens):
		_list = []
		clusterid = tokens.pop(0)
		try:
			if clusterid == '[':
				while True:
					try:
						clusterid = tokens.pop(0)
					except IndexError:
						return self.error.set(self.syntax)
					if clusterid == ']':
						break
					_list.append(ClusterID(clusterid))
			else:
				_list.append(ClusterID(clusterid))
			if not _list:
				raise ValueError('no cluster-id in the cluster-list')
			clusterlist = ClusterList(_list)
		except ValueError:
			return self.error.set(self.syntax)
		scope[-1]['announce'][-1].attributes.add(clusterlist)
		return True

	def community (self, scope, command, tokens):
		communities = Communities()
		community = tokens.pop(0)
		try:
			if community == '[':
				while True:
					try:
						community = tokens.pop(0)
					except IndexError:
						return self.error.set(self.syntax)
					if community == ']':
						break
					communities.add(self._parse_community(scope,community))
			else:
				communities.add(self._parse_community(scope,community))
		except ValueError:
			return self.error.set(self.syntax)
		scope[-1]['announce'][-1].attributes.add(communities)
		return True

	def _parse_extended_community (self, scope, data):
		SIZE_H = 0xFFFF

		if data[:2].lower() == '0x':
			try:
				raw = ''
				for i in range(2,len(data),2):
					raw += chr(int(data[i:i+2],16))
			except ValueError:
				raise ValueError('invalid extended community %s' % data)
			if len(raw) != 8:
				raise ValueError('invalid extended community %s' % data)
			return ExtendedCommunity.unpack(raw,None)
		elif data.count(':'):
			_known_community = {
				# header and subheader
				'target':   chr(0x00)+chr(0x02),
				'target4':  chr(0x02)+chr(0x02),
				'origin':   chr(0x00)+chr(0x03),
				'origin4':  chr(0x02)+chr(0x03),
				'redirect': chr(0x80)+chr(0x08),
				'l2info':   chr(0x80)+chr(0x0A),
			}

			_size_community = {
				'target':   2,
				'target4':  2,
				'origin':   2,
				'origin4':  2,
				'redirect': 2,
				'l2info':   4,
			}

			components = data.split(':')
			command = 'target' if len(components) == 2 else components.pop(0)

			if command not in _known_community:
				raise ValueError('invalid extended community %s (only origin,target or l2info are supported) ' % command)

			if len(components) != _size_community[command]:
				raise ValueError('invalid extended community %s, expecting %d fields ' % (command,len(components)))

			header = _known_community[command]

			if command == 'l2info':
				# encaps, control, mtu, site
				return ExtendedCommunity.unpack(header+pack('!BBHH',*[int(_) for _ in components]),None)

			if command in ('target','origin'):
				# global admin, local admin
				_ga,_la = components
				ga,la = _ga.upper(),_la.upper()

				if '.' in ga or '.' in la:
					gc = ga.count('.')
					lc = la.count('.')
					if gc == 0 and lc == 3:
						# ASN first, IP second
						return ExtendedCommunity.unpack(header+pack('!HBBBB',int(ga),*[int(_) for _ in la.split('.')]),None)
					if gc == 3 and lc == 0:
						# IP first, ASN second
						return ExtendedCommunity.unpack(header+pack('!BBBBH',*[int(_) for _ in ga.split('.')]+[int(la)]),None)
				else:
					iga = int(ga[:-1]) if 'L' in ga else int(ga)
					ila = int(la[:-1]) if 'L' in la else int(la)
					if command == 'target':
						if ga.endswith('L') or iga > SIZE_H:
							return ExtendedCommunity.unpack(_known_community['target4']+pack('!LH',iga,ila),None)
						else:
							return ExtendedCommunity.unpack(header+pack('!HI',iga,ila),None)
					if command == 'origin':
						if ga.endswith('L') or iga > SIZE_H:
							return ExtendedCommunity.unpack(_known_community['origin4']+pack('!LH',iga,ila),None)
						else:
							return ExtendedCommunity.unpack(header+pack('!HI',iga,ila),None)

			if command == 'target4':
				iga = int(ga[:-1]) if 'L' in ga else int(ga)
				ila = int(la[:-1]) if 'L' in la else int(la)
				return ExtendedCommunity.unpack(_known_community['target4']+pack('!LH',iga,ila),None)

			if command == 'orgin4':
				iga = int(ga[:-1]) if 'L' in ga else int(ga)
				ila = int(la[:-1]) if 'L' in la else int(la)
				return ExtendedCommunity.unpack(_known_community['origin4']+pack('!LH',iga,ila),None)

			if command in ('redirect',):
				ga,la = components
				return ExtendedCommunity.unpack(header+pack('!HL',int(ga),long(la)),None)

			raise ValueError('invalid extended community %s' % command)
		else:
			raise ValueError('invalid extended community %s - lc+gc' % data)

	def extended_community (self, scope, command, tokens):
		attributes = scope[-1]['announce'][-1].attributes
		if Attribute.CODE.EXTENDED_COMMUNITY in attributes:
			extended_communities = attributes[Attribute.CODE.EXTENDED_COMMUNITY]
		else:
			extended_communities = ExtendedCommunities()
			attributes.add(extended_communities)

		extended_community = tokens.pop(0)
		try:
			if extended_community == '[':
				while True:
					try:
						extended_community = tokens.pop(0)
					except IndexError:
						return self.error.set(self.syntax)
					if extended_community == ']':
						break
					extended_communities.add(self._parse_extended_community(scope,extended_community))
			else:
				extended_communities.add(self._parse_extended_community(scope,extended_community))
		except ValueError:
			return self.error.set(self.syntax)
		return True

	def split (self, scope, command, tokens):
		try:
			size = tokens.pop(0)
			if not size or size[0] != '/':
				raise ValueError('route "as" require a CIDR')
			scope[-1]['announce'][-1].attributes.add(Split(int(size[1:])))
			return True
		except ValueError:
			return self.error.set(self.syntax)

	def label (self, scope, command, tokens):
		labels = []
		label = tokens.pop(0)
		try:
			if label == '[':
				while True:
					try:
						label = tokens.pop(0)
					except IndexError:
						return self.error.set(self.syntax)
					if label == ']':
						break
					labels.append(int(label))
			else:
				labels.append(int(label))
		except ValueError:
			return self.error.set(self.syntax)

		nlri = scope[-1]['announce'][-1].nlri
		if not nlri.safi.has_label():
			nlri.safi = SAFI(SAFI.nlri_mpls)
		nlri.labels = Labels(labels)
		return True

	def rd (self, scope, command, tokens, safi):
		try:
			try:
				data = tokens.pop(0)
			except IndexError:
				return self.error.set(self.syntax)

			separator = data.find(':')
			if separator > 0:
				prefix = data[:separator]
				suffix = int(data[separator+1:])

			if '.' in prefix:
				data = [chr(0),chr(1)]
				data.extend([chr(int(_)) for _ in prefix.split('.')])
				data.extend([chr(suffix >> 8),chr(suffix & 0xFF)])
				rd = ''.join(data)
			else:
				number = int(prefix)
				if number < pow(2,16) and suffix < pow(2,32):
					rd = chr(0) + chr(0) + pack('!H',number) + pack('!L',suffix)
				elif number < pow(2,32) and suffix < pow(2,16):
					rd = chr(0) + chr(2) + pack('!L',number) + pack('!H',suffix)
				else:
					raise ValueError('invalid route-distinguisher %s' % data)

			nlri = scope[-1]['announce'][-1].nlri
			# overwrite nlri-mpls
			nlri.safi = SAFI(safi)
			nlri.rd = RouteDistinguisher(rd)
			return True
		except ValueError:
			return self.error.set(self.syntax)

	def insert_static_route (self, scope, command, tokens):
		try:
			ip = tokens.pop(0)
		except IndexError:
			return self.error.set(self.syntax)
		try:
			ip,mask = ip.split('/')
			mask = int(mask)
		except ValueError:
			mask = 32
		try:
			if 'rd' in tokens:
				klass = MPLS
			elif 'route-distinguisher' in tokens:
				klass = MPLS
			elif 'label' in tokens:
				klass = MPLS
			else:
				klass = INET

			# nexthop must be false and its str return nothing .. an empty string does that
			update = Change(klass(afi=IP.toafi(ip),safi=IP.tosafi(ip),packed=IP.pton(ip),mask=mask,nexthop=None,action=OUT.ANNOUNCE),Attributes())
		except ValueError:
			return self.error.set(self.syntax)

		if 'announce' not in scope[-1]:
			scope[-1]['announce'] = []

		scope[-1]['announce'].append(update)
		return True

	def route (self, scope, command, tokens):
		if len(tokens) < 3:
			return False

		if not self.insert_static_route(scope,command,tokens):
			return False

		while len(tokens):
			command = tokens.pop(0)

			if command in ('withdraw','withdrawn'):
				if self.withdraw(scope,command,tokens):
					continue
				return False

			if len(tokens) < 1:
				return False

			if command in self.command:
				if command in ('rd','route-distinguisher'):
					if self.command[command](scope,command,tokens,SAFI.nlri_mpls):
						continue
				else:
					if self.command[command](scope,command,tokens):
						continue
			else:
				return False
			return False

		if not self.check_static_route(scope,self):
			return False

		return self.make_split(scope)

	def make_split (self, scope, command=None, tokens=None):
		# if the route does not need to be broken in smaller routes, return
		change = scope[-1]['announce'][-1]
		if Attribute.CODE.INTERNAL_SPLIT not in change.attributes:
			return True

		# ignore if the request is for an aggregate, or the same size
		mask = change.nlri.mask
		split = change.attributes[Attribute.CODE.INTERNAL_SPLIT]
		if mask >= split:
			return True

		# get a local copy of the route
		change = scope[-1]['announce'].pop(-1)

		# calculate the number of IP in the /<size> of the new route
		increment = pow(2,(len(change.nlri.packed)*8) - split)
		# how many new routes are we going to create from the initial one
		number = pow(2,split - change.nlri.mask)

		# convert the IP into a integer/long
		ip = 0
		for c in change.nlri.packed:
			ip <<= 8
			ip += ord(c)

		afi = change.nlri.afi
		safi = change.nlri.safi

		# Really ugly
		klass = change.nlri.__class__
		if klass is INET:
			path_info = change.nlri.path_info
		elif klass is MPLS:
			path_info = None
			labels = change.nlri.labels
			rd = change.nlri.rd
		# packed and not pack() but does not matter atm, it is an IP not a NextHop
		nexthop = change.nlri.nexthop.packed

		change.nlri.mask = split
		change.nlri = None
		# generate the new routes
		for _ in range(number):
			# update ip to the next route, this recalculate the "ip" field of the Inet class
			nlri = klass(afi,safi,pack_int(afi,ip,split),split,nexthop,OUT.ANNOUNCE,path_info)
			if klass is MPLS:
				nlri.labels = labels
				nlri.rd = rd
			# next ip
			ip += increment
			# save route
			scope[-1]['announce'].append(Change(nlri,change.attributes))

		return True

	def check_static_route (self, scope, configuration):
		update = scope[-1]['announce'][-1]
		if update.nlri.nexthop is NoNextHop:
			return self.error.set('syntax: route <ip>/<mask> { next-hop <ip>; }')
		return True
