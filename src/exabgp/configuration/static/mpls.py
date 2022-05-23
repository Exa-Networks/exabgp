# encoding: utf-8
"""
inet/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack

from exabgp.protocol.ip import IPv6

from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.labelindex import SrLabelIndex
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb
from exabgp.bgp.message.update.attribute.sr.srv6.l3service import Srv6L3Service
from exabgp.bgp.message.update.attribute.sr.srv6.l2service import Srv6L2Service
from exabgp.bgp.message.update.attribute.sr.srv6.sidinformation import Srv6SidInformation
from exabgp.bgp.message.update.attribute.sr.srv6.sidstructure import Srv6SidStructure


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
