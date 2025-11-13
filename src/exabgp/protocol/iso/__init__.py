"""iso

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from typing import Optional


# =========================================================================== ISO
#


class ISO:
    sysid: str
    area_id: Optional[str]
    selector: Optional[str]
    afi: int

    def __init__(
        self, sysid: str, selector: Optional[str] = None, area_id: Optional[str] = None, afi: int = 49
    ) -> None:
        self.sysid = sysid
        self.area_id = area_id
        self.selector = selector
        self.afi = afi

    @classmethod
    def unpack_sysid(cls, data: bytes) -> str:
        return data.hex()

    def json(self, compact: Optional[bool] = None) -> str:
        return self.sysid
