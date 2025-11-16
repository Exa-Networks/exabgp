"""aspath.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from struct import error, unpack
from typing import TYPE_CHECKING, ClassVar, Dict, List, Optional, Tuple, Type, Union

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import AS_TRANS, ASN
from exabgp.bgp.message.update.attribute.attribute import Attribute

# =================================================================== ASPath (2)
# only 2-4% of duplicated data therefore it is not worth to cache


class SET(List[ASN]):
    ID: ClassVar[int] = 0x01
    NAME: ClassVar[str] = 'as-set'
    HEAD: ClassVar[str] = '['
    TAIL: ClassVar[str] = ']'


class SEQUENCE(List[ASN]):
    ID: ClassVar[int] = 0x02
    NAME: ClassVar[str] = 'as-sequence'
    HEAD: ClassVar[str] = '('
    TAIL: ClassVar[str] = ')'


class CONFED_SEQUENCE(List[ASN]):
    ID: ClassVar[int] = 0x03
    NAME: ClassVar[str] = 'as-sequence'
    HEAD: ClassVar[str] = '{('
    TAIL: ClassVar[str] = ')}'


class CONFED_SET(List[ASN]):
    ID: ClassVar[int] = 0x04
    NAME: ClassVar[str] = 'as-sequence'
    HEAD: ClassVar[str] = '{['
    TAIL: ClassVar[str] = ']}'

    # def __getslice__(self, i, j):
    #     return CONFED_SET(list.__getslice__(self, i, j))

    # def __add__(self, other):
    #     return CONFED_SET(list.__add__(self,other))


@Attribute.register()
class ASPath(Attribute):
    AS_SET: ClassVar[int] = SET.ID
    AS_SEQUENCE: ClassVar[int] = SEQUENCE.ID
    AS_CONFED_SEQUENCE: ClassVar[int] = CONFED_SEQUENCE.ID
    AS_CONFED_SET: ClassVar[int] = CONFED_SET.ID
    ASN4: ClassVar[bool] = False

    # AS_PATH segment constants (RFC 4271)
    SEGMENT_MAX_LENGTH: ClassVar[int] = 255  # Maximum number of ASNs in single segment

    ID = Attribute.CODE.AS_PATH
    FLAG = Attribute.Flag.TRANSITIVE

    Empty: ClassVar[Optional[ASPath]] = None

    _DISPATCH: ClassVar[Dict[int, Type[Union[SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET]]]] = {
        SET.ID: SET,
        SEQUENCE.ID: SEQUENCE,
        CONFED_SEQUENCE.ID: CONFED_SEQUENCE,
        CONFED_SET.ID: CONFED_SET,
    }

    def __init__(
        self, as_path: Tuple[Union[SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET], ...] = (), data: Optional[bytes] = None
    ) -> None:
        self.aspath: Tuple[Union[SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET], ...] = as_path
        self.segments: bytes = b''
        self.index: Optional[bytes] = data  # the original packed data, use for indexing
        self._str: str = ''
        self._json: str = ''

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ASPath):
            return False
        return (
            self.ID == other.ID and self.FLAG == other.FLAG and self.ASN4 == other.ASN4 and self.aspath == other.aspath
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    @classmethod
    def _segment(cls, seg_type: int, values: Union[SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET], asn4: bool) -> bytes:
        length = len(values)
        if length == 0:
            return b''
        if length > cls.SEGMENT_MAX_LENGTH:
            return (
                cls._segment(seg_type, values[: cls.SEGMENT_MAX_LENGTH], asn4)  # type: ignore[arg-type]
                + cls._segment(
                    seg_type,
                    values[cls.SEGMENT_MAX_LENGTH :],  # type: ignore[arg-type]
                    asn4,
                )
            )
        return bytes([seg_type, length]) + b''.join(v.pack_asn(asn4) for v in values)  # type: ignore[arg-type]

    @classmethod
    def pack_segments(cls, aspath: Tuple[Union[SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET], ...], asn4: bool) -> bytes:
        segments = b''
        for content in aspath:
            segments += cls._segment(content.ID, content, asn4)
        return cls._attribute(segments)

    @classmethod
    def _asn_pack(cls, aspath: Union[SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET], asn4: bool) -> bytes:
        return cls._attribute(cls._segment(cls.ID, aspath, asn4))

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        if negotiated.asn4:
            return self.pack_segments(self.aspath, negotiated.asn4)

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

        message = ASPath.pack_segments(astrans, negotiated.asn4)  # type: ignore[arg-type]
        if asn4:
            message += AS4Path.pack_segments(self.aspath, asn4)

        return message

    def __len__(self) -> int:
        raise RuntimeError('it makes no sense to ask for the size of this object')

    def __repr__(self) -> str:
        if not self._str:
            self._str = self.string()
        return self._str

    def string(self) -> str:
        parts = []
        for content in self.aspath:
            part = '{} {} {}'.format(content.HEAD, ' '.join(str(_) for _ in content), content.TAIL)
            parts.append(part)
        return ' '.join(parts)

    def json(self) -> str:
        jason = {}
        for pos, content in enumerate(self.aspath):
            jason[pos] = {
                'element': content.NAME,
                'value': list(content),
            }

        self._json = json.dumps(jason)
        return self._json

    @classmethod
    def _new_aspaths(
        cls, data: bytes, asn4: bool, klass: Optional[Type[Union[ASPath, AS4Path]]] = None
    ) -> Union[ASPath, AS4Path]:
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

        aspath: List[Union[SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET]] = []

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
            raise Notify(3, 11, 'not enough data to decode AS_PATH or AS4_PATH') from None
        except error:  # struct
            raise Notify(3, 11, 'not enough data to decode AS_PATH or AS4_PATH') from None

        if klass:
            return klass(tuple(aspath), backup)
        return cls(tuple(aspath), backup)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Optional[ASPath]:
        if not data:
            return None  # ASPath.Empty
        return cls._new_aspaths(data, negotiated.asn4, ASPath)


ASPath.Empty = ASPath([])  # type: ignore[arg-type]


# ================================================================= AS4Path (17)
#


@Attribute.register()
class AS4Path(ASPath):
    ID = Attribute.CODE.AS4_PATH
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    ASN4: ClassVar[bool] = True

    Empty: ClassVar[Optional[AS4Path]] = None

    def pack_attribute(self, negotiated: Optional[Negotiated] = None) -> bytes:
        return ASPath.pack_segments(self.aspath, True)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> Optional[AS4Path]:
        if not data:
            return None  # AS4Path.Empty
        return cls._new_aspaths(data, True, AS4Path)  # type: ignore[return-value]


AS4Path.Empty = AS4Path([], [])  # type: ignore[arg-type]
