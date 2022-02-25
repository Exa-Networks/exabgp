# encoding: utf-8
"""
srv6/l3service.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""
from struct import pack, unpack

from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.srv6.generic import GenericSrv6ServiceSubTlv

# 2.  SRv6 Services TLVs
# 
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   TLV Type    |         TLV Length            |   RESERVED    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |   SRv6 Service Sub-TLVs                                      //
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#
#                   Figure 1: SRv6 Service TLVs

@PrefixSid.register()
class Srv6L3Service(object):
    TLV = 5

    registered_subtlvs = dict()

    def __init__(self, subtlvs, packed=None):
        self.subtlvs = subtlvs
        self.packed = self.pack()

    @classmethod
    def register(cls):
        def register_subtlv(klass):
            scode = klass.TLV
            if scode in cls.registered_subtlvs:
                raise RuntimeError('only one class can be registered per SRv6 Service Sub-TLV type')
            cls.registered_subtlvs[scode] = klass
            return klass

        return register_subtlv

    @classmethod
    def unpack(cls, data, length):
        subtlvs = []

        # First byte is eserved
        data = data[1:]
        while data:
            code = data[0]
            length = unpack("!H", data[1:3])[0]
            if code in cls.registered_subtlvs:
                subtlv = klass = cls.registered_subtlvs[code].unpack(data[3:length+3], length)
            else:
                subtlv = GenericSrv6ServiceSubTlv(code, data[3:length+3])
            subtlvs.append(subtlv)
            data = data[length+3:]

        return cls(subtlvs=subtlvs)

    def pack(self):
        subtlvs_packed = b"".join([_.pack() for _ in self.subtlvs])
        length = len(subtlvs_packed) + 1
        reserved = 0

        return (
            pack("!B", self.TLV)
            + pack("!H", length)
            + pack("!B", reserved)
            + subtlvs_packed
        )

    def __str__(self):
        return "l3-service [ " + ", ".join([str(subtlv) for subtlv in self.subtlvs]) + " ]"

    def json(self, compact=None):
        content = "[ " + ", ".join(subtlv.json() for subtlv in self.subtlvs) + " ]"
        return '"l3-service": %s' % content
