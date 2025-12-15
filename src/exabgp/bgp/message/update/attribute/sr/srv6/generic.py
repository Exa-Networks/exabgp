"""srv6/generic.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

from __future__ import annotations

from typing import ClassVar

from exabgp.util.types import Buffer


class GenericSrv6ServiceSubTlv:
    # TLV code - defined in subclasses, used by registry
    TLV: ClassVar[int]

    def __init__(self, packed: Buffer, code: int) -> None:
        self._packed: Buffer = packed
        self.code: int = code

    @property
    def packed(self) -> bytes:
        """Raw TLV payload bytes."""
        return self._packed

    def __repr__(self) -> str:
        return 'SRv6 Service Sub-TLV type %d not implemented' % self.code

    def json(self, compact: bool | None = None) -> str:
        # Generic/unknown TLV - show type code and hex data
        return f'{{"type": {self.code}, "raw": "{bytes(self._packed).hex()}"}}'

    def pack_tlv(self) -> bytes:
        return self._packed

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
    def packed(self) -> bytes:
        """Raw TLV payload bytes."""
        return self._packed

    def __repr__(self) -> str:
        return 'SRv6 Service Data Sub-Sub-TLV type %d not implemented' % self.code

    def json(self, compact: bool | None = None) -> str:
        # Generic/unknown TLV - show type code and hex data
        return f'{{"type": {self.code}, "raw": "{bytes(self._packed).hex()}"}}'

    def pack_tlv(self) -> bytes:
        return self._packed

    @classmethod
    def unpack_attribute(cls, data: Buffer, length: int) -> 'GenericSrv6ServiceDataSubSubTlv':
        """Unpack TLV from bytes. Must be implemented by subclasses."""
        raise NotImplementedError('unpack_attribute must be implemented by subclasses')
