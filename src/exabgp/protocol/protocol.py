"""protocol.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.protocol.resource import Resource


# ===================================================================== Protocol
# https://www.iana.org/assignments/protocol-numbers/


class Protocol(Resource):
    NAME: ClassVar[str] = 'protocol'

    ICMP: ClassVar[int] = 0x01
    IGMP: ClassVar[int] = 0x02
    TCP: ClassVar[int] = 0x06
    EGP: ClassVar[int] = 0x08
    UDP: ClassVar[int] = 0x11
    RSVP: ClassVar[int] = 0x2E
    GRE: ClassVar[int] = 0x2F
    ESP: ClassVar[int] = 0x32
    AH: ClassVar[int] = 0x33
    OSPF: ClassVar[int] = 0x59
    IPIP: ClassVar[int] = 0x5E
    PIM: ClassVar[int] = 0x67
    SCTP: ClassVar[int] = 0x84

    codes: ClassVar = dict(
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

    names: ClassVar = dict([(value, name) for (name, value) in codes.items()])

    def pack(self) -> bytes:
        return bytes([self.value])
