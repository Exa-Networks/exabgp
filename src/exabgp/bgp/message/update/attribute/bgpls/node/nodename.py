"""nodename.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.notification import Notify

from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS
from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState
from exabgp.util.types import Buffer


#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                     Node Name (variable)                    //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752 Sec 3.3.1.3.  Node Name TLV

# Node name length constraint
MAX_NODE_NAME_LENGTH = 255  # Maximum length for node name TLV


@LinkState.register_lsid()
class NodeName(BaseLS):
    TLV = 1026
    MERGE = False
    REPR = 'Node Name'
    JSON = 'node-name'

    @property
    def content(self) -> str:
        """Unpack and return the node name as a string."""
        return self._packed.decode('ascii')

    @classmethod
    def make_nodename(cls, name: str) -> NodeName:
        """Factory method to create NodeName from string.

        Args:
            name: The node name string

        Returns:
            NodeName instance with packed bytes
        """
        return cls(name.encode('ascii'))

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> NodeName:
        if len(data) > MAX_NODE_NAME_LENGTH:
            raise Notify(3, 5, 'Node Name TLV length too large')
        return cls(data)

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self.content)}'
