"""keepalive.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from struct import pack

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify

# =================================================================== KeepAlive
#


@Message.register
class KeepAlive(Message):
    ID = Message.CODE.KEEPALIVE
    TYPE = bytes([Message.CODE.KEEPALIVE])

    def message(self, negotiated=None):
        return self._message(b'')

    def __str__(self):
        return 'KEEPALIVE'

    @classmethod
    def unpack_message(cls, data, direction, negotiated):  # pylint: disable=W0613
        # This can not happen at decode time as we check the length of the KEEPALIVE message
        # But could happen when calling the function programmatically
        if data:
            # this read Notify(code, subcode) with the text as the code and the
            # hexstring as the subcode, never formatting either, so code and
            # subcode were str and message() would have raised on
            # bytes([self.code, self.subcode]) rather than sending anything.
            # RFC 4271 6.1: a KEEPALIVE whose Length is not 19 is Bad Message
            # Length, and the data is the erroneous Length field
            raise Notify(1, 2, pack('!H', Message.HEADER_LEN + len(data)))
        return cls()
