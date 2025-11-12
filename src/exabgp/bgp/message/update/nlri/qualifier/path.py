"""bgp.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations


# ===================================================================== PathInfo
# RFC draft-ietf-idr-add-paths-09


class PathInfo:
    NOPATH: 'PathInfo | None' = None

    def __init__(self, packed: bytes | None = None, integer: int | None = None, ip: str | None = None) -> None:
        if packed:
            self.path_info: bytes = packed
        elif ip:
            self.path_info = b''.join(bytes([int(_)]) for _ in ip.split('.'))
        elif integer:
            self.path_info = b''.join(bytes([(integer >> offset) & 0xFF]) for offset in [24, 16, 8, 0])
        else:
            self.path_info = b''
        # sum(int(a)<<offset for (a,offset) in zip(ip.split('.'), range(24, -8, -8)))

    def __eq__(self, other: object) -> bool:
        return self.path_info == other.path_info  # type: ignore[attr-defined]

    def __neq__(self, other: object) -> bool:
        return self.path_info != other.path_info  # type: ignore[attr-defined]

    def __lt__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __le__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __gt__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __ge__(self, other: object) -> bool:
        raise RuntimeError('comparing PathInfo for ordering does not make sense')

    def __len__(self) -> int:
        return len(self.path_info)

    def json(self) -> str:
        if self.path_info:
            return '"path-information": "{}"'.format('.'.join([str(_) for _ in self.path_info]))
        return ''

    def __repr__(self) -> str:
        if self.path_info:
            return ' path-information {}'.format('.'.join([str(_) for _ in self.path_info]))
        return ''

    def pack(self) -> bytes:
        if self.path_info:
            return self.path_info
        return b'\x00\x00\x00\x00'


PathInfo.NOPATH = PathInfo()
