"""A Route Target Record keeps the format of its Route Target and the Record subtype.

RTRecord used to inherit RouteTarget next to each format's Route Target class. mypyc cannot
compile two concrete bases, so it became a trait and each format names its subtype again:
these hold the result to what the diamond produced.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.community.extended.rt import (
    RouteTarget,
    RouteTargetASN2Number,
    RouteTargetASN4Number,
    RouteTargetIPNumber,
)
from exabgp.bgp.message.update.attribute.community.extended.rt_record import (
    RTRecord,
    RTRecordASN2Number,
    RTRecordASN4Number,
    RTRecordIPNumber,
)
from exabgp.bgp.message.open.asn import ASN

TARGETS = [
    (RouteTargetASN2Number.make_route_target(ASN(64512), 22), RTRecordASN2Number),
    (RouteTargetIPNumber.make_route_target('192.0.2.1', 22), RTRecordIPNumber),
    (RouteTargetASN4Number.make_route_target(ASN(4200000000), 22), RTRecordASN4Number),
]


@pytest.mark.parametrize(('target', 'record_class'), TARGETS)
def test_a_record_keeps_the_format_of_its_route_target(
    target: RouteTarget, record_class: type[RTRecordASN2Number | RTRecordIPNumber | RTRecordASN4Number]
) -> None:
    record = RTRecord.from_rt(target)
    assert type(record) is record_class
    assert isinstance(record, RTRecord)
    assert isinstance(record, type(target))


@pytest.mark.parametrize(('target', 'record_class'), TARGETS)
def test_a_record_is_the_route_target_with_the_record_subtype(
    target: RouteTarget, record_class: type[RTRecordASN2Number | RTRecordIPNumber | RTRecordASN4Number]
) -> None:
    record = RTRecord.from_rt(target)
    packed = bytes(record.pack_attribute(Negotiated.UNSET))
    original = bytes(target.pack_attribute(Negotiated.UNSET))
    assert packed[1] == 0x13
    assert packed[0] == original[0] and packed[2:] == original[2:]
    assert record_class.COMMUNITY_SUBTYPE == 0x13
    assert record_class.DESCRIPTION == 'rtrecord'
