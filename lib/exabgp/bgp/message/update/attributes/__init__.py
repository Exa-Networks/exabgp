# encoding: utf-8
"""
attributes/__init__.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from struct import unpack,error

from exabgp.util.od import od
from exabgp.configuration.environment import environment
from exabgp.util.cache import Cache

from exabgp.protocol.family import AFI,SAFI

from exabgp.bgp.message.direction import IN

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.eor import NLRIEOR

from exabgp.bgp.message.update.attribute.id import AttributeID as AID
from exabgp.bgp.message.update.attribute.flag import Flag
from exabgp.bgp.message.update.attribute.origin import Origin
from exabgp.bgp.message.update.attribute.aspath import ASPath,AS4Path
from exabgp.bgp.message.update.attribute.nexthop import NextHop,cachedNextHop
from exabgp.bgp.message.update.attribute.med import MED
from exabgp.bgp.message.update.attribute.localpref import LocalPreference
from exabgp.bgp.message.update.attribute.atomicaggregate import AtomicAggregate
from exabgp.bgp.message.update.attribute.aggregator import Aggregator
from exabgp.bgp.message.update.attribute.communities import cachedCommunity,Communities,ECommunity,ECommunities
from exabgp.bgp.message.update.attribute.originatorid import OriginatorID
from exabgp.bgp.message.update.attribute.clusterlist import ClusterList
from exabgp.bgp.message.update.attribute.aigp import AIGP

from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI
from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

from exabgp.bgp.message.update.attribute.unknown import UnknownAttribute

from exabgp.logger import Logger,LazyFormat

class _NOTHING (object):
	def pack (self,asn4=None):
		return ''

NOTHING = _NOTHING()

# =================================================================== Attributes

# 0                   1
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  Attr. Flags  |Attr. Type Code|
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class MultiAttributes (list):
	def __init__ (self,attribute):
		list.__init__(self)
		self.ID = attribute.ID
		self.FLAG = attribute.FLAG
		self.MULTIPLE = True
		self.append(attribute)

	def pack (self,asn4=None):
		r = []
		for attribute in self:
			r.append(attribute.pack())
		return ''.join(r)

	def __len__ (self):
		return len(self.pack())

	def __str__ (self):
		return 'MultiAttibutes(%s)' % ' '.join(str(_) for _ in self)

class Attributes (dict):
	# we need this to not create an include loop !
	nlriFactory = None
	# A cache of parsed attributes
	cache = {}
	# A previously parsed object
	cached = None

	lookup = {
		AID.ORIGIN             : Origin,              # 1
		AID.AS_PATH            : ASPath,              # 2
		# NextHop                                     # 3
		AID.MED                : MED,                 # 4
		AID.LOCAL_PREF         : LocalPreference,     # 5
		AID.ATOMIC_AGGREGATE   : AtomicAggregate,     # 6
		AID.AGGREGATOR         : Aggregator,          # 7
		AID.COMMUNITY          : Communities,         # 8
		AID.ORIGINATOR_ID      : OriginatorID,        # 9
		AID.CLUSTER_LIST       : ClusterList,         # 10
		AID.EXTENDED_COMMUNITY : ECommunities,        # 16
		AID.AS4_PATH           : AS4Path,             # 17
		AID.AS4_AGGREGATOR     : Aggregator,          # 18
		AID.AIGP               : AIGP,                # 26
	}

	representation = {
		#	key:  (how, default, name, presentation),
		AID.ORIGIN             : ('string',  '', 'origin', '%s'),
		AID.AS_PATH            : ('list',    '', 'as-path', '%s'),
		AID.NEXT_HOP           : ('string',  '', 'next-hop', '%s'),
		AID.MED                : ('integer', '', 'med', '%s'),
		AID.LOCAL_PREF         : ('integer', '', 'local-preference', '%s'),
		AID.ATOMIC_AGGREGATE   : ('boolean', '', 'atomic-aggregate', '%s'),
		AID.AGGREGATOR         : ('string',  '', 'aggregator', '( %s )'),
		AID.COMMUNITY          : ('list',    '', 'community', '%s'),
		AID.ORIGINATOR_ID      : ('inet',    '', 'originator-id', '%s'),
		AID.CLUSTER_LIST       : ('list',    '', 'cluster-list', '%s'),
		AID.EXTENDED_COMMUNITY : ('list',    '', 'extended-community', '%s'),
		AID.AIGP               : ('integer', '', 'aigp', '%s'),
	}

	known_attributes = lookup.keys()

	# STRING = [_ for _ in representation if representation[_][0] == 'string']
	# INTEGER = [_ for _ in representation if representation[_][0] == 'integer']
	# LIST = [_ for _ in representation if representation[_][0] == 'list']
	# BOOLEAN = [_ for _ in representation if representation[_][0] == 'boolean']

	def __init__ (self):
		# cached representation of the object
		self._str = ''
		self._idx = ''
		self._json = ''
		# We should cache the attributes parsed
		self.cache_attributes = environment.settings().cache.attributes
		# some of the attributes are MP_REACH_NLRI or MP_UNREACH_NLRI
		self.hasmp = 0
		# The parsed attributes have no mp routes and/or those are last
		self.cacheable = True
		# for the last route, the part of the attributes which are not routes we can use for fast caching
		self.prefix = ''

	def has (self,k):
		return k in self

	def add_from_cache (self,attributeid,data):
		if data in self.cache.setdefault(attributeid,Cache()):
			self.add(self.cache[attributeid].retrieve(data))
			return True
		return False

	def add (self,attribute,data=None):
		self._str = ''
		self._json = ''
		if data and self.cache_attributes:
			self.cache[attribute.ID].cache(data,attribute)
		if attribute.MULTIPLE:
			if self.has(attribute.ID):
				self[attribute.ID].append(attribute)
			else:
				self[attribute.ID] = MultiAttributes(attribute)
		else:
			self[attribute.ID] = attribute

	def remove (self,attrid):
		self.pop(attrid)

	def watchdog (self):
		if AID.INTERNAL_WATCHDOG in self:
			return self.pop(AID.INTERNAL_WATCHDOG)
		return None

	def withdraw (self):
		if AID.INTERNAL_WITHDRAW in self:
			self.pop(AID.INTERNAL_WITHDRAW)
			return True
		return False

	def pack (self,negotiated,with_default=True):
		asn4 = negotiated.asn4
		local_asn = negotiated.local_as
		peer_asn = negotiated.peer_as

		if negotiated.neighbor.aigp is None:
			aigp = True if local_asn == peer_asn else False
		else:
			aigp = negotiated.neighbor.aigp

		message = ''

		default = {
			AID.ORIGIN:     lambda l,r: Origin(Origin.IGP),
			AID.AS_PATH:    lambda l,r: ASPath([],[]) if l == r else ASPath([local_asn,],[]),
			AID.LOCAL_PREF: lambda l,r: LocalPreference('\x00\x00\x00d') if l == r else NOTHING,
		}

		check = {
			AID.NEXT_HOP:   lambda l,r,nh: nh.afi == AFI.ipv4,
			AID.LOCAL_PREF: lambda l,r,nh: l == r,
		}

		if with_default:
			keys = set(self.keys() + default.keys())
		else:
			keys = set(self.keys())

		# AGGREGATOR generate both AGGREGATOR and AS4_AGGREGATOR
		for code in sorted(keys):
			if code in (AID.INTERNAL_SPLIT, AID.INTERNAL_WATCHDOG, AID.INTERNAL_WITHDRAW):
				continue
			if code in self:
				if code == AID.AIGP and not aigp:
					continue
				if code in check:
					if check[code](local_asn,peer_asn,self[code]):
						message += self[code].pack(asn4)
						continue
				else:
					message += self[code].pack(asn4)
					continue
			else:
				if code in default:
					message += default[code](local_asn,peer_asn).pack(asn4)

		return message

	def json (self):
		if not self._json:
			def generate (self):
				for code in sorted(self.keys() + [AID.ATOMIC_AGGREGATE,]):
					# remove the next-hop from the attribute as it is define with the NLRI
					if code in (AID.NEXT_HOP, AID.INTERNAL_SPLIT, AID.INTERNAL_WATCHDOG, AID.INTERNAL_WITHDRAW):
						continue
					if code in self.representation:
						how, default, name, presentation = self.representation[code]
						if how == 'boolean':
							yield '"%s": %s' % (name, 'true' if self.has(code) else 'false')
						elif how == 'string':
							yield '"%s": "%s"' % (name, presentation % str(self[code]))
						elif how == 'list':
							yield '"%s": %s' % (name, presentation % self[code].json())
						elif how == 'inet':
							yield '"%s": "%s"' % (name, presentation % str(self[code]))
						# Should never be ran
						else:
							yield '"%s": %s' % (name, presentation % str(self[code]))
					else:
						yield '"attribute-0x%02X-0x%02X": "%s"' % (code,self[code].FLAG,str(self[code]))
			self._json = ', '.join(generate(self))
		return self._json

	def __str__ (self):
		if not self._str:
			def generate (self):
				for code in sorted(self.keys()):
					# XXX: FIXME: really we should have a INTERNAL attribute in the classes
					if code in (AID.INTERNAL_SPLIT, AID.INTERNAL_WATCHDOG, AID.INTERNAL_WITHDRAW, AID.NEXT_HOP):
						continue
					if code in self.representation:
						how, default, name, presentation = self.representation[code]
						if how == 'boolean':
							yield ' %s' % name
						else:
							yield ' %s %s' % (name, presentation % str(self[code]))
					else:
						yield ' attribute [ 0x%02X 0x%02X %s ]' % (code,self[code].FLAG,str(self[code]))
			# XXX: FIXME: remove this ' ' + ? should it be done by the caller ?
			self._str = ''.join(generate(self))
		return self._str

	def index (self):
		# XXX: FIXME: something a little bit smaller memory wise ?
		if not self._idx:
			self._idx = '%s next-hop %s' % (str(self), str(self[AID.NEXT_HOP])) if AID.NEXT_HOP in self else str(self)
		return self._idx

	def factory (self,data):
		self.cached = self._factory(data)
		return self.cached

	def _factory (self,data):
		if not data:
			return self

		# We do not care if the attribute are transitive or not as we do not redistribute
		flag = Flag(ord(data[0]))
		code = AID(ord(data[1]))

		if flag & Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			offset = 4
		else:
			length = ord(data[2])
			offset = 3

		if self.hasmp:
			if code not in (AID.MP_REACH_NLRI, AID.MP_UNREACH_NLRI):
				self.cacheable = False
				self.prefix = ''
		else:
			self.prefix += data[:offset+length]

		data = data[offset:]
		next = data[length:]
		attribute = data[:length]

		logger = Logger()
		logger.parser(LazyFormat("parsing flag %x type %02x (%s) len %02x %s" % (flag,int(code),code,length,'payload ' if length else ''),od,data[:length]))

		if code == AID.ORIGIN and flag.matches(Origin.FLAG):
			# This if block should never be called anymore ...
			if not self.add_from_cache(code,attribute):
				self.add(Origin(ord(attribute)),attribute)
			return self.factory(next)

		# only 2-4% of duplicated data - is it worth to cache ?
		if code == AID.AS_PATH and flag.matches(ASPath.FLAG):
			if length:
				# we store the AS4_PATH as AS_PATH, do not over-write
				if not self.has(code):
					if not self.add_from_cache(code,attribute):
						self.add(self.__new_ASPath(attribute),attribute)
			return self.factory(next)

		if code == AID.AS4_PATH and flag.matches(AS4Path.FLAG):
			if length:
				# ignore the AS4_PATH on new spekers as required by RFC 4893 section 4.1
				if not self.negotiated.asn4:
					# This replace the old AS_PATH
					if not self.add_from_cache(code,attribute):
						self.add(self.__new_ASPath4(attribute),attribute)
			return self.factory(next)

		if code == AID.NEXT_HOP and flag.matches(NextHop.FLAG):
			# XXX: FIXME: we are double caching the NH (once in the class, once here)
			if not self.add_from_cache(code,attribute):
				self.add(cachedNextHop(attribute),attribute)
			return self.factory(next)

		if code == AID.MED and flag.matches(MED.FLAG):
			if not self.add_from_cache(code,attribute):
				self.add(MED(attribute),attribute)
			return self.factory(next)

		if code == AID.LOCAL_PREF and flag.matches(LocalPreference.FLAG):
			if not self.add_from_cache(code,attribute):
				self.add(LocalPreference(attribute),attribute)
			return self.factory(next)

		if code == AID.ATOMIC_AGGREGATE and flag.matches(AtomicAggregate.FLAG):
			if not self.add_from_cache(code,attribute):
				raise Notify(3,2,'invalid ATOMIC_AGGREGATE %s' % [hex(ord(_)) for _ in attribute])
			return self.factory(next)

		if code == AID.AGGREGATOR and flag.matches(Aggregator.FLAG):
			# AS4_AGGREGATOR are stored as AGGREGATOR - so do not overwrite if exists
			if not self.has(code):
				if not self.add_from_cache(AID.AGGREGATOR,attribute):
					self.add(Aggregator(attribute),attribute)
			return self.factory(next)

		if code == AID.AS4_AGGREGATOR and flag.matches(Aggregator.FLAG):
			if not self.add_from_cache(AID.AGGREGATOR,attribute):
				self.add(Aggregator(attribute),attribute)
			return self.factory(next)

		if code == AID.COMMUNITY and flag.matches(Communities.FLAG):
			if not self.add_from_cache(code,attribute):
				self.add(self.__new_communities(attribute),attribute)
			return self.factory(next)

		if code == AID.ORIGINATOR_ID and flag.matches(OriginatorID.FLAG):
			if not self.add_from_cache(code,attribute):
				self.add(OriginatorID(AFI.ipv4,SAFI.unicast,data[:4]),attribute)
			return self.factory(next)

		if code == AID.CLUSTER_LIST and flag.matches(ClusterList.FLAG):
			if not self.add_from_cache(code,attribute):
				self.add(ClusterList(attribute),attribute)
			return self.factory(next)

		if code == AID.EXTENDED_COMMUNITY and flag.matches(ECommunities.FLAG):
			if not self.add_from_cache(code,attribute):
				self.add(self.__new_extended_communities(attribute),attribute)
			return self.factory(next)

		if code == AID.AIGP and flag.matches(AIGP.FLAG):
			if self.negotiated.neighbor.aigp:
				if not self.add_from_cache(code,attribute):
					self.add(AIGP(attribute),attribute)
			return self.factory(next)

		if code == AID.MP_UNREACH_NLRI and flag.matches(MPURNLRI.FLAG):
			self.hasmp = True


			# -- Reading AFI/SAFI
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			data = data[offset:]

			if (afi,safi) not in self.negotiated.families:
				raise Notify(3,0,'presented a non-negotiated family %d/%d' % (afi,safi))

			# Is the peer going to send us some Path Information with the route (AddPath)
			addpath = self.negotiated.addpath.receive(afi,safi)

			# XXX: we do assume that it is an EOR. most likely harmless
			if not data:
				self.mp_withdraw.append(NLRIEOR(afi,safi,IN.announced))
				return self.factory(next)

			while data:
				length,nlri = self.nlriFactory(afi,safi,data,addpath,None,IN.withdrawn)
				self.mp_withdraw.append(nlri)
				data = data[length:]
				logger.parser(LazyFormat("parsed withdraw mp nlri %s payload " % nlri,od,data[:length]))

			return self.factory(next)

		if code == AID.MP_REACH_NLRI and flag.matches(MPRNLRI.FLAG):
			self.hasmp = True

			data = data[:length]
			# -- Reading AFI/SAFI
			afi,safi = unpack('!HB',data[:3])
			offset = 3

			# we do not want to accept unknown families
			if (afi,safi) not in self.negotiated.families:
				raise Notify(3,0,'presented a non-negotiated family %d/%d' % (afi,safi))

			# -- Reading length of next-hop
			len_nh = ord(data[offset])
			offset += 1

			rd = 0

			# check next-hope size
			if afi == AFI.ipv4:
				if safi in (SAFI.unicast,SAFI.multicast):
					if len_nh != 4:
						raise Notify(3,0,'invalid ipv4 unicast/multicast next-hop length %d expected 4' % len_nh)
				elif safi in (SAFI.mpls_vpn,):
					if len_nh != 12:
						raise Notify(3,0,'invalid ipv4 mpls_vpn next-hop length %d expected 12' % len_nh)
					rd = 8
				elif safi in (SAFI.flow_ip,):
					if len_nh not in (0,4):
						raise Notify(3,0,'invalid ipv4 flow_ip next-hop length %d expected 4' % len_nh)
				elif safi in (SAFI.flow_vpn,):
					if len_nh not in (0,4):
						raise Notify(3,0,'invalid ipv4 flow_vpn next-hop length %d expected 4' % len_nh)
			elif afi == AFI.ipv6:
				if safi in (SAFI.unicast,):
					if len_nh not in (16,32):
						raise Notify(3,0,'invalid ipv6 unicast next-hop length %d expected 16 or 32' % len_nh)
				elif safi in (SAFI.mpls_vpn,):
					if len_nh not in (24,40):
						raise Notify(3,0,'invalid ipv6 mpls_vpn next-hop length %d expected 24 or 40' % len_nh)
					rd = 8
				elif safi in (SAFI.flow_ip,):
					if len_nh not in (0,16,32):
						raise Notify(3,0,'invalid ipv6 flow_ip next-hop length %d expected 0, 16 or 32' % len_nh)
				elif safi in (SAFI.flow_vpn,):
					if len_nh not in (0,16,32):
						raise Notify(3,0,'invalid ipv6 flow_vpn next-hop length %d expected 0, 16 or 32' % len_nh)
			size = len_nh - rd

			# XXX: FIXME: GET IT FROM CACHE HERE ?
			nh = data[offset+rd:offset+rd+size]

			# chech the RD is well zero
			if rd and sum([int(ord(_)) for _ in data[offset:8]]) != 0:
				raise Notify(3,0,"MP_REACH_NLRI next-hop's route-distinguisher must be zero")

			offset += len_nh

			# Skip a reserved bit as somone had to bug us !
			reserved = ord(data[offset])
			offset += 1

			if reserved != 0:
				raise Notify(3,0,'the reserved bit of MP_REACH_NLRI is not zero')

			# Is the peer going to send us some Path Information with the route (AddPath)
			addpath = self.negotiated.addpath.receive(afi,safi)

			# Reading the NLRIs
			data = data[offset:]

			while data:
				length,nlri = self.nlriFactory(afi,safi,data,addpath,nh,IN.announced)
				self.mp_announce.append(nlri)
				logger.parser(LazyFormat("parsed announce mp nlri %s payload " % nlri,od,data[:length]))
				data = data[length:]
			return self.factory(next)

		if flag & Flag.TRANSITIVE:
			if code in self.known_attributes:
				# XXX: FIXME: we should really close the session
				logger.parser('ignoring implemented invalid transitive attribute (code 0x%02X, flag 0x%02X)' % (code,flag))
				return self.factory(next)

			if not self.add_from_cache(code,attribute):
				self.add(UnknownAttribute(code,flag,attribute),attribute)
			return self.factory(next)

		logger.parser('ignoring non-transitive attribute (code 0x%02X, flag 0x%02X)' % (code,flag))
		return self.factory(next)


	def merge_attributes (self):
		as2path = self[AID.AS_PATH]
		as4path = self[AID.AS4_PATH]
		self.remove(AID.AS_PATH)
		self.remove(AID.AS4_PATH)

		# this key is unique as index length is a two header, plus a number of ASN of size 2 or 4
		# so adding the : make the length odd and unique
		key = "%s:%s" % (as2path.index, as4path.index)

		# found a cache copy
		if self.add_from_cache(AID.AS_PATH,key):
			return

		as_seq = []
		as_set = []

		len2 = len(as2path.as_seq)
		len4 = len(as4path.as_seq)

		# RFC 4893 section 4.2.3
		if len2 < len4:
			as_seq = as2path.as_seq
		else:
			as_seq = as2path.as_seq[:-len4]
			as_seq.extend(as4path.as_seq)

		len2 = len(as2path.as_set)
		len4 = len(as4path.as_set)

		if len2 < len4:
			as_set = as4path.as_set
		else:
			as_set = as2path.as_set[:-len4]
			as_set.extend(as4path.as_set)

		aspath = ASPath(as_seq,as_set)
		self.add(aspath,key)

	def __new_communities (self,data):
		communities = Communities()
		while data:
			if data and len(data) < 4:
				raise Notify(3,1,'could not decode community %s' % str([hex(ord(_)) for _ in data]))
			communities.add(cachedCommunity(data[:4]))
			data = data[4:]
		return communities

	def __new_extended_communities (self,data):
		communities = ECommunities()
		while data:
			if data and len(data) < 8:
				raise Notify(3,1,'could not decode extended community %s' % str([hex(ord(_)) for _ in data]))
			communities.add(ECommunity(data[:8]))
			data = data[8:]
		return communities

	def __new_aspaths (self,data,asn4,klass):
		as_set = []
		as_seq = []
		backup = data

		unpacker = {
			False : '!H',
			True  : '!L',
		}
		size = {
			False: 2,
			True : 4,
		}
		as_choice = {
			ASPath.AS_SEQUENCE : as_seq,
			ASPath.AS_SET      : as_set,
		}

		upr = unpacker[asn4]
		length = size[asn4]

		try:

			while data:
				stype = ord(data[0])
				slen  = ord(data[1])

				if stype not in (ASPath.AS_SET, ASPath.AS_SEQUENCE):
					raise Notify(3,11,'invalid AS Path type sent %d' % stype)

				end = 2+(slen*length)
				sdata = data[2:end]
				data = data[end:]
				asns = as_choice[stype]

				for i in range(slen):
					asn = unpack(upr,sdata[:length])[0]
					asns.append(ASN(asn))
					sdata = sdata[length:]

		except IndexError:
			raise Notify(3,11,'not enough data to decode AS_PATH or AS4_PATH')
		except error:  # struct
			raise Notify(3,11,'not enough data to decode AS_PATH or AS4_PATH')

		return klass(as_seq,as_set,backup)

	def __new_ASPath (self,data):
		return self.__new_aspaths(data,self.negotiated.asn4,ASPath)

	def __new_ASPath4 (self,data):
		return self.__new_aspaths(data,True,AS4Path)

if not Attributes.cache:
	for attribute in AID._str:
		Attributes.cache[attribute] = Cache()

	# There can only be one, build it now :)
	Attributes.cache[AID.ATOMIC_AGGREGATE][''] = AtomicAggregate()

	IGP = Origin(Origin.IGP)
	EGP = Origin(Origin.EGP)
	INC = Origin(Origin.INCOMPLETE)

	Attributes.cache[AID.ORIGIN][IGP.pack()] = IGP
	Attributes.cache[AID.ORIGIN][EGP.pack()] = EGP
	Attributes.cache[AID.ORIGIN][INC.pack()] = INC
