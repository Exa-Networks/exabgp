#!/usr/bin/env python3
# encoding: utf-8
"""Tests for NLRICollection and MPNLRICollection wire containers

Tests the packed-bytes-first pattern for NLRI collection classes.
"""

from unittest.mock import Mock

import pytest
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message import Action
from exabgp.bgp.message.direction import Direction
from exabgp.bgp.message.update.nlri.inet import INET
from exabgp.bgp.message.update.nlri.cidr import CIDR
from exabgp.bgp.message.update.nlri.qualifier import PathInfo
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.capability.negotiated import Negotiated, OpenContext
from exabgp.protocol.ip import IP


def create_negotiated() -> Negotiated:
    """Create a Negotiated object with a mock neighbor for testing."""
    neighbor = Mock()
    neighbor.__getitem__ = Mock(return_value={'aigp': False})
    return Negotiated.make_negotiated(neighbor, Direction.OUT)


def create_context(afi: AFI = AFI.ipv4, safi: SAFI = SAFI.unicast, addpath: bool = False) -> OpenContext:
    """Create an OpenContext for testing."""
    return OpenContext.make_open_context(
        afi=afi,
        safi=safi,
        addpath=addpath,
        asn4=True,
        msg_size=4096,
        local_as=ASN(65000),
        peer_as=ASN(65001),
    )


class TestNLRICollectionFromBytes:
    """Test NLRICollection wire mode (from packed bytes)."""

    def test_create_from_empty_bytes(self) -> None:
        """Test creating NLRICollection from empty bytes."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        context = create_context()
        collection = NLRICollection(b'', context, Action.ANNOUNCE)

        assert collection.packed == b''
        assert collection.nlris == []

    def test_create_from_single_nlri_bytes(self) -> None:
        """Test creating NLRICollection from single NLRI wire bytes."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        # 192.168.1.0/24 in wire format: mask=24, 3 bytes
        packed = b'\x18\xc0\xa8\x01'
        context = create_context()
        collection = NLRICollection(packed, context, Action.ANNOUNCE)

        assert collection.packed == packed
        nlris = collection.nlris
        assert len(nlris) == 1
        assert nlris[0].cidr.prefix() == '192.168.1.0/24'

    def test_create_from_multiple_nlri_bytes(self) -> None:
        """Test creating NLRICollection from multiple NLRI wire bytes."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        # Two prefixes: 192.168.1.0/24 and 10.0.0.0/8
        packed = b'\x18\xc0\xa8\x01' + b'\x08\x0a'
        context = create_context()
        collection = NLRICollection(packed, context, Action.ANNOUNCE)

        assert collection.packed == packed
        nlris = collection.nlris
        assert len(nlris) == 2
        assert nlris[0].cidr.prefix() == '192.168.1.0/24'
        assert nlris[1].cidr.prefix() == '10.0.0.0/8'

    def test_withdraw_action_propagates(self) -> None:
        """Test that withdraw action propagates to parsed NLRIs."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        packed = b'\x18\xc0\xa8\x01'
        context = create_context()
        collection = NLRICollection(packed, context, Action.WITHDRAW)

        nlris = collection.nlris
        assert len(nlris) == 1
        assert nlris[0].action == Action.WITHDRAW


class TestNLRICollectionLazyParsing:
    """Test lazy parsing behavior of NLRICollection."""

    def test_nlris_not_parsed_until_accessed(self) -> None:
        """Test that NLRIs are parsed lazily."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection
        from exabgp.bgp.message.update.nlri import _UNPARSED

        packed = b'\x18\xc0\xa8\x01'
        context = create_context()
        collection = NLRICollection(packed, context, Action.ANNOUNCE)

        # Before accessing nlris, cache should be sentinel
        assert collection._nlris_cache is _UNPARSED

        # Access nlris
        _ = collection.nlris

        # Now cache should be populated (not the sentinel)
        assert collection._nlris_cache is not _UNPARSED

    def test_nlris_parsed_only_once(self) -> None:
        """Test that NLRIs are only parsed once."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        packed = b'\x18\xc0\xa8\x01'
        context = create_context()
        collection = NLRICollection(packed, context, Action.ANNOUNCE)

        # Access nlris twice
        nlris1 = collection.nlris
        nlris2 = collection.nlris

        # Should be the same list instance
        assert nlris1 is nlris2


