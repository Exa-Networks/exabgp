"""bgpls/__init__.py

BGP-LS (Link State) NLRI Implementation.

References:
    RFC 7752 - North-Bound Distribution of Link-State and TE Information Using BGP
               https://datatracker.ietf.org/doc/html/rfc7752
    RFC 9513 - BGP-LS Extensions for SRv6
               https://datatracker.ietf.org/doc/html/rfc9513

BGP-LS NLRI Format (RFC 7752 Section 3.2):
+-----------------------------------+
|    NLRI Type (2 octets)           |
+-----------------------------------+
|    Total NLRI Length (2 octets)   |
+-----------------------------------+
|    NLRI Value (variable)          |
+-----------------------------------+

NLRI Types (RFC 7752 Section 3.2.1):
- Type 1: Node NLRI - NODE
- Type 2: Link NLRI - LINK
- Type 3: IPv4 Topology Prefix NLRI - PREFIXv4
- Type 4: IPv6 Topology Prefix NLRI - PREFIXv6
- Type 6: SRv6 SID NLRI - SRv6SID (RFC 9513)

AFI/SAFI: BGP-LS (16388) / BGP-LS (71)

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#bgp-ls-rfc-7752--rfc-9552

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every BGP LINK_STATE NLRI should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.nlri.bgpls.nlri import BGPLS

from exabgp.bgp.message.update.nlri.bgpls.node import NODE
from exabgp.bgp.message.update.nlri.bgpls.link import LINK
from exabgp.bgp.message.update.nlri.bgpls.prefixv4 import PREFIXv4
from exabgp.bgp.message.update.nlri.bgpls.prefixv6 import PREFIXv6
from exabgp.bgp.message.update.nlri.bgpls.srv6sid import SRv6SID

__all__ = [
    'BGPLS',
    'NODE',
    'LINK',
    'PREFIXv4',
    'PREFIXv6',
    'SRv6SID',
]
