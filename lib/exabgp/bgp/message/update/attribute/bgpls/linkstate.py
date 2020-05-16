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

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute


@Attribute.register()
class LinkState(Attribute):
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
    JSON = 'json-name-unset'
    REPR = 'repr name unset'
    LEN = None

    def __init__(self, flags):
        self.flags = flags

    @classmethod
    def unpack_flags(cls, data):
        pad = cls.FLAGS.count('RSV')
        repeat = len(cls.FLAGS) - pad
        hex_rep = int(binascii.b2a_hex(data), 16)
        bits = f'{hex_rep:08b}'
        valid_flags = [
            ''.join(item) + '0' * pad
            for item in itertools.product('01', repeat=repeat)
        ]
        valid_flags.append('0000')
        if bits in valid_flags:
            flags = dict(zip(cls.FLAGS, [0, ] * len(cls.FLAGS)))
            flags.update(dict((k, int(v)) for k, v in zip(cls.FLAGS, bits)))
        else:
            raise Notify(3, 5, "Invalid SR flags mask")
        return flags


    def json(self, compact=None):
        return '"{}": {}'.format(self.JSON, json.dumps(self.flags))

    def __repr__(self):
        return "%s: %s" % (self.REPR, self.flags)

    @classmethod
    def unpack(cls, data, length):
        if cls.LEN is not None and length != cls.LEN:
            raise Notify(3, 5, f'wrong size for {cls.REPR}')

        # We only support IS-IS for now.
        return cls(cls.unpack_flags(data[0:1]))
