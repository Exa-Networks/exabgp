"""iso

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.util.types import Buffer


# =========================================================================== ISO
#


class ISO:
    sysid: str
    area_id: str | None
    selector: str | None
    afi: int

    def __init__(self, sysid: str, selector: str | None = None, area_id: str | None = None, afi: int = 49) -> None:
        self.sysid = sysid
        self.area_id = area_id
        self.selector = selector
        self.afi = afi

    @classmethod
    def unpack_sysid(cls, data: Buffer) -> str:
        return data.hex()

    def json(self, compact: bool | None = None) -> str:
        return self.sysid
