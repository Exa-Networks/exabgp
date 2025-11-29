"""inet/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from ipaddress import IPv4Address, IPv6Address, ip_address
from struct import pack
from typing import Any

from exabgp.bgp.message.update.attribute.sr.labelindex import SrLabelIndex
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb
from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service
from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation
from exabgp.bgp.message.update.attribute.sr.srv6.sidstructure import Srv6SidStructure
from exabgp.bgp.message.update.nlri.mup import (
    DirectSegmentDiscoveryRoute,
    InterworkSegmentDiscoveryRoute,
    Type1SessionTransformedRoute,
    Type2SessionTransformedRoute,
)
from exabgp.bgp.message.update.nlri.mvpn import SharedJoin, SourceAD, SourceJoin
from exabgp.bgp.message.update.nlri.qualifier import Labels, RouteDistinguisher
from exabgp.protocol.family import AFI
from exabgp.protocol.ip import IPv4, IPv6

# MPLS/SR configuration constants
SRGB_TUPLE_SIZE = 2  # SRGB tuple consists of (start, range)
ASN_MAX_VALUE = 4294967295  # Maximum value for 32-bit ASN
TEID_MAX_BITS = 32  # Maximum TEID length in bits


def label(tokeniser: Any) -> Labels:
    labels: list[int] = []
    value = tokeniser()

    if value == '[':
        while True:
            value = tokeniser()
            if value == ']':
                break
            labels.append(int(value))
    else:
        labels.append(int(value))

    return Labels(labels)


def route_distinguisher(tokeniser: Any) -> RouteDistinguisher:
    data = tokeniser()

    separator = data.find(':')
    if separator > 0:
        prefix = data[:separator]
        suffix = int(data[separator + 1 :])

    if '.' in prefix:
        data_list: list[bytes] = [bytes([0, 1])]
        data_list.extend([bytes([int(_)]) for _ in prefix.split('.')])
        data_list.extend([bytes([suffix >> 8]), bytes([suffix & 0xFF])])
        rtd = b''.join(data_list)
    else:
        number = int(prefix)
        if number < pow(2, 16) and suffix < pow(2, 32):
            rtd = bytes([0, 0]) + pack('!H', number) + pack('!L', suffix)
        elif number < pow(2, 32) and suffix < pow(2, 16):
            rtd = bytes([0, 2]) + pack('!L', number) + pack('!H', suffix)
        else:
            raise ValueError(f'invalid route-distinguisher {data}')

    return RouteDistinguisher(rtd)


# [ 300, [ ( 800000,100 ), ( 1000000,5000 ) ] ]
def prefix_sid(tokeniser: Any) -> PrefixSid:  # noqa: C901
    sr_attrs: list[SrLabelIndex | SrGb] = []
    srgbs: list[tuple[int, int]] = []
    srgb_data: list[Any] = []
    value = tokeniser()
    get_range = False
    consume_extra = False
    try:
        if value == '[':
            label_sid = tokeniser()
            while True:
                value = tokeniser()
                if value == '[':
                    consume_extra = True
                    continue
                if value == ',':
                    continue
                if value == '(':
                    while True:
                        value = tokeniser()
                        if value == ')':
                            break
                        if value == ',':
                            get_range = True
                            continue
                        if get_range:
                            srange = value
                            get_range = False
                        else:
                            base = value
                if value == ')':
                    srgb_data.append((base, srange))
                    continue
                if value == ']':
                    break
        if consume_extra:
            tokeniser()
    except Exception as e:
        raise ValueError(f'could not parse BGP PrefixSid attribute: {e}') from None

    if int(label_sid) < pow(2, 32):
        sr_attrs.append(SrLabelIndex(int(label_sid)))

    for srgb in srgb_data:
        if len(srgb) == SRGB_TUPLE_SIZE and int(srgb[0]) < pow(2, 24) and int(srgb[1]) < pow(2, 24):
            srgbs.append((int(srgb[0]), int(srgb[1])))
        else:
            raise ValueError('could not parse SRGB tupple')

    if srgbs:
        sr_attrs.append(SrGb(srgbs))

    return PrefixSid(sr_attrs)


# ( [l2-service|l3-service] <SID:ipv6-addr> )
# ( [l2-service|l3-service] <SID:ipv6-addr> <Endpoint Behavior:int> )
# ( [l2-service|l3-service] <SID:ipv6-addr> <Endpoint Behavior:int> [<LBL:int>, <LNL:int>, <FL:int>, <AL:int>, <Tpose-len:int>, <Tpose-offset:int>] )
def prefix_sid_srv6(tokeniser: Any) -> PrefixSid:  # type: ignore[return]
    value = tokeniser()
    if value != '(':
        raise Exception(f"expect '(', but received '{value}'")

    service_type = tokeniser()
    if service_type not in ['l3-service', 'l2-service']:
        raise Exception(f"expect 'l3-service' or 'l2-service', but received '{value}'")

    sid = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
    behavior = 0xFFFF
    subtlvs: list[Srv6SidInformation] = []
    subsubtlvs: list[Srv6SidStructure] = []
    value = tokeniser()
    if value != ')':
        base = 10 if not value.startswith('0x') else 16
        behavior = int(value, base)
        value = tokeniser()
        if value == '[':
            values = []
            for i in range(6):
                if i != 0:
                    value = tokeniser()
                    if value != ',':
                        raise Exception(f"expect ',', but received '{value}'")
                value = tokeniser()
                base = 10 if not value.startswith('0x') else 16
                values.append(int(value, base))

            value = tokeniser()
            if value != ']':
                raise Exception(f"expect ']', but received '{value}'")

            value = tokeniser()

            subsubtlvs.append(
                Srv6SidStructure(
                    loc_block_len=values[0],
                    loc_node_len=values[1],
                    func_len=values[2],
                    arg_len=values[3],
                    tpose_len=values[4],
                    tpose_offset=values[5],
                ),
            )

    subtlvs.append(
        Srv6SidInformation(
            sid=sid,
            behavior=behavior,
            subsubtlvs=subsubtlvs,  # type: ignore[arg-type]
        ),
    )

    if value != ')':
        raise Exception(f"expect ')', but received '{value}'")

    if service_type == 'l3-service':
        return PrefixSid([Srv6L3Service(subtlvs=subtlvs)])  # type: ignore[arg-type]
    if service_type == 'l2-service':
        return PrefixSid([Srv6L2Service(subtlvs=subtlvs)])  # type: ignore[arg-type]


def parse_ip_prefix(tokeninser: str) -> tuple[IPv4 | IPv6, int]:
    addrstr, length = tokeninser.split('/')
    if length is None:
        raise Exception(f"unexpect prefix format '{tokeninser}'")

    if not length.isdigit():
        raise Exception(f"unexpect prefix format '{tokeninser}'")

    addr = ip_address(addrstr)
    ip: IPv4 | IPv6
    if isinstance(addr, IPv4Address):
        ip = IPv4.unpack_ipv4(IPv4.pton(addrstr))
    elif isinstance(addr, IPv6Address):
        ip = IPv6.unpack_ipv6(IPv6.pton(addrstr))
    else:
        raise Exception(f"unexpect ipaddress format '{addrstr}'")
    return ip, int(length)


# shared-join rp <ip> group <ip> rd <rd> source-as <source-as>
def mvpn_sharedjoin(tokeniser: Any, afi: AFI, action: Any) -> SharedJoin:
    sourceip: IPv4 | IPv6
    groupip: IPv4 | IPv6
    if afi == AFI.ipv4:
        tokeniser.consume('rp')
        sourceip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
        tokeniser.consume('group')
        groupip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        tokeniser.consume('rp')
        sourceip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
        tokeniser.consume('group')
        groupip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
    else:
        raise Exception(f'unexpect afi: {afi}')

    tokeniser.consume('rd')
    rd = route_distinguisher(tokeniser)

    tokeniser.consume('source-as')
    value = tokeniser()
    if not value.isdigit():
        raise Exception(f"expect source-as to be a integer in the range 0-{ASN_MAX_VALUE}, but received '{value}'")
    asnum = int(value)
    if asnum > ASN_MAX_VALUE:
        raise Exception(f"expect source-as to be a integer in the range 0-{ASN_MAX_VALUE}, but received '{value}'")

    return SharedJoin(rd=rd, afi=afi, source=sourceip, group=groupip, source_as=asnum, action=action)


# source-join source <ip> group <ip> rd <rd> source-as <source-as>
def mvpn_sourcejoin(tokeniser: Any, afi: AFI, action: Any) -> SourceJoin:
    sourceip: IPv4 | IPv6
    groupip: IPv4 | IPv6
    if afi == AFI.ipv4:
        tokeniser.consume('source')
        sourceip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
        tokeniser.consume('group')
        groupip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        tokeniser.consume('source')
        sourceip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
        tokeniser.consume('group')
        groupip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
    else:
        raise Exception(f'unexpect afi: {afi}')

    tokeniser.consume('rd')
    rd = route_distinguisher(tokeniser)

    tokeniser.consume('source-as')
    value = tokeniser()
    if not value.isdigit():
        raise Exception(f"expect source-as to be a integer in the range 0-{ASN_MAX_VALUE}, but received '{value}'")
    asnum = int(value)
    if asnum > ASN_MAX_VALUE:
        raise Exception(f"expect source-as to be a integer in the range 0-{ASN_MAX_VALUE}, but received '{value}'")

    return SourceJoin(rd=rd, afi=afi, source=sourceip, group=groupip, source_as=asnum, action=action)


#'source-ad source <ip address> group <ip address> rd <rd>'
def mvpn_sourcead(tokeniser: Any, afi: AFI, action: Any) -> SourceAD:
    sourceip: IPv4 | IPv6
    groupip: IPv4 | IPv6
    if afi == AFI.ipv4:
        tokeniser.consume('source')
        sourceip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
        tokeniser.consume('group')
        groupip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        tokeniser.consume('source')
        sourceip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
        tokeniser.consume('group')
        groupip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
    else:
        raise Exception(f'unexpect afi: {afi}')

    tokeniser.consume('rd')
    rd = route_distinguisher(tokeniser)

    return SourceAD(rd=rd, afi=afi, source=sourceip, group=groupip, action=action)


# 'mup-isd <ip prefix> rd <rd>',
def srv6_mup_isd(tokeniser: Any, afi: AFI) -> InterworkSegmentDiscoveryRoute:
    prefix_ip, prefix_len = parse_ip_prefix(tokeniser())

    value = tokeniser()
    if value != 'rd':
        raise Exception(f"expect rd, but received '{value}'")
    rd = route_distinguisher(tokeniser)

    return InterworkSegmentDiscoveryRoute(
        rd=rd,
        prefix_ip_len=prefix_len,
        prefix_ip=prefix_ip,
        afi=afi,
    )


# 'mup-dsd <ip address> rd <rd>',
def srv6_mup_dsd(tokeniser: Any, afi: AFI) -> DirectSegmentDiscoveryRoute:
    ip: IPv4 | IPv6
    if afi == AFI.ipv4:
        ip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        ip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
    else:
        raise Exception(f'unexpect afi: {afi}')

    value = tokeniser()
    if value != 'rd':
        raise Exception(f"expect rd, but received '{value}'")
    rd = route_distinguisher(tokeniser)

    return DirectSegmentDiscoveryRoute(
        rd=rd,
        ip=ip,
        afi=afi,
    )


# 'mup-t1st <ip prefix> rd <rd> teid <teid> qfi <qfi> endpoint <endpoint> [source <source>]',
def srv6_mup_t1st(tokeniser: Any, afi: AFI) -> Type1SessionTransformedRoute:
    prefix_ip, prefix_ip_len = parse_ip_prefix(tokeniser())

    tokeniser.consume('rd')
    rd = route_distinguisher(tokeniser)

    tokeniser.consume('teid')
    value = tokeniser()
    if not value.isdigit():
        raise Exception(f"expect teid to be a number, but received '{value}'")
    teid = int(value)

    tokeniser.consume('qfi')
    value = tokeniser()
    if not value.isdigit():
        raise Exception(f"expect qfi to be a number, but received '{value}'")
    qfi = int(value)

    tokeniser.consume('endpoint')
    endpoint_ip: IPv4 | IPv6
    if afi == AFI.ipv4:
        endpoint_ip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        endpoint_ip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
    else:
        raise Exception(f'unexpect afi: {afi}')

    source_ip_len = 0
    source_ip: bytes | IPv4 | IPv6 = b''

    if tokeniser.consume_if_match('source'):
        if afi == AFI.ipv4:
            source_ip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
            source_ip_len = 32
        elif afi == AFI.ipv6:
            source_ip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
            source_ip_len = 128
        else:
            raise Exception(f'unexpect afi: {afi}')

    return Type1SessionTransformedRoute(
        rd=rd,
        prefix_ip_len=prefix_ip_len,
        prefix_ip=prefix_ip,
        teid=teid,
        qfi=qfi,
        endpoint_ip_len=endpoint_ip.bits,
        endpoint_ip=endpoint_ip,
        source_ip_len=source_ip_len,
        source_ip=source_ip,
        afi=afi,
    )


# 'mup-t2st <endpoint address> rd <rd> teid <teid>',
def srv6_mup_t2st(tokeniser: Any, afi: AFI) -> Type2SessionTransformedRoute:
    endpoint_ip: IPv4 | IPv6
    if afi == AFI.ipv4:
        endpoint_ip = IPv4.unpack_ipv4(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        endpoint_ip = IPv6.unpack_ipv6(IPv6.pton(tokeniser()))
    else:
        raise Exception(f'unexpect afi: {afi}')

    value = tokeniser()
    if value != 'rd':
        raise Exception(f"expect rd, but received '{value}'")

    rd = route_distinguisher(tokeniser)

    value = tokeniser()
    if value != 'teid':
        raise Exception(f"expect teid, but received '{value}'")

    teids = tokeniser().split('/')
    if len(teids) != SRGB_TUPLE_SIZE:
        raise Exception(f'unexpect teid format, this expect format <teid>/<length, expect 0 ~ {TEID_MAX_BITS}')

    teid = int(teids[0])
    teid_len = int(teids[1])

    if not (0 <= teid_len <= TEID_MAX_BITS):
        raise Exception(f'unexpect teid format, this expect format <teid>/<length, expect 0 ~ {TEID_MAX_BITS}>')

    if teid >= pow(2, teid_len):
        raise Exception(f'unexpect teid format, we can not store {teid} using {teid_len} bits')

    return Type2SessionTransformedRoute(
        rd=rd,
        endpoint_len=endpoint_ip.bits + teid_len,  # 32 or 128
        endpoint_ip=endpoint_ip,
        teid=teid,
        afi=afi,
    )
