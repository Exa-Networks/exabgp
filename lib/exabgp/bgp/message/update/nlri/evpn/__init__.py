"""
evpn/__init__.py

Created by Thomas Mangin on 2014-06-27.
Copyright (c) 2014-2015 Orange. All rights reserved.
"""

from exabgp.bgp.message.update.nlri.evpn.nlri import EVPN

# Is it required from the register
from exabgp.bgp.message.update.nlri.evpn.ethernetad import EthernetAD
from exabgp.bgp.message.update.nlri.evpn.mac import MAC
from exabgp.bgp.message.update.nlri.evpn.multicast import Multicast
from exabgp.bgp.message.update.nlri.evpn.segment import EthernetSegment
# end requirement
