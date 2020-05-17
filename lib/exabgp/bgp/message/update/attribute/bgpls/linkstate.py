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
            if not hasattr(klass, 'MERGE'):
                klass.MERGE = False
            scode = klass.TLV if lsid is None else lsid
            if scode in cls.registered_lsids:
                raise RuntimeError('only one class can be registered per BGP link state attribute type')
            cls.registered_lsids[scode] = klass
            return klass

        return register_lsid

    @classmethod
    def klass(cls, code):
        return cls.registered_lsids.get(code, GenericLSID)

    @classmethod
    def registered(cls, lsid, flag=None):
        return lsid in cls.registered_lsids

    @classmethod
    def unpack(cls, data, negotiated):
        ls_attrs = []
        while data:
            scode, length = unpack('!HH', data[:4])
            klass = cls.klass(scode).unpack(data[4 : length + 4], length)
            klass.TLV = scode
            data = data[length + 4 :]
            if klass.MERGE:
                for k in ls_attrs:
                    if k.TLV == klass.TLV:
                        k.merge(k)
                        continue
            ls_attrs.append(klass)

        return cls(ls_attrs=ls_attrs)

    def json(self, compact=None):
        content = ', '.join(d.json() for d in self.ls_attrs)
        return '{ %s }' % (content)

    def __str__(self):
        return ', '.join(str(d) for d in self.ls_attrs)


class BaseLS(object):
    TLV = -1
    TLV = -1
    JSON = 'json-name-unset'
    REPR = 'repr name unset'
    LEN = None

    def __init__(self, content):
        self.content = content

    def json(self, compact=None):
        return '"{}": {}'.format(self.JSON, json.dumps(self.content))

    def __repr__(self):
        return "%s: %s" % (self.REPR, self.content)

    @classmethod
    def check(cls, length):
        if cls.LEN is not None and length != cls.LEN:
            raise Notify(3, 5, f'Unable to decode attribute, wrong size for {cls.REPR}')


class GenericLSID(BaseLS):
    def __init__(self, code, content):
        BaseLS.__init__(self, content)
        self.code = code

    def __repr__(self):
        return "Attribute with code [ %s ] not implemented" % (self.code)

    def json(self):
        return '"generic-LSID-{}": {}'.format(self.code, json.dumps(self.content))

    @classmethod
    def unpack(cls, scode, data):
        return cls(scode, binascii.b2a_uu(data[:]))


class FlagLS(BaseLS):
    def __init__(self, flags):
        self.flags = flags

    def __repr__(self):
        return "%s: %s" % (self.REPR, self.flags)

    def json(self, compact=None):
        return '"{}": {}'.format(self.JSON, json.dumps(self.flags))

    @classmethod
    def unpack_flags(cls, data):
        pad = cls.FLAGS.count('RSV')
        repeat = len(cls.FLAGS) - pad
        hex_rep = int(binascii.b2a_hex(data), 16)
        bits = f'{hex_rep:08b}'
        valid_flags = [''.join(item) + '0' * pad for item in itertools.product('01', repeat=repeat)]
        valid_flags.append('0000')
        if bits in valid_flags:
            flags = dict(zip(cls.FLAGS, [0,] * len(cls.FLAGS)))
            flags.update(dict((k, int(v)) for k, v in zip(cls.FLAGS, bits)))
        else:
            raise Notify(3, 5, "Invalid SR flags mask")
        return flags

    @classmethod
    def unpack(cls, data, length):
        cls.check(length)
        # We only support IS-IS for now.
        return cls(cls.unpack_flags(data[0:1]))
