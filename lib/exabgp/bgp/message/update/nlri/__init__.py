# encoding: utf-8
"""
nlri/__init__.py

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every NLRI should be imported from this file

from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.nlri.cidr import CIDR

from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.evpn import EVPN
from exabgp.bgp.message.update.nlri.rtc import RTC
from exabgp.bgp.message.update.nlri.bgpls import BGPLS
