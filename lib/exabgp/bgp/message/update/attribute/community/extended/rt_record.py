from exabgp.util import character
from exabgp.util import concat_bytes
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended import rt

# draft-ietf-bess-service-chaining


class RTRecord(rt.RouteTarget):
    COMMUNITY_SUBTYPE = 0x13
    DESCRIPTION = "rtrecord"

    @classmethod
    def from_rt(cls, route_target):
        packed = route_target.pack()
        return cls.unpack(concat_bytes(packed[0:1], character(cls.COMMUNITY_SUBTYPE), packed[2:]))


@ExtendedCommunity.register
class RTRecordASN2Number(RTRecord, rt.RouteTargetASN2Number):
    pass


@ExtendedCommunity.register
class RTRecordIPNumber(RTRecord, rt.RouteTargetIPNumber):
    pass


@ExtendedCommunity.register
class RTRecordASN4Number(RTRecord, rt.RouteTargetASN4Number):
    pass
