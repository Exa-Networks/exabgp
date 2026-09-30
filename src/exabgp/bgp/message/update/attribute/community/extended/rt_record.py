"""rt_record.py

Created by Thomas Mangin on <unset>
Copyright (c) 2009-2022 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity
from exabgp.bgp.message.update.attribute.community.extended.community import ExtendedCommunityBase
from exabgp.bgp.message.update.attribute.community.extended import rt
from exabgp.util.mypyc import trait

# draft-ietf-bess-service-chaining

# The subtype of a Route Target Record, and the name it is shown with
RT_RECORD_SUBTYPE = 0x13
RT_RECORD_DESCRIPTION = 'rtrecord'


@trait
class RTRecord:
    """A Route Target Record, one per Route Target format.

    Each format inherits its Route Target class and marks itself with this trait. mypyc
    cannot compile a class with two concrete bases, which is what RTRecord was: a
    RouteTarget, then inherited again next to the format's own Route Target class.
    """

    COMMUNITY_SUBTYPE: ClassVar[int] = RT_RECORD_SUBTYPE
    DESCRIPTION: ClassVar[str] = RT_RECORD_DESCRIPTION

    @staticmethod
    def from_rt(route_target: rt.RouteTarget) -> ExtendedCommunityBase:
        packed = route_target.pack_attribute(Negotiated.UNSET)
        return ExtendedCommunity.unpack_attribute(bytes(packed[0:1]) + bytes([RT_RECORD_SUBTYPE]) + bytes(packed[2:]))


# The Route Target class comes first, so its own COMMUNITY_SUBTYPE and DESCRIPTION would
# win over the trait's: each class names the Record's again.


class RTRecordASN2Number(rt.RouteTargetASN2Number, RTRecord):
    COMMUNITY_SUBTYPE: ClassVar[int] = RT_RECORD_SUBTYPE
    DESCRIPTION: ClassVar[str] = RT_RECORD_DESCRIPTION


ExtendedCommunity.register_subtype(RTRecordASN2Number)


class RTRecordIPNumber(rt.RouteTargetIPNumber, RTRecord):
    COMMUNITY_SUBTYPE: ClassVar[int] = RT_RECORD_SUBTYPE
    DESCRIPTION: ClassVar[str] = RT_RECORD_DESCRIPTION


ExtendedCommunity.register_subtype(RTRecordIPNumber)


class RTRecordASN4Number(rt.RouteTargetASN4Number, RTRecord):
    COMMUNITY_SUBTYPE: ClassVar[int] = RT_RECORD_SUBTYPE
    DESCRIPTION: ClassVar[str] = RT_RECORD_DESCRIPTION


ExtendedCommunity.register_subtype(RTRecordASN4Number)
