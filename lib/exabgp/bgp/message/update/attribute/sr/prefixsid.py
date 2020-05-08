# encoding: utf-8
"""
sr/prefixsid.py

Created by Evelio Vila 2017-02-16
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

import binascii
from struct import unpack
from exabgp.vendoring import six

from exabgp.util import concat_bytes_i
from exabgp.bgp.message.update.attribute.attribute import Attribute

# =====================================================================
# draft-ietf-idr-bgp-prefix-sid
# This Attribute may contain up to 3 TLVs
# Label-Index TLV ( type = 1 ) is mandatory for this attribute.


@Attribute.register()
class PrefixSid(Attribute):
    ID = Attribute.CODE.BGP_PREFIX_SID
    FLAG = FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    CACHING = True
    TLV = -1

    # Registered subclasses we know how to decode
    registered_srids = dict()

    def __init__(self, sr_attrs, packed=None):
        self.sr_attrs = sr_attrs
        self._packed = self._attribute(packed if packed else concat_bytes_i(_.pack() for _ in sr_attrs))

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
    def unpack(cls, data, negotiated):
        sr_attrs = []
        while data:
            # Type = 1 octet
            scode = six.indexbytes(data, 0)
            # L = 2 octet  :|
            length = unpack('!H', data[1:3])[0]
            if scode in cls.registered_srids:
                klass = cls.registered_srids[scode].unpack(data[3 : length + 3], length)
            else:
                klass = GenericSRId(scode, data[3 : length + 3])
            klass.TLV = scode
            sr_attrs.append(klass)
            data = data[length + 3 :]
        return cls(sr_attrs=sr_attrs)

    def json(self, compact=None):
        content = ', '.join(d.json() for d in self.sr_attrs)
        return '{ %s }' % (content)

    def __str__(self):
        label_index = next((i for i in self.sr_attrs if i.TLV == 1), None)
        srgb = next((i for i in self.sr_attrs if i.TLV == 3), None)
        if srgb:
            return "[ {}, {} ]".format(str(label_index), str(srgb))
        else:
            return "[ {} ]".format(str(label_index))

    def pack(self, negotiated=None):
        return self._packed


class GenericSRId(object):
    TLV = 99998

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
