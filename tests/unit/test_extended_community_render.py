#!/usr/bin/env python3
# encoding: utf-8

"""Extended communities must render without exhausting the stack"""

import pytest
from exabgp.bgp.message.notification import Notify


class TestExtendedCommunityRepr:
    """Eight bytes exhausted the stack, from the writer feeding the API"""

    def test_traffic_redirect_asn4_does_not_recurse(self) -> None:
        from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

        # a registered class with no __repr__ of its own inherited the base one,
        # whose delegation called straight back into itself
        community = ExtendedCommunity.unpack(bytes.fromhex('0208359d0f6f18f2'))
        assert repr(community)

    def test_every_registered_community_renders(self) -> None:
        from exabgp.bgp.message.update.attribute.community.extended import (
            ExtendedCommunity,
            ExtendedCommunityIPv6,
        )

        for base in (ExtendedCommunity, ExtendedCommunityIPv6):
            for (kind, subtype), klass in base.registered_extended.items():
                data = bytes([kind, subtype]) + b'\x00' * (base.SIZE - 2)
                try:
                    community = base.unpack(data)
                except Notify:
                    continue
                assert repr(community)
                assert str(community)

    def test_short_community_is_a_protocol_error(self) -> None:
        from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunity

        with pytest.raises(Notify):
            ExtendedCommunity.unpack(b'\x02')

    def test_ipv6_redirect_decodes(self) -> None:
        from exabgp.bgp.message.update.attribute.community.extended import ExtendedCommunityIPv6

        # this sliced 9 bytes for a format needing 18, so it never decoded at all
        community = ExtendedCommunityIPv6.unpack(bytes.fromhex('000b') + b'\x00' * 18)
        assert 'redirect' in str(community)
