# encoding: utf-8
"""
nlri/__init__.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

# Every NLRI should be imported from this file

from exabgp.bgp.message.update.nlri.nlri import NLRI

from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.mpls import MPLS
from exabgp.bgp.message.update.nlri.mpls import MPLSVPN
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.evpn import EVPN
from exabgp.bgp.message.update.nlri.rtc import RouteTargetConstraint
