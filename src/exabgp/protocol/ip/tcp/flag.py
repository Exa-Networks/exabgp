
"""tcpflags.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar, Dict

from exabgp.protocol.resource import BitResource


# ====================================================================== TCPFlag
# https://www.iana.org/assignments/tcp-header-flags


class TCPFlag(BitResource):
    NAME: ClassVar[str] = 'tcp flag'

    FIN: ClassVar[int] = 0x01
    SYN: ClassVar[int] = 0x02
    RST: ClassVar[int] = 0x04
    PUSH: ClassVar[int] = 0x08
    ACK: ClassVar[int] = 0x10
    URG: ClassVar[int] = 0x20
    ECE: ClassVar[int] = 0x40
    CWR: ClassVar[int] = 0x80
    NS: ClassVar[int] = 0x100

    codes: ClassVar[Dict[str, int]] = dict(
        (k.lower().replace('_', '-'), v)
        for (k, v) in {
            'FIN': FIN,
            'SYN': SYN,
            'RST': RST,
            'PUSH': PUSH,
            'ACK': ACK,
            'URG': URG,
            'ECE': ECE,
            'CWR': CWR,
            'NS': NS,
        }.items()
    )

    names: ClassVar[Dict[int, str]] = dict([(value, name) for (name, value) in codes.items()])


# Backward compatibility
TCPFlag.codes['urgent'] = TCPFlag.URG
