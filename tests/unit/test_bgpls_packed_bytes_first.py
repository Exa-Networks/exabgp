#!/usr/bin/env python3
# encoding: utf-8

"""Unit tests for BGP-LS packed-bytes-first pattern conversion

Tests the new packed-bytes-first pattern for BGP-LS classes:
- BaseLS: __init__(packed: bytes), @property content
- FlagLS: __init__(packed: bytes), @property flags
- GenericLSID: __init__(packed: bytes)
- Subclasses: factory methods for semantic construction

TDD: These tests are written BEFORE the implementation changes.
They should FAIL initially, proving they test something real.
"""

import pytest
from struct import pack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import (
    GenericLSID,
    LinkState,
)
from exabgp.bgp.message.update.attribute.bgpls.node.nodeflags import NodeFlags
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric
from tests import negotiation


# The BaseLS and FlagLS behaviour is checked through registered subclasses, PrefixMetric
# (four octets, an int) and NodeFlags (one octet of flags): the compiled build refuses a
# class written in a test inheriting from a compiled one.


class TestBaseLSPackedBytesFirst:
    """Test BaseLS packed-bytes-first pattern"""

    def test_basels_init_requires_packed_bytes(self) -> None:
        """BaseLS.__init__ takes packed bytes parameter"""
        packed = b'\x00\x00\x00\x14'  # 4 bytes
        instance = PrefixMetric(packed)
        assert instance._packed == packed
        assert instance.content == 20  # 0x14 = 20

    def test_basels_stores_packed_attribute(self) -> None:
        """BaseLS stores _packed bytes attribute"""
        packed = b'\xde\xad\xbe\xef'
        instance = PrefixMetric(packed)
        assert hasattr(instance, '_packed')
        assert instance._packed == packed

    def test_basels_content_property_unpacks_on_access(self) -> None:
        """BaseLS content property unpacks bytes on each access"""
        instance = PrefixMetric(pack('!I', 12345))
        # Access content multiple times - should unpack each time
        assert instance.content == 12345
        assert instance.content == 12345

    def test_basels_json_uses_content_property(self) -> None:
        """BaseLS.json() uses content property"""
        instance = PrefixMetric(pack('!I', 100))
        assert '"prefix-metric": 100' in instance.json()

    def test_basels_repr_uses_content_property(self) -> None:
        """BaseLS.__repr__ uses content property"""
        repr_str = repr(PrefixMetric(pack('!I', 42)))
        assert 'prefix_metric' in repr_str
        assert '42' in repr_str


class TestFlagLSPackedBytesFirst:
    """Test FlagLS packed-bytes-first pattern"""

    def test_flagls_init_takes_packed_bytes(self) -> None:
        """FlagLS.__init__ takes packed bytes parameter"""
        packed = b'\x80'  # First flag bit set
        instance = NodeFlags(packed)
        assert instance._packed == packed

    def test_flagls_flags_property_unpacks_bytes(self) -> None:
        """FlagLS.flags property unpacks bytes on access"""
        flags = NodeFlags(b'\x80').flags  # 10000000 - first flag set
        assert flags['O'] == 1
        assert flags['T'] == 0

    def test_flagls_json_uses_flags_property(self) -> None:
        """FlagLS.json() uses flags property"""
        json_output = NodeFlags(b'\xc0').json()  # 11000000 - first two flags set
        assert '"node-flags"' in json_output
        assert '"O": 1' in json_output and '"T": 1' in json_output and '"E": 0' in json_output


class TestGenericLSIDPackedBytesFirst:
    """Test GenericLSID packed-bytes-first pattern"""

    def test_genericlsid_init_takes_packed_bytes(self) -> None:
        """GenericLSID.__init__ takes packed bytes"""
        packed = b'\x01\x02\x03\x04'

        instance = GenericLSID(packed)
        assert instance._packed == packed

    def test_genericlsid_content_returns_hex_string(self) -> None:
        """GenericLSID.content returns hex string of packed bytes"""
        packed = b'\xde\xad\xbe\xef'

        instance = GenericLSID(packed)
        # GenericLSID.content returns hex string, json() wraps in array for backward compat
        assert isinstance(instance.content, str)
        assert instance.content == '0xDEADBEEF'
        # json() should output array for backward compatibility
        assert '["0xDEADBEEF"]' in instance.json()

    def test_genericlsid_unpack_bgpls_returns_instance(self) -> None:
        """GenericLSID.unpack_bgpls() returns instance with packed bytes"""
        packed = b'\xca\xfe\xba\xbe'

        instance = GenericLSID.unpack_bgpls(packed)
        assert instance._packed == packed


