# encoding: utf-8
"""
Copyright (c) 2016 Evelio Vila <eveliovila@gmail.com>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import json
import binascii
import itertools
from struct import unpack

from exabgp.util import concat_strs
from exabgp.vendoring.bitstring import BitArray
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute


@Attribute.register()
class LINKSTATE(Attribute):
    ID = Attribute.CODE.BGP_LS
    FLAG = Attribute.Flag.OPTIONAL
    TLV = -1

    # Registered subclasses we know how to decode
    registered_lsids = dict()

    # what this implementation knows as LS attributes
    node_lsids = []
    link_lsids = []
    prefix_lsids = []

    def __init__(self, ls_attrs):
        self.ls_attrs = ls_attrs

    @classmethod
    def register(cls, lsid=None, flag=None):
        def register_lsid(klass):
            scode = klass.TLV if lsid is None else lsid
            if scode in cls.registered_lsids:
                raise RuntimeError('only one class can be registered per BGP link state attribute type')
            cls.registered_lsids[scode] = klass
            return klass

        return register_lsid

    @classmethod
    def registered(cls, lsid, flag=None):
        return lsid in cls.registered_lsids

    @classmethod
    def unpack(cls, data, negotiated):
        ls_attrs = []
        while data:
            scode, length = unpack('!HH', data[:4])
            if scode in cls.registered_lsids:
                klass = cls.registered_lsids[scode].unpack(data[4 : length + 4], length)
            else:
                klass = GenericLSID(scode, data[4 : length + 4])
            klass.TLV = scode
            ls_attrs.append(klass)
            data = data[length + 4 :]
        for klass in ls_attrs:
            if hasattr(klass, 'terids'):
                klass.reset()

        return cls(ls_attrs=ls_attrs)

    def json(self, compact=None):
        content = ', '.join(d.json() for d in self.ls_attrs)
        return '{ %s }' % (content)

    def __str__(self):
        return ', '.join(str(d) for d in self.ls_attrs)


class GenericLSID(object):
    TLV = 99999

    def __init__(self, code, rep):
        self.rep = rep
        self.code = code

    def __repr__(self):
        return "Attribute with code [ %s ] not implemented" % (self.code)

    @classmethod
    def unpack(cls, scode, data):
        length = len(data)
        info = binascii.b2a_uu(data[:length])
        return cls(code=scode, rep=info)

    def json(self, compact=None):
        return '"attribute-not-implemented": "%s"' % (self.code)


class LsGenericFlags(object):

    # 	draft-ietf-isis-segment-routing-extensions Prefix-SID Sub-TLV
    ISIS_SR_FLAGS = ['R', 'N', 'P', 'E', 'V', 'L', 'RSV', 'RSV']
    # 	RFC 7794 IPv4/IPv6 Extended Reachability Attribute Flags
    ISIS_SR_ATTR_FLAGS = ['X', 'R', 'N', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    # 	draft-ietf-isis-segment-routing-extensions - Adj-SID IS-IS Flags
    ISIS_SR_ADJ_FLAGS = ['F', 'B', 'V', 'L', 'S', 'P', 'RSV', 'RSV']
    # 	isis-segment-routing-extensions 3.1. SR-Capabilities Sub-TLV
    ISIS_SR_CAP_FLAGS = ['I', 'V', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    # 	RFC 7752 3.3.1.1. Node Flag Bits TLV
    LS_NODE_FLAGS = ['O', 'T', 'E', 'B', 'R', 'V', 'RSV', 'RSV']
    # 	RFC 7752 3.3.3.1. IGP Flags TLV
    LS_IGP_FLAGS = ['D', 'N', 'L', 'P', 'RSV', 'RSV', 'RSV', 'RSV']
    # 	RFC 7752 3.3.2.2.  MPLS Protocol Mask TLV
    LS_MPLS_MASK = ['LDP', 'RSVP-TE', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV', 'RSV']
    # 	RFC 5307 1.2.
    LS_PROTECTION_MASK = [
        'ExtraTrafic',
        'Unprotected',
        'Shared',
        'Dedicated 1:1',
        'Dedicated 1+1',
        'Enhanced',
        'RSV',
        'RSV',
    ]

    def __init__(self, flags):
        self.flags = flags

    @classmethod
    def unpack(cls, data, pattern):
        pad = pattern.count('RSV')
        repeat = len(pattern) - pad
        flag_array = binascii.b2a_hex(data)
        hex_rep = hex(int(flag_array, 16))
        bit_array = BitArray(hex_rep)
        valid_flags = [
            concat_strs(''.join(item), ''.join(itertools.repeat('0', pad)))
            for item in itertools.product('01', repeat=repeat)
        ]
        valid_flags.append('0000')
        if bit_array.bin in valid_flags:
            flags = dict(zip(pattern, [0,] * len(pattern)))
            flags.update(dict((k, int(v)) for k, v in zip(pattern, bit_array.bin)))
        else:
            raise Notify(3, 5, "Invalid SR flags mask")
        return cls(flags=flags)

    def json(self, compact=None):
        return json.dumps(self.flags)

    def __repr__(self):
        return str(self.flags)
