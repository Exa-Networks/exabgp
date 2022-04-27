# encoding: utf-8
"""
srv6/sidinformation.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""
from struct import pack, unpack

from exabgp.protocol.ip import IPv6

from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service
from exabgp.bgp.message.update.attribute.sr.srv6.generic import GenericSrv6ServiceDataSubSubTlv

# 3.1.  SRv6 SID Information Sub-TLV
#
#  0                   1                   2                   3
#  0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | SRv6 Service  |    SRv6 Service               |               |
# | Sub-TLV       |    Sub-TLV                    |               |
# | Type=1        |    Length                     |  RESERVED1    |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  SRv6 SID Value (16 octets)                                  //
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# | Svc SID Flags |   SRv6 Endpoint Behavior      |   RESERVED2   |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |  SRv6 Service Data Sub-Sub-TLVs                              //
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

#            Figure 3: SRv6 SID Information Sub-TLV


@Srv6L2Service.register()
@Srv6L3Service.register()
class Srv6SidInformation:
    TLV = 1

    registered_subsubtlvs = dict()

    def __init__(self, sid, behavior, subsubtlvs, packed=None):
        self.sid = sid
        self.behavior = behavior
        self.subsubtlvs = subsubtlvs
        self.packed = self.pack()

    @classmethod
    def register(cls):
        def register_subsubtlv(klass):
            code = klass.TLV
            if code in cls.registered_subsubtlvs:
                raise RuntimeError('only one class can be registered per SRv6 Service Sub-Sub-TLV type')
            cls.registered_subsubtlvs[code] = klass
            return klass

        return register_subsubtlv

    @classmethod
    def unpack(cls, data, length):
        sid = IPv6.unpack(data[1:17])
        behavior = unpack("!H", data[18:20])[0]
        subsubtlvs = []

        data = data[21:]
        while data:
            code = data[0]
            length = unpack("!H", data[1:3])[0]
            if code in cls.registered_subsubtlvs:
                subsubtlv = klass = cls.registered_subsubtlvs[code].unpack(data[3 : length + 3], length)
            else:
                subsubtlv = GenericSrv6ServiceDataSubSubTlv(code, data[3 : length + 3])
            subsubtlvs.append(subsubtlv)
            data = data[length + 3 :]

        return cls(sid=sid, behavior=behavior, subsubtlvs=subsubtlvs)

    def pack(self):
        subsubtlvs_packed = b"".join([_.pack() for _ in self.subsubtlvs])
        length = len(subsubtlvs_packed) + 21
        reserved, flags = 0, 0

        return (
            pack("!B", self.TLV)
            + pack("!H", length)
            + pack("!B", reserved)
            + self.sid.pack()
            + pack("!B", flags)
            + pack("!H", self.behavior)
            + pack("!B", reserved)
            + subsubtlvs_packed
        )

    def __str__(self):
        s = "sid-information [ sid:%s flags:0 endpoint_behavior:0x%x " % (str(self.sid), self.behavior)
        if len(self.subsubtlvs) != 0:
            s += " [ " + ", ".join([str(subsubtlv) for subsubtlv in self.subsubtlvs]) + " ]"
        s + " ]"
        return s

    def json(self, compact=None):
        s = '{ "sid": "%s", "flags": 0, "endpoint_behavior": %d'
        content = ", ".join(subsubtlv.json() for subsubtlv in self.subsubtlvs)
        if content:
            s += ", %s" % content
        s += " }"
        return s
