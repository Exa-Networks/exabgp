"""sr/prefixsid.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack
from struct import unpack

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.attribute import Attribute

from exabgp.util import hexstring

# =====================================================================
# draft-ietf-idr-bgp-prefix-sid
# This Attribute may contain up to 3 TLVs
# Label-Index TLV ( type = 1 ) is mandatory for this attribute.

# SR TLV type codes
SR_TLV_SRGB = 3  # Segment Routing Global Block TLV type


@Attribute.register()
class PrefixSid(Attribute):
    ID = Attribute.CODE.BGP_PREFIX_SID
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    CACHING = True
    TLV = -1

    TLV_HEADER_SIZE = 3  # Type(1) + Length(2)

    # Registered subclasses we know how to decode
    registered_srids = dict()

    def __init__(self, sr_attrs, packed=None):
        self.sr_attrs = sr_attrs
        self._packed = self._attribute(packed if packed else b''.join(_.pack() for _ in sr_attrs))

    @classmethod
    def register(cls, srid=None, flag=None):
        def register_srid(klass):
            scode = klass.TLV if srid is None else srid
            if scode in cls.registered_srids:
                raise RuntimeError('only one class can be registered per Segment Routing TLV type')
            cls.registered_srids[scode] = klass
            return klass

        return register_srid

    @classmethod
    def unpack(cls, data, direction, negotiated):
        # keep what the peer sent: rebuilding the attribute from the parsed TLVs
        # re-encodes something it never sent, and an unregistered TLV cannot be
        # re-encoded at all
        packed = bytes(data)
        sr_attrs = []
        while data:
            if len(data) < cls.TLV_HEADER_SIZE:
                raise Notify(3, 5, 'invalid BGP prefix SID attribute, truncated TLV header')
            # Type = 1 octet
            scode = data[0]
            # L = 2 octet  :|
            length = unpack('!H', data[1:3])[0]
            if len(data) < length + cls.TLV_HEADER_SIZE:
                raise Notify(3, 5, 'invalid BGP prefix SID attribute, TLV announces more than it carries')
            if scode in cls.registered_srids:
                klass = cls.registered_srids[scode].unpack(data[3 : length + 3], length)
            else:
                klass = GenericSRId(scode, data[3 : length + 3])
            klass.TLV = scode
            sr_attrs.append(klass)
            data = data[length + 3 :]
        return cls(sr_attrs=sr_attrs, packed=packed)

    def json(self, compact=None):
        content = ', '.join(d.json() for d in self.sr_attrs)
        return f'{{ {content} }}'

    def as_dict(self):
        result = {}
        for d in self.sr_attrs:
            result.update(d.as_dict())
        return result

    def __str__(self):
        # First, we try to decode path attribute for SR-MPLS
        label_index = next((i for i in self.sr_attrs if i.TLV == 1), None)
        if label_index is not None:
            srgb = next((i for i in self.sr_attrs if i.TLV == SR_TLV_SRGB), None)
            if srgb is not None:
                return f'[ {label_index!s}, {srgb!s} ]'
            return f'[ {label_index!s} ]'

        # if not, we try to decode path attribute for SRv6
        return '[ ' + ', '.join([str(attr) for attr in self.sr_attrs]) + ' ]'

    def pack(self, negotiated=None):
        return self._packed


class GenericSRId:
    TLV = 99998

    def __init__(self, code, rep):
        self.rep = rep
        self.code = code

    def __repr__(self):
        return 'Attribute with code [ {} ] not implemented'.format(self.code)

    @classmethod
    def unpack(cls, scode, data):
        return cls(code=scode, rep=data)

    def pack(self):
        # re-emit exactly the bytes which arrived, header included
        return bytes([self.code]) + pack('!H', len(self.rep)) + bytes(self.rep)

    def json(self, compact=None):
        return '"attribute-not-implemented-{}": "{}"'.format(self.code, hexstring(self.rep))

    def as_dict(self):
        return {f'attribute-not-implemented-{self.code}': hexstring(self.rep)}