class TestNLRICollectionMakeCollection:
    """Test NLRICollection semantic mode (from NLRI list)."""

    def test_make_collection_from_single_nlri(self) -> None:
        """Test creating NLRICollection from a single NLRI."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        context = create_context()

        collection = NLRICollection.make_collection(context, [nlri], Action.ANNOUNCE)

        assert len(collection.nlris) == 1
        assert collection.nlris[0] is nlri

    def test_make_collection_from_multiple_nlris(self) -> None:
        """Test creating NLRICollection from multiple NLRIs."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        cidr1 = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        cidr2 = CIDR.make_cidr(IP.pton('10.0.0.0'), 8)
        nlri1 = INET.from_cidr(cidr1, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        nlri2 = INET.from_cidr(cidr2, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        context = create_context()

        collection = NLRICollection.make_collection(context, [nlri1, nlri2], Action.ANNOUNCE)

        assert len(collection.nlris) == 2

    def test_make_collection_packed_property(self) -> None:
        """Test that semantic mode collection can generate packed bytes."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        cidr = CIDR.make_cidr(IP.pton('192.168.1.0'), 24)
        nlri = INET.from_cidr(cidr, AFI.ipv4, SAFI.unicast, Action.ANNOUNCE)
        context = create_context()

        collection = NLRICollection.make_collection(context, [nlri], Action.ANNOUNCE)
        packed = collection.packed

        # Should be able to pack the NLRI
        assert isinstance(packed, bytes)
        assert len(packed) > 0


class TestNLRICollectionRoundtrip:
    """Test bytes -> parse -> pack -> bytes roundtrip."""

    def test_roundtrip_single_prefix(self) -> None:
        """Test roundtrip for single prefix."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        original_packed = b'\x18\xc0\xa8\x01'  # 192.168.1.0/24
        context = create_context()

        # Wire -> semantic
        collection = NLRICollection(original_packed, context, Action.ANNOUNCE)
        nlris = collection.nlris

        # Semantic -> wire
        collection2 = NLRICollection.make_collection(context, nlris, Action.ANNOUNCE)
        repacked = collection2.packed

        # Verify roundtrip
        assert repacked == original_packed

    def test_roundtrip_multiple_prefixes(self) -> None:
        """Test roundtrip for multiple prefixes."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        original_packed = b'\x18\xc0\xa8\x01' + b'\x08\x0a'  # 192.168.1.0/24 + 10.0.0.0/8
        context = create_context()

        collection = NLRICollection(original_packed, context, Action.ANNOUNCE)
        nlris = collection.nlris

        collection2 = NLRICollection.make_collection(context, nlris, Action.ANNOUNCE)
        repacked = collection2.packed

        assert repacked == original_packed


class TestMPNLRICollectionSemantic:
    """Test MPNLRICollection semantic mode (from NLRI list)."""

    def test_create_from_nlris(self) -> None:
        """Test creating MPNLRICollection from NLRI list."""
        from exabgp.bgp.message.update.nlri.collection import MPNLRICollection

        context = create_context(AFI.ipv6, SAFI.unicast)
        cidr = CIDR.make_cidr(IP.pton('2001:db8::'), 32)
        nlri = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast, Action.ANNOUNCE)
        nlri.nexthop = IP.from_string('2001:db8::1')

        collection = MPNLRICollection([nlri], {}, context)

        assert collection.afi == AFI.ipv6
        assert collection.safi == SAFI.unicast
        assert len(collection.nlris) == 1

    def test_from_wire_with_mprnlri(self) -> None:
        """Test creating MPNLRICollection from MPRNLRI wire container."""
        from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
        from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI

        # Create a mock MPRNLRI from wire format
        # MP_REACH_NLRI format: AFI(2) + SAFI(1) + NH_len(1) + NH + reserved(1) + NLRI
        afi_bytes = b'\x00\x02'  # AFI.ipv6
        safi_byte = b'\x01'  # SAFI.unicast
        nh_len = b'\x10'  # 16 bytes
        nexthop = b'\x20\x01\x0d\xb8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01'
        reserved = b'\x00'
        nlri = b'\x20\x20\x01\x0d\xb8'  # 2001:db8::/32

        packed = afi_bytes + safi_byte + nh_len + nexthop + reserved + nlri
        context = create_context(AFI.ipv6, SAFI.unicast)

        mprnlri = MPRNLRI(packed, context)
        collection = MPNLRICollection.from_wire(mprnlri, None, {}, context)

        assert collection.afi == AFI.ipv6
        assert collection.safi == SAFI.unicast
        assert len(collection.nlris) == 1

    def test_from_wire_with_mpurnlri(self) -> None:
        """Test creating MPNLRICollection from MPURNLRI wire container."""
        from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
        from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

        # MP_UNREACH_NLRI format: AFI(2) + SAFI(1) + NLRI
        afi_bytes = b'\x00\x02'  # AFI.ipv6
        safi_byte = b'\x01'  # SAFI.unicast
        nlri = b'\x20\x20\x01\x0d\xb8'  # 2001:db8::/32

        packed = afi_bytes + safi_byte + nlri
        context = create_context(AFI.ipv6, SAFI.unicast)

        mpurnlri = MPURNLRI(packed, context)
        collection = MPNLRICollection.from_wire(None, mpurnlri, {}, context)

        assert collection.afi == AFI.ipv6
        assert collection.safi == SAFI.unicast
        assert len(collection.nlris) == 1


class TestMPNLRICollectionPacking:
    """Test MPNLRICollection packing methods."""

    def test_packed_reach_attributes_single_nexthop(self) -> None:
        """Test packed_reach_attributes with single nexthop."""
        from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
        from exabgp.bgp.message.open.capability.negotiated import Negotiated

        context = create_context(AFI.ipv6, SAFI.unicast)
        cidr = CIDR.make_cidr(IP.pton('2001:db8::'), 32)
        nlri = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast, Action.ANNOUNCE)
        nlri.nexthop = IP.from_string('2001:db8::1')

        collection = MPNLRICollection([nlri], {}, context)

        attrs = list(collection.packed_reach_attributes(Negotiated.UNSET))
        assert len(attrs) == 1
        # First 3 bytes after header should be AFI(2) + SAFI(1)
        # Header is flag(1) + code(1) + len(1 or 2)
        attr = attrs[0]
        assert attr[0] & 0x80  # Optional flag set
        assert attr[1] == 14  # MP_REACH_NLRI code

    def test_packed_unreach_attributes(self) -> None:
        """Test packed_unreach_attributes generates valid wire format."""
        from exabgp.bgp.message.update.nlri.collection import MPNLRICollection
        from exabgp.bgp.message.open.capability.negotiated import Negotiated

        context = create_context(AFI.ipv6, SAFI.unicast)
        cidr = CIDR.make_cidr(IP.pton('2001:db8::'), 32)
        nlri = INET.from_cidr(cidr, AFI.ipv6, SAFI.unicast, Action.WITHDRAW)

        collection = MPNLRICollection([nlri], {}, context)

        attrs = list(collection.packed_unreach_attributes(Negotiated.UNSET))
        assert len(attrs) == 1
        attr = attrs[0]
        assert attr[0] & 0x80  # Optional flag set
        assert attr[1] == 15  # MP_UNREACH_NLRI code


class TestMPNLRICollectionAFISAFI:
    """Test AFI/SAFI access from MPNLRICollection."""

    def test_afi_safi_from_context(self) -> None:
        """Test AFI/SAFI comes from context."""
        from exabgp.bgp.message.update.nlri.collection import MPNLRICollection

        context = create_context(AFI.ipv4, SAFI.multicast)
        collection = MPNLRICollection([], {}, context)

        assert collection.afi == AFI.ipv4
        assert collection.safi == SAFI.multicast

    def test_afi_safi_ipv6_unicast(self) -> None:
        """Test IPv6 unicast AFI/SAFI."""
        from exabgp.bgp.message.update.nlri.collection import MPNLRICollection

        context = create_context(AFI.ipv6, SAFI.unicast)
        collection = MPNLRICollection([], {}, context)

        assert collection.afi == AFI.ipv6
        assert collection.safi == SAFI.unicast


class TestMPRNLRIIterator:
    """Test MPRNLRI __iter__ method."""

    def test_mprnlri_iter_yields_nlris(self) -> None:
        """Test that MPRNLRI.__iter__ yields NLRIs."""
        from exabgp.bgp.message.update.attribute.mprnlri import MPRNLRI

        # MP_REACH_NLRI with one IPv6 prefix
        afi_bytes = b'\x00\x02'  # AFI.ipv6
        safi_byte = b'\x01'  # SAFI.unicast
        nh_len = b'\x10'  # 16 bytes
        nexthop = b'\x20\x01\x0d\xb8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01'
        reserved = b'\x00'
        nlri_data = b'\x20\x20\x01\x0d\xb8'  # 2001:db8::/32

        packed = afi_bytes + safi_byte + nh_len + nexthop + reserved + nlri_data
        context = create_context(AFI.ipv6, SAFI.unicast)

        mprnlri = MPRNLRI(packed, context)
        nlris = list(mprnlri)

        assert len(nlris) == 1
        assert nlris[0].afi == AFI.ipv6

    def test_mpurnlri_iter_yields_nlris(self) -> None:
        """Test that MPURNLRI.__iter__ yields NLRIs."""
        from exabgp.bgp.message.update.attribute.mpurnlri import MPURNLRI

        # MP_UNREACH_NLRI with one IPv6 prefix
        afi_bytes = b'\x00\x02'  # AFI.ipv6
        safi_byte = b'\x01'  # SAFI.unicast
        nlri_data = b'\x20\x20\x01\x0d\xb8'  # 2001:db8::/32

        packed = afi_bytes + safi_byte + nlri_data
        context = create_context(AFI.ipv6, SAFI.unicast)

        mpurnlri = MPURNLRI(packed, context)
        nlris = list(mpurnlri)

        assert len(nlris) == 1
        assert nlris[0].afi == AFI.ipv6


class TestNLRICollectionAddPath:
    """Test NLRICollection with AddPath enabled."""

    def test_addpath_nlri_parsing(self) -> None:
        """Test parsing NLRIs with AddPath path ID."""
        from exabgp.bgp.message.update.nlri.collection import NLRICollection

        # With AddPath: path_id(4) + mask(1) + prefix
        path_id = b'\x00\x00\x00\x01'  # Path ID = 1
        prefix = b'\x18\xc0\xa8\x01'  # 192.168.1.0/24

        packed = path_id + prefix
        context = create_context(AFI.ipv4, SAFI.unicast, addpath=True)

        collection = NLRICollection(packed, context, Action.ANNOUNCE)
        nlris = collection.nlris

        assert len(nlris) == 1
        assert nlris[0].path_info != PathInfo.DISABLED


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
