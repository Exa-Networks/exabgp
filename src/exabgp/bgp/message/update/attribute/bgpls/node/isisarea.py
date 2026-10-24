"""isisarea.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                 Area Identifier (variable)                  //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.1.2


@LinkState.register()
class IsisArea(BaseLS):
    TLV = 1027
    REPR = 'ISIS area id'
    JSON = 'area-id'

    def __init__(self, areaid):
        BaseLS.__init__(self, areaid)

    @classmethod
    def unpack(cls, data):
        # int() has nothing to parse when the TLV carries no area id
        if not data:
            raise Notify(3, 5, f'Unable to decode attribute, no data for {cls.REPR}')
        return cls(int(data.hex(), 16))

    def json(self, compact=None):
        return f'"{self.JSON}": "{self.content}"'
