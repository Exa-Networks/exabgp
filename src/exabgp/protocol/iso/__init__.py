# encoding: utf-8
"""
iso

Created by Evelio Vila on 2016-11-26. eveliovila@gmail.com
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations


# =========================================================================== ISO
#


class ISO(object):
    def __init__(self, sysid, selector=None, area_id=None, afi=49):
        self.sysid = sysid
        self.area_id = area_id
        self.selector = selector
        self.afi = afi

    @classmethod
    def unpack_sysid(cls, data):
        return data.hex()

    def json(self, compact=None):
        return self.sysid
