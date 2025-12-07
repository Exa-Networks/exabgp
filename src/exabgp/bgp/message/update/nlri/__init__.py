"""nlri/__init__.py

BGP NLRI (Network Layer Reachability Information) Package.

This is the main entry point for all NLRI types supported by ExaBGP.
All NLRI classes should be imported from here to ensure registration
decorators are executed.

Supported NLRI Families:
+------------------+----------+------+----------------------------------+
| NLRI Type        | AFI      | SAFI | RFC                              |
+------------------+----------+------+----------------------------------+
| INET             | 1, 2     | 1, 2 | RFC 4271 (IPv4/IPv6 unicast/mcast)|
| Label            | 1, 2     | 4    | RFC 3107 (MPLS labels)           |
| IPVPN            | 1, 2     | 128  | RFC 4364 (VPNv4/VPNv6)           |
| VPLS             | 25       | 65   | RFC 4761 (Virtual Private LAN)   |
| Flow             | 1, 2     | 133  | RFC 5575 (FlowSpec)              |
| EVPN             | 25       | 70   | RFC 7432 (Ethernet VPN)          |
| RTC              | 1        | 132  | RFC 4684 (Route Target Constraint)|
| BGPLS            | 16388    | 71   | RFC 7752 (Link-State)            |
| MUP              | 1, 2     | 69   | draft-mpmz-bess-mup-safi         |
| MVPN             | 1, 2     | 5    | RFC 6514 (Multicast VPN)         |
+------------------+----------+------+----------------------------------+

AFI Values: 1=IPv4, 2=IPv6, 25=L2VPN, 16388=BGP-LS
SAFI Values: See protocol/family.py for full list

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md

Created by Thomas Mangin on 2013-08-07.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every NLRI should be imported from this file

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.nlri.nlri import NLRI, _UNPARSED
from exabgp.bgp.message.update.nlri.cidr import CIDR

from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.label import Label
from exabgp.bgp.message.update.nlri.ipvpn import IPVPN
from exabgp.bgp.message.update.nlri.vpls import VPLS
from exabgp.bgp.message.update.nlri.flow import Flow
from exabgp.bgp.message.update.nlri.evpn import EVPN
from exabgp.bgp.message.update.nlri.rtc import RTC
from exabgp.bgp.message.update.nlri.bgpls import BGPLS
from exabgp.bgp.message.update.nlri.mup import MUP
from exabgp.bgp.message.update.nlri.mvpn import MVPN
from exabgp.bgp.message.update.nlri.collection import NLRICollection, MPNLRICollection

__all__ = [
    'NLRI',
    'CIDR',
    'INET',
    'Label',
    'IPVPN',
    'VPLS',
    'Flow',
    'EVPN',
    'RTC',
    'BGPLS',
    'MUP',
    'MVPN',
    'NLRICollection',
    'MPNLRICollection',
]
