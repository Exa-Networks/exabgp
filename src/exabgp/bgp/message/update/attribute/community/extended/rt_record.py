"""rt_record.py

Created by Thomas Mangin on <unset>
Copyright (c) 2009-2022 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar, Type, TypeVar

from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended import rt

# draft-ietf-bess-service-chaining

T = TypeVar('T', bound='RTRecord')


class RTRecord(rt.RouteTarget):
    COMMUNITY_SUBTYPE: ClassVar[int] = 0x13
    DESCRIPTION: ClassVar[str] = 'rtrecord'

    @classmethod
    def from_rt(cls: Type[T], route_target: rt.RouteTarget) -> T:
        packed = route_target.pack_attribute(None)  # type: ignore[arg-type]
        return cls.unpack_attribute(packed[0:1] + bytes([cls.COMMUNITY_SUBTYPE]) + packed[2:])  # type: ignore[return-value]


@ExtendedCommunity.register
class RTRecordASN2Number(RTRecord, rt.RouteTargetASN2Number):
    pass


@ExtendedCommunity.register
class RTRecordIPNumber(RTRecord, rt.RouteTargetIPNumber):
    pass


@ExtendedCommunity.register
class RTRecordASN4Number(RTRecord, rt.RouteTargetASN4Number):
    pass
