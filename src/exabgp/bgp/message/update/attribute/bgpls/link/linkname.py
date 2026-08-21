"""linkname.py

Created by Evelio Vila on 2016-12-01.
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

import json

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.attribute.bgpls.linkstate import BaseLS, LinkState
from exabgp.util.types import Buffer

#      0                   1                   2                   3
#      0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     |              Type             |             Length            |
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     //                     Link Name (variable)                    //
#     +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#     https://tools.ietf.org/html/rfc7752#section-3.3.2.7  Link Name TLV


@LinkState.register_lsid(tlv=1098, json_key='link-name', repr_name='Link Name')
class LinkName(BaseLS):
    # BGP-LS TLV length constants
    BGPLS_TLV_MAX_LENGTH = 255  # Maximum TLV data length

    @property
    def content(self) -> str:
        """The link name, decoded leniently rather than to the letter of the RFC.

        RFC 9552 5.3.2.7 carries the same sentence as 5.3.1.3: the field "is encoded in
        7-bit ASCII", with RFC 5890 ToASCII the sender's job.  See NodeName.content for why
        this decodes UTF-8 anyway; the two have to agree and the argument is the same.

        This returned the raw bytes and left the decoding to jsonable(), which is a
        fallback for values nobody declared rather than a decision about this one.  A name
        is text and says so here.
        """
        return bytes(self._packed).decode('utf-8', 'replace')

    @classmethod
    def make_linkname(cls, name: str) -> LinkName:
        """Factory method to create LinkName from string."""
        return cls(name.encode('utf-8'))

    def json(self, compact: bool = False) -> str:
        """Render what content holds, rather than decoding the bytes a second time.

        This did its own decode with no error handler, so it raised UnicodeDecodeError from
        the API writer for a name content renders happily.  Two renderers over one value,
        disagreeing, in the class whose encoding this whole change is about.
        """
        return f'"{self.JSON}": {json.dumps(self.content)}'

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> LinkName:
        if len(data) > cls.BGPLS_TLV_MAX_LENGTH:
            raise Notify(3, 5, 'Link Name TLV length too large')
        # No encoding gate.  It was here because json() decoded without an error handler,
        # so an unreadable name raised out of the API writer; content decodes with
        # 'replace' now and cannot.  The gate is worse than useless once that is true: the
        # BGP-LS attribute is discarded whole, so a router loses its router-ids, its
        # metrics and its SIDs because one interface description was mis-encoded.  Node
        # Name reached the same conclusion from the other direction, and the two have to
        # agree: one refused non-ASCII while the other refused non-UTF-8.
        return cls(data)
