"""Copyright (c) 2016 Evelio Vila <eveliovila@gmail.com>
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import binascii
import itertools
import json
from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.util import hexstring


@Attribute.register()
class LinkState(Attribute):
    ID = Attribute.CODE.BGP_LS
    FLAG = Attribute.Flag.OPTIONAL
    TLV = -1

    TLV_HEADER_SIZE = 4  # Type(2) + Length(2)

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
    def _decode_tlv(cls, klass, scode, payload):
        """Decode one TLV and prove the result can be rendered

        A decoder which returns, but whose object raises from json() or repr(),
        moves the failure into the API writer, where nothing treats it as a
        protocol error and the line is already half written.  Rendering once
        here costs less than a dead session later.
        """
        try:
            instance = klass.unpack(payload)
            instance.json()
            repr(instance)
            return instance
        except Notify:
            raise
        except Exception as exc:
            raise Notify(3, 5, f'Invalid BGP-LS attribute TLV {scode} ({type(exc).__name__})') from None

    @classmethod
    def unpack(cls, data, direction, negotiated):
        ls_attrs = []
        while data:
            if len(data) < cls.TLV_HEADER_SIZE:
                raise Notify(3, 5, 'Invalid BGP-LS attribute, truncated TLV header')
            scode, length = unpack('!HH', data[: cls.TLV_HEADER_SIZE])
            payload = data[cls.TLV_HEADER_SIZE : length + cls.TLV_HEADER_SIZE]
            BaseLS.check_length(payload, length)

            data = data[length + cls.TLV_HEADER_SIZE :]
            klass = cls.klass(scode)
            instance = cls._decode_tlv(klass, scode, payload)

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

    def as_dict(self):
        result = {}
        for d in self.ls_attrs:
            result.update(d.as_dict())
        return result

    def __str__(self):
        return ', '.join(str(d) for d in self.ls_attrs)


def jsonable(value):
    """Make a decoded TLV value safe to hand to json.dumps

    The content comes from the wire and is not trusted, so decoding it must
    never raise at emission time, and it must never be inlined into the JSON
    by hand as that would let a peer inject its own keys into the API stream.
    """
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).decode('utf-8', 'replace')
    if isinstance(value, (list, tuple)):
        return [jsonable(_) for _ in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


class BaseLS:
    TLV = -1
    JSON = 'json-name-unset'
    REPR = 'repr name unset'
    LEN = 0
    MERGE = False

    BGPLS_SUBTLV_HEADER_SIZE = 4  # Sub-TLV header is 4 bytes (Type 2 + Length 2)

    def __init__(self, content):
        self.content = content

    def json(self, compact=None):
        return f'"{self.JSON}": {json.dumps(jsonable(self.content))}'

    def as_dict(self):
        return {self.JSON: jsonable(self.content)}

    def __repr__(self):
        return '{}: {}'.format(self.REPR, self.content)

    @classmethod
    def check_length(cls, data, length):
        if length and len(data) != length:
            raise Notify(3, 5, f'Unable to decode attribute, wrong size for {cls.REPR}')

    @classmethod
    def check(cls, data):
        return cls.check_length(data, cls.LEN)

    @classmethod
    def check_multiple(cls, data, size):
        # LEN is 0 for the repeated value TLVs, which makes check() a no-op for them.
        # An EMPTY TLV is not refused: none is a whole number of elements, this
        # release renders it as an empty list, and refusing it drops a route on
        # upgrade for something no decoder has trouble with.
        if len(data) % size:
            raise Notify(3, 5, f'Unable to decode attribute, wrong size for {cls.REPR}')

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

    def as_dict(self):
        return {f'generic-lsid-{self.TLV}': [hexstring(c) for c in self.content]}

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

    def as_dict(self):
        return {self.JSON: self.flags}

    @classmethod
    def unpack_flags(cls, data):
        # b2a_hex of an empty buffer gives int() nothing to parse
        if not data:
            raise Notify(3, 5, f'Unable to decode attribute, no flags for {cls.REPR}')
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
