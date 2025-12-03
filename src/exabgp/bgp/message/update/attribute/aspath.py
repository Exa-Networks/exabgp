"""aspath.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import json
from struct import error, unpack
from typing import TYPE_CHECKING, ClassVar, Sequence, Type, TypeVar

if TYPE_CHECKING:
    from exabgp.bgp.message.open.capability.negotiated import Negotiated

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.open.asn import AS_TRANS, ASN
from exabgp.bgp.message.update.attribute.attribute import Attribute

# =================================================================== ASPath (2)
# only 2-4% of duplicated data therefore it is not worth to cache


class SET(list[ASN]):
    ID: ClassVar[int] = 0x01
    NAME: ClassVar[str] = 'as-set'
    HEAD: ClassVar[str] = '['
    TAIL: ClassVar[str] = ']'


class SEQUENCE(list[ASN]):
    ID: ClassVar[int] = 0x02
    NAME: ClassVar[str] = 'as-sequence'
    HEAD: ClassVar[str] = '('
    TAIL: ClassVar[str] = ')'


class CONFED_SEQUENCE(list[ASN]):
    ID: ClassVar[int] = 0x03
    NAME: ClassVar[str] = 'as-sequence'
    HEAD: ClassVar[str] = '{('
    TAIL: ClassVar[str] = ')}'


class CONFED_SET(list[ASN]):
    ID: ClassVar[int] = 0x04
    NAME: ClassVar[str] = 'as-sequence'
    HEAD: ClassVar[str] = '{['
    TAIL: ClassVar[str] = ']}'


# TypeVar for segment types - allows slicing to preserve type
SegmentType = TypeVar('SegmentType', SET, SEQUENCE, CONFED_SEQUENCE, CONFED_SET)


@Attribute.register()
class ASPath(Attribute):
    """AS Path attribute (code 2).

    Stores packed wire-format bytes. The wire format can be either 2-byte or 4-byte
    ASNs depending on the negotiated capability. The _asn4 flag tracks which format
    is stored.
    """

    ID = Attribute.CODE.AS_PATH
    FLAG = Attribute.Flag.TRANSITIVE

    AS_SET: ClassVar[int] = SET.ID
    AS_SEQUENCE: ClassVar[int] = SEQUENCE.ID
    AS_CONFED_SEQUENCE: ClassVar[int] = CONFED_SEQUENCE.ID
    AS_CONFED_SET: ClassVar[int] = CONFED_SET.ID

    # AS_PATH segment constants (RFC 4271)
    SEGMENT_MAX_LENGTH: ClassVar[int] = 255  # Maximum number of ASNs in single segment

    TREAT_AS_WITHDRAW: ClassVar[bool] = True
    MANDATORY: ClassVar[bool] = True
    VALID_ZERO: ClassVar[bool] = True

    Empty: ClassVar[ASPath | None] = None

    _DISPATCH: ClassVar[dict[int, Type[SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET]]] = {
        SET.ID: SET,
        SEQUENCE.ID: SEQUENCE,
        CONFED_SEQUENCE.ID: CONFED_SEQUENCE,
        CONFED_SET.ID: CONFED_SET,
    }

    def __init__(self, packed: bytes, asn4: bool = False) -> None:
        """Initialize from packed wire-format bytes.

        NO validation - trusted internal use only.
        Use from_packet() for wire data or make_aspath() for semantic construction.

        Args:
            packed: Raw attribute value bytes
            asn4: True if packed uses 4-byte ASNs, False for 2-byte
        """
        self._packed: bytes = packed
        self._asn4: bool = asn4

    @classmethod
    def from_packet(cls, data: bytes, asn4: bool) -> 'ASPath':
        """Validate and create from wire-format bytes.

        Args:
            data: Raw attribute value bytes from wire
            asn4: True if data uses 4-byte ASNs, False for 2-byte

        Returns:
            ASPath instance

        Raises:
            Notify: If data format is invalid
        """
        # Validate by attempting to parse - will raise Notify on error
        cls._unpack_segments_static(data, asn4)
        return cls(data, asn4)

    @classmethod
    def make_aspath(
        cls, segments: Sequence[SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET], asn4: bool = False
    ) -> 'ASPath':
        """Create from parsed segments.

        Args:
            segments: Sequence of AS path segments (SET, SEQUENCE, etc.)
            asn4: True to pack with 4-byte ASNs, False for 2-byte

        Returns:
            ASPath instance
        """
        packed = cls._pack_segments_raw(tuple(segments), asn4)
        return cls(packed, asn4)

    @property
    def aspath(self) -> tuple[SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET, ...]:
        """Get parsed AS path segments by unpacking from bytes."""
        return self._unpack_segments_static(self._packed, self._asn4)

    @property
    def index(self) -> bytes:
        """Get the original packed data, used for indexing/caching."""
        return self._packed

    @property
    def as_seq(self) -> list[ASN]:
        """Get ASNs from SEQUENCE segments (flattened)."""
        result: list[ASN] = []
        for seg in self.aspath:
            if isinstance(seg, (SEQUENCE, CONFED_SEQUENCE)):
                result.extend(seg)
        return result

    @property
    def as_set(self) -> list[ASN]:
        """Get ASNs from SET segments (flattened)."""
        result: list[ASN] = []
        for seg in self.aspath:
            if isinstance(seg, (SET, CONFED_SET)):
                result.extend(seg)
        return result

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ASPath):
            return False
        return (
            self.ID == other.ID
            and self.FLAG == other.FLAG
            and self._asn4 == other._asn4
            and self._packed == other._packed
        )

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __len__(self) -> int:
        return len(self._packed)

    def __repr__(self) -> str:
        return self.string()

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
        return json.dumps(jason)

    @classmethod
    def _unpack_segments_static(
        cls, data: bytes, asn4: bool
    ) -> tuple[SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET, ...]:
        """Unpack segments from wire format."""
        unpacker = '!L' if asn4 else '!H'
        length = 4 if asn4 else 2
        aspath: list[SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET] = []

        try:
            while data:
                stype = data[0]
                slen = data[1]

                if stype not in cls._DISPATCH:
                    raise Notify(3, 11, 'invalid AS Path type sent %d' % stype)

                end = 2 + (slen * length)
                sdata = data[2:end]
                data = data[end:]
                asns = cls._DISPATCH[stype]()

                for _ in range(slen):
                    asn = unpack(unpacker, sdata[:length])[0]
                    asns.append(ASN(asn))
                    sdata = sdata[length:]

                aspath.append(asns)

        except IndexError:
            raise Notify(3, 11, 'not enough data to decode AS_PATH or AS4_PATH') from None
        except error:  # struct
            raise Notify(3, 11, 'not enough data to decode AS_PATH or AS4_PATH') from None

        return tuple(aspath)

    @classmethod
    def _pack_segments_raw(
        cls, segments: tuple[SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET, ...], asn4: bool
    ) -> bytes:
        """Pack segments to wire format (without attribute header)."""
        result = b''
        for content in segments:
            result += cls._segment(content.ID, content, asn4)
        return result

    @classmethod
    def _segment(cls, seg_type: int, values: SegmentType, asn4: bool) -> bytes:
        length = len(values)
        if length == 0:
            return b''
        if length > cls.SEGMENT_MAX_LENGTH:
            first_half = type(values)(values[: cls.SEGMENT_MAX_LENGTH])
            second_half = type(values)(values[cls.SEGMENT_MAX_LENGTH :])
            return cls._segment(seg_type, first_half, asn4) + cls._segment(seg_type, second_half, asn4)
        return bytes([seg_type, length]) + b''.join(v.pack_asn(asn4) for v in values)  # type: ignore[arg-type]

    def pack_attribute(self, negotiated: Negotiated) -> bytes:
        """Pack for sending to peer.

        Handles format conversion based on negotiated capability:
        - If peer supports ASN4: send with 4-byte ASNs
        - If peer doesn't support ASN4: send with 2-byte ASNs, use AS_TRANS for large ASNs,
          and add AS4_PATH attribute for the real values
        """
        if negotiated.asn4:
            # Peer supports ASN4, ensure we pack with 4-byte format
            if self._asn4:
                # Already in 4-byte format
                return self._attribute(self._packed)
            else:
                # Convert from 2-byte to 4-byte format
                return self._attribute(self._pack_segments_raw(self.aspath, asn4=True))

        # Peer doesn't support ASN4, need 2-byte format with possible AS_TRANS
        has_large_asn = False
        astrans = []

        for content in self.aspath:
            local = content.__class__()
            for asn in content:
                if not asn.asn4():
                    local.append(asn)
                else:
                    local.append(AS_TRANS)
                    has_large_asn = True
            astrans.append(local)

        message = self._attribute(self._pack_segments_raw(tuple(astrans), asn4=False))
        if has_large_asn:
            # Add AS4_PATH for large ASNs
            message += AS4Path._attribute(AS4Path._pack_segments_raw(self.aspath, asn4=True))

        return message

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> 'ASPath | None':
        if not data:
            return None
        return cls.from_packet(data, negotiated.asn4)


ASPath.Empty = ASPath(b'', asn4=False)


# Backward compatibility alias
AS2Path = ASPath


# ================================================================= AS4Path (17)


@Attribute.register()
class AS4Path(ASPath):
    """AS4_PATH attribute (code 17). Always uses 4-byte ASNs."""

    ID = Attribute.CODE.AS4_PATH
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL

    Empty: ClassVar[AS4Path | None] = None

    def __init__(self, packed: bytes, asn4: bool = True) -> None:
        """Initialize from packed wire-format bytes.

        AS4Path always uses 4-byte ASNs, so asn4 parameter is ignored.
        """
        super().__init__(packed, asn4=True)

    @classmethod
    def from_packet(cls, data: bytes, asn4: bool = True) -> 'AS4Path':
        """Validate and create from wire-format bytes.

        AS4Path always uses 4-byte ASNs.
        """
        # Validate by attempting to parse - will raise Notify on error
        cls._unpack_segments_static(data, asn4=True)
        return cls(data)

    @classmethod
    def make_aspath(
        cls, segments: Sequence[SET | SEQUENCE | CONFED_SEQUENCE | CONFED_SET], asn4: bool = True
    ) -> 'AS4Path':
        """Create from parsed segments. Always uses 4-byte ASNs."""
        packed = cls._pack_segments_raw(tuple(segments), asn4=True)
        return cls(packed)

    def pack_attribute(self, negotiated: Negotiated | None = None) -> bytes:
        """Pack AS4_PATH. Always uses 4-byte format."""
        return self._attribute(self._packed)

    @classmethod
    def unpack_attribute(cls, data: bytes, negotiated: Negotiated) -> 'AS4Path | None':
        if not data:
            return None
        return cls.from_packet(data)


AS4Path.Empty = AS4Path(b'')
