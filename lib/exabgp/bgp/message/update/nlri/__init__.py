# encoding: utf-8
"""
nlri/__init__.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.prefix import Prefix
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.mpls import MPLS
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.flow import Flow


NLRI.register_nlri(Prefix,SAFI.unicast,AFI.ipv4)
NLRI.register_nlri(Prefix,SAFI.unicast,AFI.ipv6)
NLRI.register_nlri(Prefix,SAFI.multicast,AFI.ipv4)
NLRI.register_nlri(Prefix,SAFI.multicast,AFI.ipv6)

NLRI.register_nlri(MPLS,SAFI.nlri_mpls,AFI.ipv4)
NLRI.register_nlri(MPLS,SAFI.nlri_mpls,AFI.ipv6)
NLRI.register_nlri(MPLS,SAFI.mpls_vpn,AFI.ipv4)
NLRI.register_nlri(MPLS,SAFI.mpls_vpn,AFI.ipv6)

NLRI.register_nlri(VPLS,SAFI.vpls,AFI.l2vpn)

NLRI.register_nlri(Flow,SAFI.flow_ip,AFI.ipv4)
NLRI.register_nlri(Flow,SAFI.flow_ip,AFI.ipv6)
NLRI.register_nlri(Flow,SAFI.flow_vpn,AFI.ipv4)
NLRI.register_nlri(Flow,SAFI.flow_vpn,AFI.ipv6)