class TestLinkStateUnpackWithPackedPattern:
    """Test LinkState.unpack_attribute works with packed-bytes-first subclasses"""

    def test_linkstate_unpack_creates_packed_instances(self) -> None:
        """LinkState.unpack_attribute creates instances using packed bytes pattern"""

        # Build a TLV: Type=1155 (PrefixMetric), Length=4, Value=20
        tlv_data = b'\x04\x83\x00\x04\x00\x00\x00\x14'

        negotiated = negotiation.negotiated(())
        ls = LinkState.unpack_attribute(tlv_data, negotiated)

        assert len(ls.ls_attrs) == 1
        attr = ls.ls_attrs[0]

        # Should have _packed attribute
        assert hasattr(attr, '_packed')
        # Content should be correct
        assert attr.content == 20


class TestPrefixMetricPackedBytesFirst:
    """Test PrefixMetric conversion to packed-bytes-first"""

    def test_prefixmetric_init_takes_packed_bytes(self) -> None:
        """PrefixMetric.__init__ takes packed bytes"""
        from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric

        packed = pack('!I', 100)
        instance = PrefixMetric(packed)

        assert instance._packed == packed
        assert instance.content == 100

    def test_prefixmetric_make_factory(self) -> None:
        """PrefixMetric.make_prefixmetric() factory method"""
        from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric

        instance = PrefixMetric.make_prefixmetric(100)

        assert instance.content == 100
        # Should have packed bytes
        assert instance._packed == pack('!I', 100)

    def test_prefixmetric_unpack_returns_packed_instance(self) -> None:
        """PrefixMetric.unpack_bgpls returns instance with _packed"""
        from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric

        packed = pack('!I', 42)
        instance = PrefixMetric.unpack_bgpls(packed)

        assert instance._packed == packed
        assert instance.content == 42


class TestIgpMetricPackedBytesFirst:
    """Test IgpMetric conversion to packed-bytes-first"""

    def test_igpmetric_init_takes_packed_bytes(self) -> None:
        """IgpMetric.__init__ takes packed bytes (variable length)"""
        from exabgp.bgp.message.update.attribute.bgpls.link.igpmetric import IgpMetric

        # 3-byte IS-IS wide metric
        packed = b'\x00\x00\x64'  # 100
        instance = IgpMetric(packed)

        assert instance._packed == packed
        assert instance.content == 100

    def test_igpmetric_unpack_ospf(self) -> None:
        """IgpMetric unpacks OSPF 2-byte metric"""
        from exabgp.bgp.message.update.attribute.bgpls.link.igpmetric import IgpMetric

        packed = pack('!H', 200)  # 2-byte OSPF metric
        instance = IgpMetric.unpack_bgpls(packed)

        assert instance._packed == packed
        assert instance.content == 200

    def test_igpmetric_unpack_isis_small(self) -> None:
        """IgpMetric unpacks IS-IS small 1-byte metric"""
        from exabgp.bgp.message.update.attribute.bgpls.link.igpmetric import IgpMetric

        packed = b'\x0a'  # 1-byte IS-IS small metric = 10
        instance = IgpMetric.unpack_bgpls(packed)

        assert instance._packed == packed
        assert instance.content == 10

    def test_igpmetric_unpack_isis_wide(self) -> None:
        """IgpMetric unpacks IS-IS wide 3-byte metric"""
        from exabgp.bgp.message.update.attribute.bgpls.link.igpmetric import IgpMetric

        packed = b'\x00\x03\xe8'  # 3-byte IS-IS wide metric = 1000
        instance = IgpMetric.unpack_bgpls(packed)

        assert instance._packed == packed
        assert instance.content == 1000


