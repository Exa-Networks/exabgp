# encoding: utf-8
"""
inet/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack
from ipaddress import ip_address
from ipaddress import IPv4Address
from ipaddress import IPv6Address
from exabgp.protocol.ip import IPv4
from exabgp.protocol.ip import IPv6
from exabgp.protocol.family import AFI

from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.labelindex import SrLabelIndex
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb
from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service
from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation
from exabgp.bgp.message.update.attribute.sr.srv6.sidstructure import Srv6SidStructure
from exabgp.bgp.message.update.nlri.mup import InterworkSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.mup import DirectSegmentDiscoveryRoute
from exabgp.bgp.message.update.nlri.mup import Type1SessionTransformedRoute
from exabgp.bgp.message.update.nlri.mup import Type2SessionTransformedRoute
from exabgp.bgp.message.update.nlri.mvpn import SourceAD
from exabgp.bgp.message.update.nlri.mvpn import SourceJoin
from exabgp.bgp.message.update.nlri.mvpn import SharedJoin


def label(tokeniser):
    labels = []
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


def route_distinguisher(tokeniser):
    data = tokeniser()

    separator = data.find(':')
    if separator > 0:
        prefix = data[:separator]
        suffix = int(data[separator + 1 :])

    if '.' in prefix:
        data = [bytes([0, 1])]
        data.extend([bytes([int(_)]) for _ in prefix.split('.')])
        data.extend([bytes([suffix >> 8]), bytes([suffix & 0xFF])])
        rtd = b''.join(data)
    else:
        number = int(prefix)
        if number < pow(2, 16) and suffix < pow(2, 32):
            rtd = bytes([0, 0]) + pack('!H', number) + pack('!L', suffix)
        elif number < pow(2, 32) and suffix < pow(2, 16):
            rtd = bytes([0, 2]) + pack('!L', number) + pack('!H', suffix)
        else:
            raise ValueError('invalid route-distinguisher %s' % data)

    return RouteDistinguisher(rtd)


# [ 300, [ ( 800000,100 ), ( 1000000,5000 ) ] ]
def prefix_sid(tokeniser):  # noqa: C901
    sr_attrs = []
    srgbs = []
    srgb_data = []
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
        raise ValueError('could not parse BGP PrefixSid attribute: {}'.format(e))

    if int(label_sid) < pow(2, 32):
        sr_attrs.append(SrLabelIndex(int(label_sid)))

    for srgb in srgb_data:
        if len(srgb) == 2 and int(srgb[0]) < pow(2, 24) and int(srgb[1]) < pow(2, 24):
            srgbs.append((int(srgb[0]), int(srgb[1])))
        else:
            raise ValueError('could not parse SRGB tupple')

    if srgbs:
        sr_attrs.append(SrGb(srgbs))

    return PrefixSid(sr_attrs)


# ( [l2-service|l3-service] <SID:ipv6-addr> )
# ( [l2-service|l3-service] <SID:ipv6-addr> <Endpoint Behavior:int> )
# ( [l2-service|l3-service] <SID:ipv6-addr> <Endpoint Behavior:int> [<LBL:int>, <LNL:int>, <FL:int>, <AL:int>, <Tpose-len:int>, <Tpose-offset:int>] )
def prefix_sid_srv6(tokeniser):
    value = tokeniser()
    if value != "(":
        raise Exception("expect '(', but received '%s'" % value)

    service_type = tokeniser()
    if service_type not in ["l3-service", "l2-service"]:
        raise Exception("expect 'l3-service' or 'l2-service', but received '%s'" % value)

    sid = IPv6.unpack(IPv6.pton(tokeniser()))
    behavior = 0xFFFF
    subtlvs = []
    subsubtlvs = []
    value = tokeniser()
    if value != ")":
        base = 10 if not value.startswith("0x") else 16
        behavior = int(value, base)
        value = tokeniser()
        if value == "[":
            values = []
            for i in range(6):
                if i != 0:
                    value = tokeniser()
                    if value != ",":
                        raise Exception("expect ',', but received '%s'" % value)
                value = tokeniser()
                base = 10 if not value.startswith("0x") else 16
                values.append(int(value, base))

            value = tokeniser()
            if value != "]":
                raise Exception("expect ']', but received '%s'" % value)

            value = tokeniser()

            subsubtlvs.append(
                Srv6SidStructure(
                    loc_block_len=values[0],
                    loc_node_len=values[1],
                    func_len=values[2],
                    arg_len=values[3],
                    tpose_len=values[4],
                    tpose_offset=values[5],
                )
            )

    subtlvs.append(
        Srv6SidInformation(
            sid=sid,
            behavior=behavior,
            subsubtlvs=subsubtlvs,
        )
    )

    if value != ")":
        raise Exception("expect ')', but received '%s'" % value)

    if service_type == "l3-service":
        return PrefixSid([Srv6L3Service(subtlvs=subtlvs)])
    elif service_type == "l2-service":
        return PrefixSid([Srv6L2Service(subtlvs=subtlvs)])


def parse_ip_prefix(tokeninser):
    addrstr, length = tokeninser.split("/")
    if length is None:
        raise Exception("unexpect prefix format '%s'" % tokeninser)

    if not length.isdigit():
        raise Exception("unexpect prefix format '%s'" % tokeninser)

    addr = ip_address(addrstr)
    if isinstance(addr, IPv4Address):
        ip = IPv4.unpack(IPv4.pton(addrstr))
    elif isinstance(addr, IPv6Address):
        ip = IPv6.unpack(IPv6.pton(addrstr))
    else:
        raise Exception("unexpect ipaddress format '%s'" % addrstr)

    return ip, int(length)


# shared-join rp <ip> group <ip> rd <rd> source-as <source-as>
def mvpn_sharedjoin(tokeniser, afi, action):
    if afi == AFI.ipv4:
        tokeniser.consume("rp")
        sourceip = IPv4.unpack(IPv4.pton(tokeniser()))
        tokeniser.consume("group")
        groupip = IPv4.unpack(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        tokeniser.consume("rp")
        sourceip = IPv6.unpack(IPv6.pton(tokeniser()))
        tokeniser.consume("group")
        groupip = IPv6.unpack(IPv6.pton(tokeniser()))
    else:
        raise Exception("unexpect afi: %s" % afi)

    tokeniser.consume("rd")
    rd = route_distinguisher(tokeniser)

    tokeniser.consume("source-as")
    value = tokeniser()
    if not value.isdigit():
        raise Exception("expect source-as to be a integer in the range 0-4294967295, but received '%s'" % value)
    asnum = int(value)
    if asnum > 4294967295:
        raise Exception("expect source-as to be a integer in the range 0-4294967295, but received '%s'" % value)

    return SharedJoin(rd=rd, afi=afi, source=sourceip, group=groupip, source_as=asnum, action=action)


# source-join source <ip> group <ip> rd <rd> source-as <source-as>
def mvpn_sourcejoin(tokeniser, afi, action):
    if afi == AFI.ipv4:
        tokeniser.consume("source")
        sourceip = IPv4.unpack(IPv4.pton(tokeniser()))
        tokeniser.consume("group")
        groupip = IPv4.unpack(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        tokeniser.consume("source")
        sourceip = IPv6.unpack(IPv6.pton(tokeniser()))
        tokeniser.consume("group")
        groupip = IPv6.unpack(IPv6.pton(tokeniser()))
    else:
        raise Exception("unexpect afi: %s" % afi)

    tokeniser.consume("rd")
    rd = route_distinguisher(tokeniser)

    tokeniser.consume("source-as")
    value = tokeniser()
    if not value.isdigit():
        raise Exception("expect source-as to be a integer in the range 0-4294967295, but received '%s'" % value)
    asnum = int(value)
    if asnum > 4294967295:
        raise Exception("expect source-as to be a integer in the range 0-4294967295, but received '%s'" % value)

    return SourceJoin(rd=rd, afi=afi, source=sourceip, group=groupip, source_as=asnum, action=action)


#'source-ad source <ip address> group <ip address> rd <rd>'
def mvpn_sourcead(tokeniser, afi, action):
    if afi == AFI.ipv4:
        tokeniser.consume("source")
        sourceip = IPv4.unpack(IPv4.pton(tokeniser()))
        tokeniser.consume("group")
        groupip = IPv4.unpack(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        tokeniser.consume("source")
        sourceip = IPv6.unpack(IPv6.pton(tokeniser()))
        tokeniser.consume("group")
        groupip = IPv6.unpack(IPv6.pton(tokeniser()))
    else:
        raise Exception("unexpect afi: %s" % afi)

    tokeniser.consume("rd")
    rd = route_distinguisher(tokeniser)

    return SourceAD(rd=rd, afi=afi, source=sourceip, group=groupip, action=action)


# 'mup-isd <ip prefix> rd <rd>',
def srv6_mup_isd(tokeniser, afi):
    prefix_ip, prefix_len = parse_ip_prefix(tokeniser())

    value = tokeniser()
    if value != "rd":
        raise Exception("expect rd, but received '%s'" % value)
    rd = route_distinguisher(tokeniser)

    return InterworkSegmentDiscoveryRoute(
        rd=rd,
        prefix_ip_len=prefix_len,
        prefix_ip=prefix_ip,
        afi=afi,
    )


# 'mup-dsd <ip address> rd <rd>',
def srv6_mup_dsd(tokeniser, afi):
    if afi == AFI.ipv4:
        ip = IPv4.unpack(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        ip = IPv6.unpack(IPv6.pton(tokeniser()))
    else:
        raise Exception("unexpect afi: %s" % afi)

    value = tokeniser()
    if value != "rd":
        raise Exception("expect rd, but received '%s'" % value)
    rd = route_distinguisher(tokeniser)

    return DirectSegmentDiscoveryRoute(
        rd=rd,
        ip=ip,
        afi=afi,
    )


# 'mup-t1st <ip prefix> rd <rd> teid <teid> qfi <qfi> endpoint <endpoint> [source <source>]',
def srv6_mup_t1st(tokeniser, afi):
    prefix_ip, prefix_ip_len = parse_ip_prefix(tokeniser())

    tokeniser.consume("rd")
    rd = route_distinguisher(tokeniser)

    tokeniser.consume("teid")
    value = tokeniser()
    if not value.isdigit():
        raise Exception("expect teid to be a number, but received '%s'" % value)
    teid = int(value)

    tokeniser.consume("qfi")
    value = tokeniser()
    if not value.isdigit():
        raise Exception("expect qfi to be a number, but received '%s'" % value)
    qfi = int(value)

    tokeniser.consume("endpoint")
    if afi == AFI.ipv4:
        endpoint_ip = IPv4.unpack(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        endpoint_ip = IPv6.unpack(IPv6.pton(tokeniser()))
    else:
        raise Exception("unexpect afi: %s" % afi)

    source_ip_len = 0
    source_ip = b""

    if tokeniser.consume_if_match("source"):
        if afi == AFI.ipv4:
            source_ip = IPv4.unpack(IPv4.pton(tokeniser()))
            source_ip_len = 32
        elif afi == AFI.ipv6:
            source_ip = IPv6.unpack(IPv6.pton(tokeniser()))
            source_ip_len = 128
        else:
            raise Exception("unexpect afi: %s" % afi)

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
def srv6_mup_t2st(tokeniser, afi):
    if afi == AFI.ipv4:
        endpoint_ip = IPv4.unpack(IPv4.pton(tokeniser()))
    elif afi == AFI.ipv6:
        endpoint_ip = IPv6.unpack(IPv6.pton(tokeniser()))
    else:
        raise Exception("unexpect afi: %s" % afi)

    value = tokeniser()
    if "rd" != value:
        raise Exception("expect rd, but received '%s'" % value)

    rd = route_distinguisher(tokeniser)

    value = tokeniser()
    if value != "teid":
        raise Exception("expect teid, but received '%s'" % value)

    teids = tokeniser().split("/")
    if len(teids) != 2:
        raise Exception("unexpect teid format, this expect format <teid>/<length, expect 0 ~ 32")

    teid = int(teids[0])
    teid_len = int(teids[1])

    if not (0 <= teid_len <= 32):
        raise Exception("unexpect teid format, this expect format <teid>/<length, expect 0 ~ 32>")

    if teid >= pow(2, teid_len):
        raise Exception(f"unexpect teid format, we can not store {teid} using {teid_len} bits")

    return Type2SessionTransformedRoute(
        rd=rd,
        endpoint_len=endpoint_ip.bits + teid_len,  # 32 or 128
        endpoint_ip=endpoint_ip,
        teid=teid,
        afi=afi,
    )
