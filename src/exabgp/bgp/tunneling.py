# encoding: utf-8
"""
tunneling.py

Created by Thomas Mangin on 2024-07-21.
Copyright (c) 2009-2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.ip import IP
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message.update.nlri.label import Label as MPLS
from exabgp.bgp.message import Action
from exabgp.bgp.message.update.nlri.qualifier import Labels

class Tunneling:
    def __init__(self, neighbor):
        self.neighbor = neighbor

    def create(self, destination, next_hop):
        """
        Creates a quantum tunnel to a destination.
        """
        # This is a simplified implementation. In a real-world scenario,
        # this would involve a more complex mechanism to create a tunnel.
        label = [100]  # Example label
        nlri = MPLS(AFI.ipv4, SAFI.mpls_vpn, Action.ANNOUNCE)
        nlri.nexthop = IP.create(next_hop)
        nlri.labels = Labels(label)
        return nlri
