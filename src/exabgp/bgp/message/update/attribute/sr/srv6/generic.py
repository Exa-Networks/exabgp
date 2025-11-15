"""srv6/generic.py

Created by Ryoga Saito 2022-02-24
Copyright (c) 2022 Ryoga Saito. All rights reserved.
"""

from __future__ import annotations

from typing import Optional


class GenericSrv6ServiceSubTlv:
    def __init__(self, code: int, packed: bytes) -> None:
        self.code: int = code
        self.packed: bytes = packed

    def __repr__(self) -> str:
        return 'SRv6 Service Sub-TLV type %d not implemented' % self.code

    def json(self, compact: Optional[bool] = None) -> str:
        # TODO:
        return ''

    def pack_tlv(self) -> bytes:
        return self.packed


class GenericSrv6ServiceDataSubSubTlv:
    def __init__(self, code: int, packed: bytes) -> None:
        self.code: int = code
        self.packed: bytes = packed

    def __repr__(self) -> str:
        return 'SRv6 Service Data Sub-Sub-TLV type %d not implemented' % self.code

    def json(self, compact: Optional[bool] = None) -> str:
        # TODO:
        return ''

    def pack_tlv(self) -> bytes:
        return self.packed
