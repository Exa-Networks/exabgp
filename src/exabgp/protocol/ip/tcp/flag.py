# encoding: utf-8
"""
tcpflags.py

Created by Thomas Mangin on 2010-02-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.protocol.resource import BitResource


# ====================================================================== TCPFlag
# https://www.iana.org/assignments/tcp-header-flags


class TCPFlag(BitResource):
    NAME = 'tcp flag'

    FIN = 0x01
    SYN = 0x02
    RST = 0x04
    PUSH = 0x08
    ACK = 0x10
    URGENT = 0x20

    codes = dict(
        (k.lower().replace('_', '-'), v)
        for (k, v) in {'FIN': FIN, 'SYN': SYN, 'RST': RST, 'PUSH': PUSH, 'ACK': ACK, 'URGENT': URGENT,}.items()
    )

    names = dict([(r, l) for (l, r) in codes.items()])
