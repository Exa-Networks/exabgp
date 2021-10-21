# encoding: utf-8
"""
aspath.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import unpack
from struct import error

import json

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify


# =================================================================== ASPath (2)
# only 2-4% of duplicated data therefore it is not worth to cache

class SET(list):
    ID = 0x01
    NAME = "as-set"
    HEAD = "["
    TAIL = "]"


class SEQUENCE(list):
    ID = 0x02
    NAME = "as-sequence"
    HEAD = "("
    TAIL = ")"


class CONFED_SEQUENCE(list):
    ID = 0x03
    NAME = "as-sequence"
    HEAD = "{("
    TAIL = ")}"


class CONFED_SET(list):
    ID = 0x04
    NAME = "as-sequence"
    HEAD = "{["
    TAIL = "]}"

    # def __getslice__(self, i, j):
    #     return CONFED_SET(list.__getslice__(self, i, j))

    # def __add__(self, other):
    #     return CONFED_SET(list.__add__(self,other))


@Attribute.register()
class ASPath(Attribute):
    AS_SET = SET.ID
    AS_SEQUENCE = SEQUENCE.ID
    AS_CONFED_SEQUENCE = CONFED_SEQUENCE.ID
    AS_CONFED_SET = CONFED_SET.ID
    ASN4 = False

    ID = Attribute.CODE.AS_PATH
    FLAG = Attribute.Flag.TRANSITIVE

    _DISPATCH = {
        SET.ID: SET,
        SEQUENCE.ID: SEQUENCE,
        CONFED_SEQUENCE.ID: CONFED_SEQUENCE,
        CONFED_SET.ID: CONFED_SET,
    }

    def __init__(self, as_path=[], data=None):
        self.aspath = as_path
        self.segments = b''
        self.index = data  # the original packed data, use for indexing
        self._str = ''
        self._json = ''

    def __eq__(self, other):
        return (
            self.ID == other.ID
            and self.FLAG == other.FLAG
            and self.ASN4 == other.ASN4
            and self.aspath == other.aspath
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    @classmethod
    def _segment(cls, seg_type, values, asn4):
        length = len(values)
        if length:
            if length > 255:
                return cls._segment(seg_type, values[:255], asn4) + cls._segment(seg_type, values[255:], asn4)
            return bytes([seg_type, len(values)]) + b''.join(v.pack(asn4) for v in values)
        return b""

    @classmethod
    def _segments(cls, aspath, asn4):
        segments = b''
        for content in aspath:
            segments += cls._segment(content.ID, content, asn4)
        return segments

    @classmethod
    def _asn_pack(self, aspath, asn4):
        return self._attribute(self._segments(aspath, asn4))

    def pack(self, negotiated):
        if negotiated.asn4:
            return self._asn_pack(self.aspath, negotiated.asn4)

        # if the peer does not understand ASN4, we need to build a transitive AS4_PATH
        astrans = []
        asn4 = False

        for content in self.aspath:
            local = content.__class__()
            for asn in content:
                if not asn.asn4():
                    local.append(asn)
                else:
                    local.append(AS_TRANS)
                    asn4 = True
            astrans.append(local)

        message = ASPath._asn_pack(astrans, negotiated.asn4)
        if asn4:
            message += AS4Path._asn_pack(self.aspath, asn4)

        return message

    def __len__(self):
        raise RuntimeError('it makes no sense to ask for the size of this object')

    def __repr__(self):
        if not self._str:
            self._str = self.string()
        return self._str

    def string(self):
        parts = []
        for content in self.aspath:
            part = "%s %s %s" % (content.HEAD, " ".join((str(_) for _ in content)), content.TAIL) 
            parts.append(part)
        return " ".join(parts)

    def json(self):
        jason = {}
        for pos, content in enumerate(self.aspath):
            jason[pos] = {
                'element': content.NAME,
                'value': list(content),
            }

        self._json = json.dumps(jason)
        return self._json

    @classmethod
    def _new_aspaths(cls, data, asn4, klass=None):
        backup = data

        unpacker = {
            False: '!H',
            True: '!L',
        }
        size = {
            False: 2,
            True: 4,
        }

        upr = unpacker[asn4]
        length = size[asn4]

        aspath = []

        try:
            while data:
                stype = data[0]
                slen = data[1]

                if stype not in cls._DISPATCH:
                    raise Notify(3, 11, 'invalid AS Path type sent %d' % stype)

                end = 2 + (slen * length)
                sdata = data[2:end]
                data = data[end:]
                # Eat the data and ignore it if the ASPath attribute is know known
                asns = cls._DISPATCH[stype]()

                for _ in range(slen):
                    asn = unpack(upr, sdata[:length])[0]
                    asns.append(ASN(asn))
                    sdata = sdata[length:]

                aspath.append(asns)

        except IndexError:
            raise Notify(3, 11, 'not enough data to decode AS_PATH or AS4_PATH')
        except error:  # struct
            raise Notify(3, 11, 'not enough data to decode AS_PATH or AS4_PATH')

        if klass:
            return klass(aspath, backup)
        return cls(aspath, backup)

    @classmethod
    def unpack(cls, data, direction, negotiated):
        if not data:
            return None  # ASPath.Empty
        return cls._new_aspaths(data, negotiated.asn4, ASPath)


ASPath.Empty = ASPath([])


# ================================================================= AS4Path (17)
#


@Attribute.register()
class AS4Path(ASPath):
    ID = Attribute.CODE.AS4_PATH
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    ASN4 = True

    def pack(self, negotiated=None):
        ASPath.pack(self, True)

    @classmethod
    def unpack(cls, data, direction, negotiated):
        if not data:
            return None  # AS4Path.Empty
        return cls._new_aspaths(data, True, AS4Path)


AS4Path.Empty = AS4Path([], [])
