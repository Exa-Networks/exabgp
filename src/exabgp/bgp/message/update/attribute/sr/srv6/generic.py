"""srv6/generic.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

from __future__ import annotations

from struct import pack
from typing import ClassVar

from exabgp.util.types import Buffer


class GenericSrv6ServiceSubTlv:
    # TLV code - defined in subclasses, used by registry
    TLV: ClassVar[int]

    def __init__(self, packed: Buffer, code: int) -> None:
        self._packed: Buffer = packed
        self.code: int = code

    @property
    def packed(self) -> Buffer:
        """Raw TLV payload bytes."""
        return self._packed

    def __repr__(self) -> str:
        return 'SRv6 Service Sub-TLV type %d not implemented' % self.code

    def json(self, compact: bool | None = None) -> str:
        # Generic/unknown TLV - show type code and hex data
        return f'{{"type": {self.code}, "raw": "{bytes(self._packed).hex()}"}}'

    def __str__(self) -> str:
        return f'sub-tlv-{self.code}:0x{bytes(self._packed).hex()}'

    def pack_tlv(self) -> bytes:
        # The type and length come back in front of the value, as for the sub-sub-TLV.
        return pack('!BH', self.code, len(self._packed)) + bytes(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, length: int) -> 'GenericSrv6ServiceSubTlv':
        """Unpack TLV from bytes. Must be implemented by subclasses."""
        raise NotImplementedError('unpack_attribute must be implemented by subclasses')


class GenericSrv6ServiceDataSubSubTlv:
    # TLV code - defined in subclasses, used by registry
    TLV: ClassVar[int]

    def __init__(self, packed: Buffer, code: int) -> None:
        self._packed: Buffer = packed
        self.code: int = code

    @property
    def packed(self) -> Buffer:
        """Raw TLV payload bytes."""
        return self._packed

    def __repr__(self) -> str:
        return 'SRv6 Service Data Sub-Sub-TLV type %d not implemented' % self.code

    def json(self, compact: bool | None = None) -> str:
        # The sub-sub-TLVs are members of the SID Information object, beside "sid" and
        # "structure", so an unknown one is a key and a value. A bare object here made the
        # whole line unparseable.
        return f'"sub-sub-tlv-{self.code}": "{bytes(self._packed).hex()}"'

    def __str__(self) -> str:
        return f'sub-sub-tlv-{self.code}:0x{bytes(self._packed).hex()}'

    def pack_tlv(self) -> bytes:
        # The type and length come back in front of the value, or the re-encoded
        # SID Information is three octets short and misframed for every unknown one.
        return pack('!BH', self.code, len(self._packed)) + bytes(self._packed)

    @classmethod
    def unpack_attribute(cls, data: Buffer, length: int) -> 'GenericSrv6ServiceDataSubSubTlv':
        """Unpack TLV from bytes. Must be implemented by subclasses."""
        raise NotImplementedError('unpack_attribute must be implemented by subclasses')
