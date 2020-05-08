# encoding: utf-8
"""
inet/parser.py

Created by Thomas Mangin on 2015-06-04.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import pack

from exabgp.util import character
from exabgp.util import concat_bytes_i

from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid
from exabgp.bgp.message.update.attribute.sr.labelindex import SrLabelIndex
from exabgp.bgp.message.update.attribute.sr.ipv6sid import SrV6Sid
from exabgp.bgp.message.update.attribute.sr.srv6vpnsid import Srv6VpnSid
from exabgp.bgp.message.update.attribute.sr.srv6l3vpnsid import Srv6L3vpnSid
from exabgp.bgp.message.update.attribute.sr.srgb import SrGb


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
        data = [character(0), character(1)]
        data.extend([character(int(_)) for _ in prefix.split('.')])
        data.extend([character(suffix >> 8), character(suffix & 0xFF)])
        rtd = concat_bytes_i(data)
    else:
        number = int(prefix)
        if number < pow(2, 16) and suffix < pow(2, 32):
            rtd = character(0) + character(0) + pack('!H', number) + pack('!L', suffix)
        elif number < pow(2, 32) and suffix < pow(2, 16):
            rtd = character(0) + character(2) + pack('!L', number) + pack('!H', suffix)
        else:
            raise ValueError('invalid route-distinguisher %s' % data)

    return RouteDistinguisher(rtd)


# [ 300, [ ( 800000,100 ), ( 1000000,5000 ) ] ]
def prefix_sid(tokeniser):
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


# { ipv6 <ipv6-addr> | vpn <ipv6-addr> | l3vpn <ipv6-addr> }
def prefix_sid_srv6(tokeniser):
    sr_attrs = []
    value = tokeniser()
    try:
        if value == '(':
            value = tokeniser()
            if value == 'ipv6':
                value = tokeniser()
                sr_attrs.append(SrV6Sid(value))
                value = tokeniser()
                if value == ')':
                    return PrefixSid(sr_attrs)

            if value == 'vpn':
                value = tokeniser()
                sr_attrs.append(Srv6VpnSid(value))
                value = tokeniser()
                if value == ')':
                    return PrefixSid(sr_attrs)

            if value == 'l3vpn':
                value = tokeniser()
                sr_attrs.append(Srv6L3vpnSid(value))
                value = tokeniser()
                if value == ')':
                    return PrefixSid(sr_attrs)

        raise Exception("format error")
    except Exception as e:
        raise ValueError('could not parse BGP PrefixSid Srv6 attribute: {}'.format(e))
