#!/usr/bin/env python3
# encoding: utf-8

"""A BGP prefix SID TLV we do not know must still decode and re-encode"""

import json
import pytest
from exabgp.bgp.message.notification import Notify


class TestPrefixSidUnknownTlv:
    """An unregistered TLV could not be re-encoded, so the decoder raised"""

    def test_unknown_tlv_decodes_and_renders(self) -> None:
        from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

        attribute = PrefixSid.unpack(bytes.fromhex('00' + '0003' + '010203'), None, None)
        json.loads(attribute.json())
        assert attribute.pack()

    def test_truncated_tlv_is_a_protocol_error(self) -> None:
        from exabgp.bgp.message.update.attribute.sr.prefixsid import PrefixSid

        with pytest.raises(Notify):
            PrefixSid.unpack(bytes.fromhex('0100'), None, None)
