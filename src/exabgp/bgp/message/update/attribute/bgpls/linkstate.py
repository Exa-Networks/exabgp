
"""Copyright (c) 2016 Evelio Vila <eveliovila@gmail.com>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
import binascii
import itertools
from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.util import hexstring


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
        def register_class(klass):
            if klass.TLV in cls.registered_lsids:
                raise RuntimeError('only one class can be registered per BGP link state attribute type')
            cls.registered_lsids[klass.TLV] = klass
            return klass

        def register_lsid(klass):
            if not lsid:
                return register_class(klass)

            kls = type('%s_%d' % (klass.__name__, lsid), klass.__bases__, dict(klass.__dict__))
            kls.TLV = lsid
            return register_class(kls)

        return register_lsid

    @classmethod
    def klass(cls, code):
        klass = cls.registered_lsids.get(code, None)
        if klass is not None:
            return klass
        unknown = type('GenericLSID_%d' % code, GenericLSID.__bases__, dict(GenericLSID.__dict__))
        unknown.TLV = code
        cls.registered_lsids[code] = unknown
        return unknown

    @classmethod
    def registered(cls, lsid, flag=None):
        return lsid in cls.registered_lsids

    @classmethod
    def unpack(cls, data, direction, negotiated):
        ls_attrs = []
        while data:
            scode, length = unpack('!HH', data[:4])
            payload = data[4 : length + 4]
            BaseLS.check_length(payload, length)

            data = data[length + 4 :]
            klass = cls.klass(scode)
            instance = klass.unpack(payload)

            if not instance.MERGE:
                ls_attrs.append(instance)
                continue

            for k in ls_attrs:
                if k.TLV == instance.TLV:
                    k.merge(instance)
                    break
            else:
                ls_attrs.append(instance)

        return cls(ls_attrs=ls_attrs)

    def json(self, compact=None):
        content = ', '.join(d.json() for d in self.ls_attrs)
        return f'{{ {content} }}'

    def __str__(self):
        return ', '.join(str(d) for d in self.ls_attrs)


class BaseLS:
    TLV = -1
    JSON = 'json-name-unset'
    REPR = 'repr name unset'
    LEN = 0
    MERGE = False

    def __init__(self, content):
        self.content = content

    def json(self, compact=None):
        try:
            return f'"{self.JSON}": {json.dumps(self.content)}'
        except TypeError:
            # not a basic type
            return f'"{self.JSON}": "{self.content.decode("utf-8")}"'

    def __repr__(self):
        return '{}: {}'.format(self.REPR, self.content)

    @classmethod
    def check_length(cls, data, length):
        if length and len(data) != length:
            raise Notify(3, 5, f'Unable to decode attribute, wrong size for {cls.REPR}')

    @classmethod
    def check(cls, data):
        return cls.check_length(data, cls.LEN)

    def merge(self, other):
        if not self.MERGE:
            raise Notify(3, 5, f'Invalid merge, issue decoding {self.REPR}')
        self.content.extend(other.content)


class GenericLSID(BaseLS):
    TLV = 0
    MERGE = True

    def __init__(self, content):
        BaseLS.__init__(
            self,
            [
                content,
            ],
        )

    def __repr__(self):
        return 'Attribute with code [ {} ] not implemented'.format(self.TLV)

    def json(self):
        merged = ', '.join([f'"{hexstring(_)}"' for _ in self.content])
        return f'"generic-lsid-{self.TLV}": [{merged}]'

    @classmethod
    def unpack(cls, data):
        return cls(data)


class FlagLS(BaseLS):
    def __init__(self, flags):
        self.flags = flags

    def __repr__(self):
        return '{}: {}'.format(self.REPR, self.flags)

    def json(self, compact=None):
        return f'"{self.JSON}": {json.dumps(self.flags)}'

    @classmethod
    def unpack_flags(cls, data):
        pad = cls.FLAGS.count('RSV')
        repeat = len(cls.FLAGS) - pad
        hex_rep = int(binascii.b2a_hex(data), 16)
        bits = f'{hex_rep:08b}'
        valid_flags = [''.join(item) + '0' * pad for item in itertools.product('01', repeat=repeat)]
        valid_flags.append('0000')
        if bits in valid_flags:
            flags = dict(
                zip(
                    cls.FLAGS,
                    [
                        0,
                    ]
                    * len(cls.FLAGS),
                ),
            )
            flags.update(dict((k, int(v)) for k, v in zip(cls.FLAGS, bits)))
        else:
            raise Notify(3, 5, 'Invalid SR flags mask')
        return flags

    @classmethod
    def unpack(cls, data):
        cls.check(data)
        # We only support IS-IS for now.
        return cls(cls.unpack_flags(data[0:1]))
