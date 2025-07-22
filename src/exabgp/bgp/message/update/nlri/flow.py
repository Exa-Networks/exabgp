# encoding: utf-8
"""
flow.py

Created by Thomas Mangin on 2010-01-14.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI
from exabgp.bgp.message.action import Action
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.protocol.ip import NoNextHop
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.cidr import CIDR


@NLRI.register(AFI.ipv4, SAFI.flow_ip)
@NLRI.register(AFI.ipv6, SAFI.flow_ip)
@NLRI.register(AFI.ipv4, SAFI.flow_vpn)
@NLRI.register(AFI.ipv6, SAFI.flow_vpn)
class Flow(NLRI):
    def __init__(self, afi=AFI.ipv4, safi=SAFI.flow_ip, action=Action.UNSET):
        super().__init__(afi, safi, action)
        self.rules = {}
        self.nexthop = NoNextHop
        self.rd = RouteDistinguisher.NORD

    def add(self, rule):
        ID = rule.ID
        if ID in (1, 2):  # Destination or Source
            if self.rules.get(1) and self.rules.get(2):
                if self.rules[1][0].afi != self.rules[2][0].afi:
                    return False
        self.rules.setdefault(ID, []).append(rule)
        return True

    def extensive(self, afi=False, rib=None):
        nexthop = ' next-hop %s' % self.nexthop if self.nexthop is not NoNextHop else ''
        rd = '' if self.rd is RouteDistinguisher.NORD else str(self.rd)
        rules = ' '.join(str(r) for r in self.rules.get(1, []))
        return f'flow {rules}{rd}{nexthop}'

    def __str__(self):
        return self.extensive()


class EdgeFlow(Flow):
    def __init__(self, device_id=None, afi=AFI.ipv4, safi=SAFI.flow_ip, action=Action.UNSET):
        super().__init__(afi, safi, action)
        self.device_id = device_id

    def extensive(self, afi=False, rib=None):
        base = super().extensive(afi, rib)
        return f"{base} device-id {self.device_id}" if self.device_id else base


class Flow4Source(NLRI):
    ID = 2

    def __init__(self, pack, mask):
        super().__init__(AFI.ipv4, SAFI.unicast)
        self.cidr = CIDR(pack, mask)

    def __str__(self):
        return f"source {self.cidr}"
