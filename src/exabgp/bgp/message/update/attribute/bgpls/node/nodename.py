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


@LinkState.register_lsid(tlv=1026, json_key='node-name', repr_name='Node Name')
class NodeName(BaseLS):
    @property
    def content(self) -> str:
        """The node name, decoded leniently rather than to the letter of the RFC.

        RFC 9552 5.3.1.3 says the field "is encoded in 7-bit ASCII", and puts the duty of
        applying RFC 5890 ToASCII on the sender's interface, so the conformant way to carry
        an accented name is its punycode.  A peer putting raw UTF-8 here is not following
        the RFC, and the nine year old decode('ascii') was matching what the RFC expects.

        We accept it anyway, and the reason is proportion rather than permission.  This is
        a descriptive field, and refusing it from the decoder discards the WHOLE BGP-LS
        attribute: the router-ids, the metrics and the SIDs go with it over something
        cosmetic.  UTF-8 is a superset of ASCII, so a conformant name decodes identically
        and only a non-conformant one is affected, which is the right place to be lenient.

        'replace' rather than a raise, so a name we cannot read costs nothing at all.
        """
        return bytes(self._packed).decode('utf-8', 'replace')

    @classmethod
    def make_nodename(cls, name: str) -> NodeName:
        """Factory method to create NodeName from string.

        Args:
            name: The node name string

        Returns:
            NodeName instance with packed bytes
        """
        return cls(name.encode('utf-8'))

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> NodeName:
        if len(data) > MAX_NODE_NAME_LENGTH:
            raise Notify(3, 5, 'Node Name TLV length too large')
        # No encoding gate.  It existed because content decoded ASCII strictly, so an
        # unreadable name raised from the accessor; content cannot raise now.  The RFC does
        # ask for 7-bit ASCII here, so refusing was defensible, but the cost of refusing is
        # the whole attribute and the field is descriptive: see content for the argument.
        return cls(data)

    def json(self, compact: bool = False) -> str:
        return f'"{self.JSON}": {json.dumps(self.content)}'
