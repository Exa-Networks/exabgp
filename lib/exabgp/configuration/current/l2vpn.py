# encoding: utf-8
"""
parse_l2vpn.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# from struct import pack
#
# from exabgp.protocol.family import AFI
# from exabgp.protocol.family import SAFI
#
# from exabgp.protocol.ip import IP
# from exabgp.protocol.ip import NoNextHop
#
# from exabgp.bgp.message.open.asn import ASN
# from exabgp.bgp.message.open.routerid import RouterID
#
# from exabgp.bgp.message.update.nlri import INET
# from exabgp.bgp.message.update.nlri import MPLS
#
# from exabgp.bgp.message.update.nlri.qualifier import Labels
# from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
# from exabgp.bgp.message.update.nlri.qualifier import PathInfo
#
# from exabgp.bgp.message.update.attribute import Attribute
# from exabgp.bgp.message.update.attribute import Attributes
#
# from exabgp.bgp.message.update.attribute import Origin
# from exabgp.bgp.message.update.attribute import NextHop
# from exabgp.bgp.message.update.attribute import ASPath
# from exabgp.bgp.message.update.attribute import MED
# from exabgp.bgp.message.update.attribute import LocalPreference
# from exabgp.bgp.message.update.attribute import AtomicAggregate
# from exabgp.bgp.message.update.attribute import Aggregator
#
# from exabgp.bgp.message.update.attribute.community.community import Community
# from exabgp.bgp.message.update.attribute.community.communities import Communities
# from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
# from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunities
#
# from exabgp.bgp.message.update.attribute import OriginatorID
# from exabgp.bgp.message.update.attribute import ClusterID
# from exabgp.bgp.message.update.attribute import ClusterList
# from exabgp.bgp.message.update.attribute import AIGP
# from exabgp.bgp.message.update.attribute import GenericAttribute
#
# from exabgp.bgp.message import OUT
# from exabgp.rib.change import Change
#
from exabgp.configuration.current.basic import Basic
# from exabgp.configuration.current.basic import Split
# from exabgp.configuration.current.basic import Withdrawn
# from exabgp.configuration.current.basic import Watchdog
# from exabgp.configuration.current.basic import Name


class ParseL2VPN (Basic):
	syntax = \
		'syntax:\n' \
		'  l2vpn {\n' \
		'    vpls site_name {\n' \
		'       endpoint <vpls endpoint id; integer>\n' \
		'       base <label base; integer>\n' \
		'       offset <block offet; interger>\n' \
		'       size <block size; integer>\n' \
		'       route-distinguisher|rd 255.255.255.255:65535|65535:65536|65536:65535\n' \
		'       next-hop 192.0.1.254;\n' \
		'       origin IGP|EGP|INCOMPLETE;\n' \
		'       as-path [ as as as as] ;\n' \
		'       med 100;\n' \
		'       local-preference 100;\n' \
		'       community [ 65000 65001 65002 ];\n' \
		'       extended-community [ target:1234:5.6.7.8 target:1.2.3.4:5678 origin:1234:5.6.7.8 origin:1.2.3.4:5678 0x0002FDE800000001 l2info:19:0:1500:111 ]\n' \
		'       originator-id 10.0.0.10;\n' \
		'       cluster-list [ 10.10.0.1 10.10.0.2 ];\n' \
		'       withdraw\n' \
		'       name what-you-want-to-remember-about-the-route\n' \
		'    }\n' \
		'  }\n'

	_str_vpls_bad_size = "you tried to configure an invalid l2vpn vpls block-size"
	_str_vpls_bad_offset = "you tried to configure an invalid l2vpn vpls block-offset"
	_str_vpls_bad_label = "you tried to configure an invalid l2vpn vpls label"
	_str_vpls_bad_enpoint = "you tried to configure an invalid l2vpn vpls endpoint"

	def __init__ (self, error):
		self.error = error

	def clear (self):
		pass

	def vpls_endpoint (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_enpoint)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.ve = number
		return True

	def vpls_size (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_size)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.size = number
		return True

	def vpls_offset (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_offset)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.offset = number
		return True

	def vpls_base (self, scope, token):
		number = int(token.pop(0))
		if number < 0 or number > 0xFFFF:
			return self.error.set(self._str_vpls_bad_label)

		vpls = scope[-1]['announce'][-1].nlri
		vpls.base = number
		return True
