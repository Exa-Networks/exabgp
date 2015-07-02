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


NLRI.register_nlri(MPLS,AFI.ipv4,SAFI.unicast)
NLRI.register_nlri(MPLS,AFI.ipv6,SAFI.unicast)
NLRI.register_nlri(MPLS,AFI.ipv4,SAFI.multicast)
NLRI.register_nlri(MPLS,AFI.ipv6,SAFI.multicast)

NLRI.register_nlri(MPLS,AFI.ipv4,SAFI.nlri_mpls)
NLRI.register_nlri(MPLS,AFI.ipv6,SAFI.nlri_mpls)
NLRI.register_nlri(MPLS,AFI.ipv4,SAFI.mpls_vpn)
NLRI.register_nlri(MPLS,AFI.ipv6,SAFI.mpls_vpn)

NLRI.register_nlri(VPLS,AFI.l2vpn,SAFI.vpls)

NLRI.register_nlri(Flow,AFI.ipv4,SAFI.flow_ip)
NLRI.register_nlri(Flow,AFI.ipv6,SAFI.flow_ip)
NLRI.register_nlri(Flow,AFI.ipv4,SAFI.flow_vpn)
NLRI.register_nlri(Flow,AFI.ipv6,SAFI.flow_vpn)