class TestNodeNamePackedBytesFirst:
    """Test NodeName conversion to packed-bytes-first"""

    def test_nodename_init_takes_packed_bytes(self) -> None:
        """NodeName.__init__ takes packed bytes"""
        from exabgp.bgp.message.update.attribute.bgpls.node.nodename import NodeName

        packed = b'router-1.example.com'
        instance = NodeName(packed)

        assert instance._packed == packed
        assert instance.content == 'router-1.example.com'

    def test_nodename_make_factory(self) -> None:
        """NodeName.make_nodename() factory method"""
        from exabgp.bgp.message.update.attribute.bgpls.node.nodename import NodeName

        instance = NodeName.make_nodename('test-router')

        assert instance.content == 'test-router'
        assert instance._packed == b'test-router'


class TestNodeFlagsPackedBytesFirst:
    """Test NodeFlags (FlagLS subclass) conversion"""

    def test_nodeflags_init_takes_packed_bytes(self) -> None:
        """NodeFlags.__init__ takes packed bytes"""
        from exabgp.bgp.message.update.attribute.bgpls.node.nodeflags import NodeFlags

        packed = b'\x80'  # Overload bit set
        instance = NodeFlags(packed)

        assert instance._packed == packed
        flags = instance.flags
        assert flags['O'] == 1  # Overload
        assert flags['T'] == 0

    def test_nodeflags_unpack_bgpls(self) -> None:
        """NodeFlags.unpack_bgpls returns packed instance"""
        from exabgp.bgp.message.update.attribute.bgpls.node.nodeflags import NodeFlags

        packed = b'\xa0'  # O=1, T=0, E=1
        instance = NodeFlags.unpack_bgpls(packed)

        assert instance._packed == packed
        assert instance.flags['O'] == 1
        assert instance.flags['E'] == 1


class TestLocalRouterIdPackedBytesFirst:
    """Test LocalRouterId packed-bytes-first pattern"""

    def test_local_router_id_init_takes_packed_bytes(self) -> None:
        """LocalRouterId.__init__ takes packed bytes"""
        from exabgp.bgp.message.update.attribute.bgpls.node.localrouterid import LocalRouterId

        # IPv4 address
        packed = b'\xc0\x00\x02\x01'  # 192.0.2.1
        instance = LocalRouterId(packed)

        assert instance._packed == packed
        assert instance.content == '192.0.2.1'

    def test_local_router_id_make_factory_ipv4(self) -> None:
        """LocalRouterId.make_local_router_id() factory for IPv4"""
        from exabgp.bgp.message.update.attribute.bgpls.node.localrouterid import LocalRouterId

        instance = LocalRouterId.make_local_router_id('192.0.2.1')

        assert instance.content == '192.0.2.1'
        assert instance._packed == b'\xc0\x00\x02\x01'

    def test_local_router_id_make_factory_ipv6(self) -> None:
        """LocalRouterId.make_local_router_id() factory for IPv6"""
        from exabgp.bgp.message.update.attribute.bgpls.node.localrouterid import LocalRouterId

        instance = LocalRouterId.make_local_router_id('2001:db8::1')

        assert '2001:db8::1' in instance.content
        assert len(instance._packed) == 16


class TestNodeOpaquePackedBytesFirst:
    """Test NodeOpaque packed-bytes-first pattern"""

    def test_node_opaque_init_takes_packed_bytes(self) -> None:
        """NodeOpaque.__init__ takes packed bytes"""
        from exabgp.bgp.message.update.attribute.bgpls.node.opaque import NodeOpaque

        packed = b'\xde\xad\xbe\xef'
        instance = NodeOpaque(packed)

        assert instance._packed == packed
        # opaque payloads are arbitrary IGP TLVs, so content is their hex, not the bytes
        assert instance.content == packed.hex()

    def test_node_opaque_make_factory(self) -> None:
        """NodeOpaque.make_node_opaque() factory method"""
        from exabgp.bgp.message.update.attribute.bgpls.node.opaque import NodeOpaque

        data = b'opaque-data-123'
        instance = NodeOpaque.make_node_opaque(data)

        # opaque payloads are arbitrary IGP TLVs, so content is their hex, not the bytes
        assert instance.content == data.hex()
        assert instance._packed == data


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
