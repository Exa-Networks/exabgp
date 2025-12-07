"""mvpn/__init__.py

BGP MVPN (Multicast VPN) NLRI Implementation.

Reference: RFC 6514 - BGP Encodings and Procedures for Multicast in MPLS/BGP IP VPNs
           https://datatracker.ietf.org/doc/html/rfc6514

MVPN NLRI Format (Section 4):
+-----------------------------------+
|    Route Type (1 octet)           |
+-----------------------------------+
|    Length (1 octet)               |
+-----------------------------------+
|    Route Type specific (variable) |
+-----------------------------------+

Route Types (Section 4):
- Type 1: Intra-AS I-PMSI A-D Route (not implemented)
- Type 2: Inter-AS I-PMSI A-D Route (not implemented)
- Type 3: S-PMSI A-D Route - SourceAD
- Type 4: Leaf A-D Route (not implemented)
- Type 5: Source Active A-D Route - SourceJoin
- Type 6: Shared Tree Join Route - SharedJoin
- Type 7: Source Tree Join Route (not implemented)

AFI/SAFI: IPv4 (1) or IPv6 (2) / MCAST-VPN (5)

Wire Format Reference: doc/RFC_WIRE_FORMAT_REFERENCE.md#mvpn-rfc-6514

Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

# Every MVPN should be imported from this file
# as it makes sure that all the registering decorator are run

# flake8: noqa: F401,E261

from __future__ import annotations

from exabgp.bgp.message.update.nlri.mvpn.nlri import MVPN

from exabgp.bgp.message.update.nlri.mvpn.sourcead import SourceAD
from exabgp.bgp.message.update.nlri.mvpn.sourcejoin import SourceJoin
from exabgp.bgp.message.update.nlri.mvpn.sharedjoin import SharedJoin

__all__ = [
    'MVPN',
    'SourceAD',
    'SourceJoin',
    'SharedJoin',
]
