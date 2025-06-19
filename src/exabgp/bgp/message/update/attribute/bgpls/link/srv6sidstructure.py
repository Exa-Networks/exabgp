# encoding: utf-8
"""
srv6endx.py

Created by Quentin De Muynck
Copyright (c) 2025 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json
from struct import unpack
from exabgp.util import hexstring

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.bgp.message.update.attribute.bgpls.linkstate import FlagLS
from exabgp.bgp.message.update.attribute.bgpls.link.srv6endx import Srv6EndX


#     RFC 9514 : 8.  SRv6 SID Structure TLV
#     0                   1                   2                   3
#     0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |               Type            |          Length               |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#    |    LB Length  |  LN Length    | Fun. Length   |  Arg. Length  |
#    +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                      Figure 10: SRv6 SID Structure TLV

@Srv6EndX.register()
class Srv6SidStructure:
    TLV = 1252

    def __init__(self, loc_block_len, loc_node_len, func_len, arg_len):
        self.loc_block_len = loc_block_len
        self.loc_node_len = loc_node_len
        self.func_len = func_len
        self.arg_len = arg_len

    @classmethod
    def unpack(cls, data):
        loc_block_len = data[0]
        loc_node_len = data[1]
        func_len = data[2]
        arg_len = data[3]

        return cls(
            loc_block_len=loc_block_len,
            loc_node_len=loc_node_len,
            func_len=func_len,
            arg_len=arg_len,
        )
    
    def __str__(self):
        return 'sid-structure [%d,%d,%d,%d,]' % (
            self.loc_block_len,
            self.loc_node_len,
            self.func_len,
            self.arg_len,
        )
    
    def json(self):
        return {'structure': 
        {
                'loc_block_len': self.loc_block_len,
                'loc_node_len': self.loc_node_len,
                'func_len': self.func_len,
                'arg_len': self.arg_len,
            }
        }

