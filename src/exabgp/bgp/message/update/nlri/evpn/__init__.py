"""
evpn/__init__.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2017 Orange. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every EVPN should be imported from this file
# as it makes sure that all the registering decorator are run

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

from exabgp.bgp.message.update.nlri.evpn.ethernetad import EthernetAD
from exabgp.bgp.message.update.nlri.evpn.mac import MAC
from exabgp.bgp.message.update.nlri.evpn.multicast import Multicast
from exabgp.bgp.message.update.nlri.evpn.segment import EthernetSegment
from exabgp.bgp.message.update.nlri.evpn.prefix import Prefix
