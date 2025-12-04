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
    BaseLS,
    FlagLS,
    GenericLSID,
    LinkState,
)


class TestBaseLSPackedBytesFirst:
    """Test BaseLS packed-bytes-first pattern"""

    def test_basels_init_requires_packed_bytes(self) -> None:
        """BaseLS.__init__ takes packed bytes parameter"""
        packed = b'\x00\x00\x00\x14'  # 4 bytes

        # Create a concrete subclass for testing
        class TestLS(BaseLS):
            TLV = 9998
            JSON = 'test-ls'
            REPR = 'TestLS'
            LEN = 4

            @property
            def content(self) -> int:
                from struct import unpack

                return unpack('!I', self._packed)[0]

            @classmethod
            def unpack_bgpls(cls, data: bytes) -> 'TestLS':
                cls.check(data)
                return cls(data)

        instance = TestLS(packed)
        assert instance._packed == packed
        assert instance.content == 20  # 0x14 = 20

    def test_basels_stores_packed_attribute(self) -> None:
        """BaseLS stores _packed bytes attribute"""
        packed = b'\xde\xad\xbe\xef'

        class TestLS(BaseLS):
            TLV = 9997

            @property
            def content(self) -> bytes:
                return self._packed

        instance = TestLS(packed)
        assert hasattr(instance, '_packed')
        assert instance._packed == packed

    def test_basels_content_property_unpacks_on_access(self) -> None:
        """BaseLS content property unpacks bytes on each access"""
        packed = pack('!I', 12345)

        class TestLS(BaseLS):
            TLV = 9996
            JSON = 'test-unpack'

            @property
            def content(self) -> int:
                from struct import unpack

                return unpack('!I', self._packed)[0]

        instance = TestLS(packed)
        # Access content multiple times - should unpack each time
        assert instance.content == 12345
        assert instance.content == 12345

    def test_basels_json_uses_content_property(self) -> None:
        """BaseLS.json() uses content property"""
        packed = pack('!I', 100)

        class TestLS(BaseLS):
            TLV = 9995
            JSON = 'test-json'
            REPR = 'TestJSON'

            @property
            def content(self) -> int:
                from struct import unpack

                return unpack('!I', self._packed)[0]

        instance = TestLS(packed)
        json_output = instance.json()
        assert '"test-json": 100' in json_output

    def test_basels_repr_uses_content_property(self) -> None:
        """BaseLS.__repr__ uses content property"""
        packed = pack('!I', 42)

        class TestLS(BaseLS):
            TLV = 9994
            JSON = 'test-repr'
            REPR = 'TestRepr'

            @property
            def content(self) -> int:
                from struct import unpack

                return unpack('!I', self._packed)[0]

        instance = TestLS(packed)
        repr_str = repr(instance)
        assert 'TestRepr' in repr_str
        assert '42' in repr_str


class TestFlagLSPackedBytesFirst:
    """Test FlagLS packed-bytes-first pattern"""

    def test_flagls_init_takes_packed_bytes(self) -> None:
        """FlagLS.__init__ takes packed bytes parameter"""
        packed = b'\x80'  # First flag bit set

        class TestFlagLS(FlagLS):
            TLV = 9993
            FLAGS = ['A', 'B', 'C', 'D', 'RSV', 'RSV', 'RSV', 'RSV']
            LEN = 1
            JSON = 'test-flags'

        instance = TestFlagLS(packed)
        assert instance._packed == packed

    def test_flagls_flags_property_unpacks_bytes(self) -> None:
        """FlagLS.flags property unpacks bytes on access"""
        packed = b'\x80'  # 10000000 - first flag set

        class TestFlagLS(FlagLS):
            TLV = 9992
            FLAGS = ['A', 'B', 'C', 'D', 'RSV', 'RSV', 'RSV', 'RSV']
            LEN = 1
            JSON = 'test-flags'

        instance = TestFlagLS(packed)
        flags = instance.flags
        assert flags['A'] == 1
        assert flags['B'] == 0

    def test_flagls_json_uses_flags_property(self) -> None:
        """FlagLS.json() uses flags property"""
        packed = b'\xc0'  # 11000000 - first two flags set

        class TestFlagLS(FlagLS):
            TLV = 9991
            FLAGS = ['X', 'Y', 'Z', 'W', 'RSV', 'RSV', 'RSV', 'RSV']
            LEN = 1
            JSON = 'test-flag-json'
            REPR = 'TestFlagJSON'

        instance = TestFlagLS(packed)
        json_output = instance.json()
        assert '"test-flag-json"' in json_output
        # Flags should be in JSON
        assert '"X": 1' in json_output or '"X":1' in json_output


class TestGenericLSIDPackedBytesFirst:
    """Test GenericLSID packed-bytes-first pattern"""

    def test_genericlsid_init_takes_packed_bytes(self) -> None:
        """GenericLSID.__init__ takes packed bytes"""
        packed = b'\x01\x02\x03\x04'

        instance = GenericLSID(packed)
        assert instance._packed == packed

    def test_genericlsid_content_returns_list_with_packed(self) -> None:
        """GenericLSID.content returns list containing packed bytes"""
        packed = b'\xde\xad\xbe\xef'

        instance = GenericLSID(packed)
        # GenericLSID.content should be a list for merge support
        assert isinstance(instance.content, list)
        assert packed in instance.content

    def test_genericlsid_merge_appends_to_content(self) -> None:
        """GenericLSID.merge() appends other's content"""
        packed1 = b'\x01\x02'
        packed2 = b'\x03\x04'

        instance1 = GenericLSID(packed1)
        instance2 = GenericLSID(packed2)

        instance1.merge(instance2)

        # After merge, content should have both
        assert packed1 in instance1.content
        assert packed2 in instance1.content

    def test_genericlsid_unpack_bgpls_returns_instance(self) -> None:
        """GenericLSID.unpack_bgpls() returns instance with packed bytes"""
        packed = b'\xca\xfe\xba\xbe'

        instance = GenericLSID.unpack_bgpls(packed)
        assert instance._packed == packed


class TestLinkStateUnpackWithPackedPattern:
    """Test LinkState.unpack_attribute works with packed-bytes-first subclasses"""

    def test_linkstate_unpack_creates_packed_instances(self) -> None:
        """LinkState.unpack_attribute creates instances using packed bytes pattern"""
        from unittest.mock import Mock

        # Build a TLV: Type=1155 (PrefixMetric), Length=4, Value=20
        tlv_data = b'\x04\x83\x00\x04\x00\x00\x00\x14'

        negotiated = Mock()
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


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
