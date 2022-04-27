# encoding: utf-8
"""
srv6/sidstructure.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""
import json
from struct import pack

from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation

# 3.2.1.  SRv6 SID Structure Sub-Sub-TLV
#
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | SRv6 Service  |    SRv6 Service               | Locator Block |
# | Data Sub-Sub  |    Data Sub-Sub-TLV           | Length        |
# | -TLV Type=1   |    Length                     |               |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Locator Node  | Function      | Argument      | Transposition |
# | Length        | Length        | Length        | Length        |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Transposition |
# | Offset        |
# +-+-+-+-+-+-+-+-+
#
#           Figure 5: SRv6 SID Structure Sub-Sub-TLV


@Srv6SidInformation.register()
class Srv6SidStructure:
    TLV = 1

    registered_subsubtlvs = dict()

    def __init__(self, loc_block_len, loc_node_len, func_len, arg_len, tpose_len, tpose_offset, packed=None):
        self.loc_block_len = loc_block_len
        self.loc_node_len = loc_node_len
        self.func_len = func_len
        self.arg_len = arg_len
        self.tpose_len = tpose_len
        self.tpose_offset = tpose_offset
        self.packed = self.pack()

    @classmethod
    def unpack(cls, data, length):
        loc_block_len = data[0]
        loc_node_len = data[1]
        func_len = data[2]
        arg_len = data[3]
        tpose_len = data[4]
        tpose_offset = data[5]

        return cls(
            loc_block_len=loc_block_len,
            loc_node_len=loc_node_len,
            func_len=func_len,
            arg_len=arg_len,
            tpose_len=tpose_len,
            tpose_offset=tpose_offset,
        )

    def pack(self):
        return (
            pack("!B", self.TLV)
            + pack("!H", 6)
            + pack("!B", self.loc_block_len)
            + pack("!B", self.loc_node_len)
            + pack("!B", self.func_len)
            + pack("!B", self.arg_len)
            + pack("!B", self.tpose_len)
            + pack("!B", self.tpose_offset)
        )

    def __str__(self):
        return "sid-structure [%d,%d,%d,%d,%d,%d]" % (
            self.loc_block_len,
            self.loc_node_len,
            self.func_len,
            self.arg_len,
            self.tpose_len,
            self.tpose_offset,
        )

    def json(self, compact=None):
        pairs = {
            "locator-block-length": self.loc_block_len,
            "locator-node-length": self.loc_node_len,
            "function-length": self.func_len,
            "argument-length": self.arg_len,
            "transposition-length": self.tpose_len,
            "transposition-offset": self.tpose_offset,
        }

        return '"structure": %s' % json.dumps(pairs)
