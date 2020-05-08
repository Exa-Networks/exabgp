# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.util import character

from exabgp.protocol.resource import Resource


# ===================================================================== Protocol
# https://www.iana.org/assignments/protocol-numbers/


class Protocol(Resource):
    NAME = 'protocol'

    ICMP = 0x01
    IGMP = 0x02
    TCP = 0x06
    EGP = 0x08
    UDP = 0x11
    RSVP = 0x2E
    GRE = 0x2F
    ESP = 0x32
    AH = 0x33
    OSPF = 0x59
    IPIP = 0x5E
    PIM = 0x67
    SCTP = 0x84

    codes = dict(
        (k.lower().replace('_', '-'), v)
        for (k, v) in {
            'ICMP': ICMP,
            'IGMP': IGMP,
            'TCP': TCP,
            'EGP': EGP,
            'UDP': UDP,
            'RSVP': RSVP,
            'GRE': GRE,
            'ESP': ESP,
            'AH': AH,
            'OSPF': OSPF,
            'IPIP': IPIP,
            'PIM': PIM,
            'SCTP': SCTP,
        }.items()
    )

    names = dict([(r, l) for (l, r) in codes.items()])

    def pack(self):
        return character(self)
