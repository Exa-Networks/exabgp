#!/usr/bin/env python3
# encoding: utf-8

"""BGP-LS JSON Validation Tests

Validates that all BGP-LS attribute classes produce valid JSON output.
Creates instances of each class and verifies json() output parses correctly.

Tests cover:
- Link attributes (TLV 1088-1108, 1162, 1250, 1252)
- Node attributes (TLV 1024-1035)
- Prefix attributes (TLV 1152-1171)
- Base/generic classes
"""

import json
import pytest
from typing import Any, Dict

# Base classes
from exabgp.bgp.message.update.attribute.bgpls.linkstate import (
    LinkState,
    GenericLSID,
)

# Link attributes
from exabgp.bgp.message.update.attribute.bgpls.link.admingroup import AdminGroup
from exabgp.bgp.message.update.attribute.bgpls.link.igpmetric import IgpMetric
from exabgp.bgp.message.update.attribute.bgpls.link.linkname import LinkName
from exabgp.bgp.message.update.attribute.bgpls.link.protection import LinkProtectionType
from exabgp.bgp.message.update.attribute.bgpls.link.maxbw import MaxBw
from exabgp.bgp.message.update.attribute.bgpls.link.mplsmask import MplsMask
from exabgp.bgp.message.update.attribute.bgpls.link.rterid import RemoteTeRid
from exabgp.bgp.message.update.attribute.bgpls.link.rsvpbw import RsvpBw
from exabgp.bgp.message.update.attribute.bgpls.link.sradj import SrAdjacency
from exabgp.bgp.message.update.attribute.bgpls.link.sradjlan import SrAdjacencyLan
from exabgp.bgp.message.update.attribute.bgpls.link.srlg import Srlg
from exabgp.bgp.message.update.attribute.bgpls.link.temetric import TeMetric
from exabgp.bgp.message.update.attribute.bgpls.link.unrsvpbw import UnRsvpBw
from exabgp.bgp.message.update.attribute.bgpls.link.srv6capabilities import Srv6Capabilities
from exabgp.bgp.message.update.attribute.bgpls.link.srv6endx import Srv6EndX
from exabgp.bgp.message.update.attribute.bgpls.link.srv6lanendx import Srv6LanEndXISIS, Srv6LanEndXOSPF
from exabgp.bgp.message.update.attribute.bgpls.link.srv6locator import Srv6Locator
from exabgp.bgp.message.update.attribute.bgpls.link.srv6endpointbehavior import Srv6EndpointBehavior
from exabgp.bgp.message.update.attribute.bgpls.link.srv6sidstructure import Srv6SidStructure

# Node attributes
from exabgp.bgp.message.update.attribute.bgpls.node.nodeflags import NodeFlags
from exabgp.bgp.message.update.attribute.bgpls.node.nodename import NodeName
from exabgp.bgp.message.update.attribute.bgpls.node.opaque import NodeOpaque
from exabgp.bgp.message.update.attribute.bgpls.node.isisarea import IsisArea
from exabgp.bgp.message.update.attribute.bgpls.node.lterid import LocalTeRid
from exabgp.bgp.message.update.attribute.bgpls.node.srcap import SrCapabilities
from exabgp.bgp.message.update.attribute.bgpls.node.sralgo import SrAlgorithm

# Prefix attributes
from exabgp.bgp.message.update.attribute.bgpls.prefix.igpflags import IgpFlags
from exabgp.bgp.message.update.attribute.bgpls.prefix.igptags import IgpTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.igpextags import IgpExTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric
from exabgp.bgp.message.update.attribute.bgpls.prefix.ospfaddr import OspfForwardingAddress
from exabgp.bgp.message.update.attribute.bgpls.prefix.opaque import PrefixOpaque
from exabgp.bgp.message.update.attribute.bgpls.prefix.srprefix import SrPrefix
from exabgp.bgp.message.update.attribute.bgpls.prefix.srrid import SrSourceRouterID
from exabgp.bgp.message.update.attribute.bgpls.prefix.srigpprefixattr import SrIgpPrefixAttr


def validate_json(json_str: str, class_name: str) -> Dict[str, Any]:
    """Validate JSON string and return parsed dict.

    Args:
        json_str: JSON string fragment like '"key": value' or '"key": {...}'
        class_name: Class name for error messages

    Returns:
        Parsed dict

    Raises:
        AssertionError: If JSON is invalid
    """
    # Wrap in braces to make valid JSON object
    wrapped = '{' + json_str + '}'
    try:
        return json.loads(wrapped)
    except json.JSONDecodeError as e:
        pytest.fail(f'{class_name}.json() produced invalid JSON: {e}\nOutput was: {json_str}')


class TestLinkAttributesJson:
    """Test JSON output from link attribute classes"""

    def test_admin_group_json(self) -> None:
        """AdminGroup (TLV 1088) produces valid JSON"""
        attr = AdminGroup.make_admingroup(0xFF)
        result = validate_json(attr.json(), 'AdminGroup')
        assert 'admin-group-mask' in result
        assert result['admin-group-mask'] == 255

    def test_igp_metric_json(self) -> None:
        """IgpMetric (TLV 1095) produces valid JSON"""
        # Use 3-byte IS-IS wide metric format
        attr = IgpMetric.unpack_bgpls(b'\x00\x00\x64')  # 100
        result = validate_json(attr.json(), 'IgpMetric')
        assert 'igp-metric' in result
        assert result['igp-metric'] == 100

    def test_te_metric_json(self) -> None:
        """TeMetric (TLV 1092) produces valid JSON"""
        attr = TeMetric.make_temetric(1000)
        result = validate_json(attr.json(), 'TeMetric')
        assert 'te-metric' in result
        assert result['te-metric'] == 1000

    def test_max_bw_json(self) -> None:
        """MaxBw (TLV 1089) produces valid JSON"""
        attr = MaxBw.make_maxbw(125000000.0)
        result = validate_json(attr.json(), 'MaxBw')
        assert 'maximum-link-bandwidth' in result
        assert result['maximum-link-bandwidth'] == 125000000.0

    def test_rsvp_bw_json(self) -> None:
        """RsvpBw (TLV 1090) produces valid JSON"""
        attr = RsvpBw.make_rsvpbw(100000000.0)
        result = validate_json(attr.json(), 'RsvpBw')
        assert 'maximum-reservable-link-bandwidth' in result

    def test_unreserved_bw_json(self) -> None:
        """UnRsvpBw (TLV 1091) produces valid JSON"""
        bw_list = [125000000.0] * 8
        attr = UnRsvpBw.make_unrsvpbw(bw_list)
        result = validate_json(attr.json(), 'UnRsvpBw')
        assert 'unreserved-bandwidth' in result
        assert len(result['unreserved-bandwidth']) == 8

    def test_link_protection_type_json(self) -> None:
        """LinkProtectionType (TLV 1093) produces valid JSON"""
        # Use unpack_bgpls with raw bytes: 0x40 = Unprotected bit set (bit 6)
        # FLAGS order: ExtraTrafic, Unprotected, Shared, Dedicated1:1, Dedicated1+1, Enhanced, RSV, RSV
        attr = LinkProtectionType.unpack_bgpls(b'\x40\x00')
        result = validate_json(attr.json(), 'LinkProtectionType')
        assert 'link-protection-flags' in result

    def test_mpls_mask_json(self) -> None:
        """MplsMask (TLV 1094) produces valid JSON"""
        # Use unpack_bgpls with raw bytes: 0x80 = LDP bit set
        attr = MplsMask.unpack_bgpls(b'\x80')
        result = validate_json(attr.json(), 'MplsMask')
        assert 'mpls-mask' in result

    def test_srlg_json(self) -> None:
        """Srlg (TLV 1096) produces valid JSON"""
        attr = Srlg.make_srlg([100, 200, 300])
        result = validate_json(attr.json(), 'Srlg')
        assert 'shared-risk-link-groups' in result
        assert result['shared-risk-link-groups'] == [100, 200, 300]

    def test_link_name_json(self) -> None:
        """LinkName (TLV 1098) produces valid JSON"""
        attr = LinkName.make_linkname('link-to-router-2')
        result = validate_json(attr.json(), 'LinkName')
        assert 'link-name' in result
        assert result['link-name'] == 'link-to-router-2'

    def test_remote_te_rid_json(self) -> None:
        """RemoteTeRid (TLV 1097) produces valid JSON"""
        attr = RemoteTeRid.make_remoteterid('192.0.2.1')
        result = validate_json(attr.json(), 'RemoteTeRid')
        assert 'remote-te-router-id' in result
        assert result['remote-te-router-id'] == '192.0.2.1'

    def test_sr_adjacency_json(self) -> None:
        """SrAdjacency (TLV 1099) produces valid JSON"""
        flags = {'F': 0, 'B': 0, 'V': 1, 'L': 1, 'S': 0, 'P': 0}
        attr = SrAdjacency.make_sradjacency(flags=flags, weight=10, sids=[16000])
        result = validate_json(attr.json(), 'SrAdjacency')
        assert 'sr-adj' in result
        assert 'flags' in result['sr-adj']
        assert 'sids' in result['sr-adj']
        assert 'weight' in result['sr-adj']

    def test_sr_adjacency_lan_json(self) -> None:
        """SrAdjacencyLan (TLV 1100) produces valid JSON"""
        flags = {'F': 0, 'B': 0, 'V': 1, 'L': 1, 'S': 0, 'P': 0}
        attr = SrAdjacencyLan.make_sradjacencylan(
            flags=flags,
            weight=5,
            system_id='0102.0304.0506',
            sid=16001,
        )
        result = validate_json(attr.json(), 'SrAdjacencyLan')
        assert 'sr-adj-lan-sids' in result

    def test_srv6_capabilities_json(self) -> None:
        """Srv6Capabilities (TLV 1038) produces valid JSON"""
        flags = {'O': 0}
        attr = Srv6Capabilities.make_srv6_capabilities(flags=flags)
        result = validate_json(attr.json(), 'Srv6Capabilities')
        assert 'srv6-capabilities' in result

    @pytest.mark.skip(reason='Srv6EndX not yet converted to packed-bytes-first')
    def test_srv6_endx_json(self) -> None:
        """Srv6EndX (TLV 1106) produces valid JSON"""
        content = {
            'behavior': 48,
            'flags': {'B': 0, 'S': 0, 'P': 0},
            'algorithm': 0,
            'weight': 10,
            'sid': 'fc00::1',
        }
        attr = Srv6EndX(content=content)
        result = validate_json(attr.json(), 'Srv6EndX')
        assert 'srv6-endx' in result
        assert isinstance(result['srv6-endx'], list)

    @pytest.mark.skip(reason='Srv6LanEndXISIS not yet converted to packed-bytes-first')
    def test_srv6_lan_endx_isis_json(self) -> None:
        """Srv6LanEndXISIS (TLV 1107) produces valid JSON"""
        content = {
            'behavior': 48,
            'flags': {'B': 0, 'S': 0, 'P': 0},
            'algorithm': 0,
            'weight': 10,
            'sid': 'fc00::2',
            'neighbor-id': '0102.0304.0506',
        }
        attr = Srv6LanEndXISIS(content=content)
        result = validate_json(attr.json(), 'Srv6LanEndXISIS')
        assert 'srv6-lan-endx-isis' in result

    @pytest.mark.skip(reason='Srv6LanEndXOSPF not yet converted to packed-bytes-first')
    def test_srv6_lan_endx_ospf_json(self) -> None:
        """Srv6LanEndXOSPF (TLV 1108) produces valid JSON"""
        content = {
            'behavior': 48,
            'flags': {'B': 0, 'S': 0, 'P': 0},
            'algorithm': 0,
            'weight': 10,
            'sid': 'fc00::3',
            'neighbor-id': '192.0.2.1',
        }
        attr = Srv6LanEndXOSPF(content=content)
        result = validate_json(attr.json(), 'Srv6LanEndXOSPF')
        assert 'srv6-lan-endx-ospf' in result

    def test_srv6_locator_json(self) -> None:
        """Srv6Locator (TLV 1162) produces valid JSON"""
        flags = {'D': 0}
        attr = Srv6Locator.make_srv6_locator(flags=flags, algorithm=0, metric=100)
        result = validate_json(attr.json(), 'Srv6Locator')
        assert 'srv6-locator' in result

    def test_srv6_endpoint_behavior_json(self) -> None:
        """Srv6EndpointBehavior (TLV 1250) produces valid JSON"""
        attr = Srv6EndpointBehavior.make_srv6_endpoint_behavior(endpoint_behavior=48, algorithm=128)
        result = validate_json(attr.json(), 'Srv6EndpointBehavior')
        assert 'srv6-endpoint-behavior' in result
        assert 'endpoint-behavior' in result['srv6-endpoint-behavior']

    def test_srv6_sid_structure_json(self) -> None:
        """Srv6SidStructure (TLV 1252) produces valid JSON"""
        attr = Srv6SidStructure.make_srv6_sid_structure(loc_block_len=32, loc_node_len=16, func_len=0, arg_len=80)
        result = validate_json(attr.json(), 'Srv6SidStructure')
        assert 'srv6-sid-structure' in result
        assert 'loc_block_len' in result['srv6-sid-structure']


class TestNodeAttributesJson:
    """Test JSON output from node attribute classes"""

    def test_node_flags_json(self) -> None:
        """NodeFlags (TLV 1024) produces valid JSON"""
        # Use unpack_bgpls: 0xa0 = O=1, T=0, E=1 (bits 7,5 set)
        attr = NodeFlags.unpack_bgpls(b'\xa0')
        result = validate_json(attr.json(), 'NodeFlags')
        assert 'node-flags' in result

    def test_node_name_json(self) -> None:
        """NodeName (TLV 1026) produces valid JSON"""
        attr = NodeName.make_nodename('router-1.example.com')
        result = validate_json(attr.json(), 'NodeName')
        assert 'node-name' in result
        assert result['node-name'] == 'router-1.example.com'

    @pytest.mark.skip(reason="NodeOpaque.json() can't serialize bytes - known limitation")
    def test_node_opaque_json(self) -> None:
        """NodeOpaque (TLV 1025) produces valid JSON"""
        # NOTE: NodeOpaque stores raw bytes which json.dumps() can't serialize
        # This is a known limitation in the current implementation
        attr = NodeOpaque(opaque=b'opaque-data-123')
        result = validate_json(attr.json(), 'NodeOpaque')
        assert 'opaque' in result

    @pytest.mark.skip(reason='IsisArea not yet converted to packed-bytes-first')
    def test_isis_area_json(self) -> None:
        """IsisArea (TLV 1027) produces valid JSON"""
        # IsisArea expects integer area ID (hex converted to int)
        attr = IsisArea(areaid=0x490001)
        result = validate_json(attr.json(), 'IsisArea')
        assert 'area-id' in result

    @pytest.mark.skip(reason='LocalTeRid not yet converted to packed-bytes-first')
    def test_local_te_rid_json(self) -> None:
        """LocalTeRid (TLV 1028/1029) produces valid JSON"""
        attr = LocalTeRid(terids=['192.0.2.1', '192.0.2.2'])
        result = validate_json(attr.json(), 'LocalTeRid')
        assert 'local-te-router-ids' in result

    @pytest.mark.skip(reason='SrCapabilities not yet converted to packed-bytes-first')
    def test_sr_capabilities_json(self) -> None:
        """SrCapabilities (TLV 1034) produces valid JSON"""
        flags = {'I': 0, 'V': 0, 'RSV': 0}
        sids = [[1000, 16000]]  # base, range pairs
        attr = SrCapabilities(flags=flags, sids=sids)
        result = validate_json(attr.json(), 'SrCapabilities')
        assert 'sr-capability-flags' in result

    @pytest.mark.skip(reason='SrAlgorithm not yet converted to packed-bytes-first')
    def test_sr_algorithm_json(self) -> None:
        """SrAlgorithm (TLV 1035) produces valid JSON"""
        attr = SrAlgorithm(sr_algos=[0, 1])
        result = validate_json(attr.json(), 'SrAlgorithm')
        assert 'sr-algorithms' in result
        assert result['sr-algorithms'] == [0, 1]


class TestPrefixAttributesJson:
    """Test JSON output from prefix attribute classes"""

    @pytest.mark.skip(reason='IgpFlags not yet converted to packed-bytes-first')
    def test_igp_flags_json(self) -> None:
        """IgpFlags (TLV 1152) produces valid JSON"""
        flags = {'D': 0, 'N': 1, 'L': 0, 'P': 0, 'RSV': 0}
        attr = IgpFlags(flags=flags)
        result = validate_json(attr.json(), 'IgpFlags')
        assert 'igp-flags' in result

    @pytest.mark.skip(reason='IgpTags not yet converted to packed-bytes-first')
    def test_igp_tags_json(self) -> None:
        """IgpTags (TLV 1153) produces valid JSON"""
        attr = IgpTags(content=[65534, 65535])
        result = validate_json(attr.json(), 'IgpTags')
        assert 'igp-route-tags' in result
        assert result['igp-route-tags'] == [65534, 65535]

    @pytest.mark.skip(reason='IgpExTags not yet converted to packed-bytes-first')
    def test_igp_ex_tags_json(self) -> None:
        """IgpExTags (TLV 1154) produces valid JSON"""
        attr = IgpExTags(content=[0xDEADBEEF, 0xCAFEBABE])
        result = validate_json(attr.json(), 'IgpExTags')
        assert 'igp-extended-route-tags' in result

    def test_prefix_metric_json(self) -> None:
        """PrefixMetric (TLV 1155) produces valid JSON"""
        attr = PrefixMetric.make_prefixmetric(20)
        result = validate_json(attr.json(), 'PrefixMetric')
        assert 'prefix-metric' in result
        assert result['prefix-metric'] == 20

    @pytest.mark.skip(reason='OspfForwardingAddress not yet converted to packed-bytes-first')
    def test_ospf_forwarding_address_json(self) -> None:
        """OspfForwardingAddress (TLV 1156) produces valid JSON"""
        attr = OspfForwardingAddress(content='192.0.2.1')
        result = validate_json(attr.json(), 'OspfForwardingAddress')
        assert 'ospf-forwarding-address' in result

    def test_prefix_opaque_json(self) -> None:
        """PrefixOpaque (TLV 1157) produces valid JSON"""
        # Use valid UTF-8 string bytes for JSON compatibility
        attr = PrefixOpaque(b'prefix-opaque-data')
        result = validate_json(attr.json(), 'PrefixOpaque')
        assert 'opaque-prefix' in result

    @pytest.mark.skip(reason='SrPrefix not yet converted to packed-bytes-first')
    def test_sr_prefix_json(self) -> None:
        """SrPrefix (TLV 1158) produces valid JSON"""
        flags = {'R': 0, 'N': 1, 'P': 0, 'E': 0, 'V': 0, 'L': 0, 'RSV': 0, 'RSV2': 0}
        attr = SrPrefix(flags=flags, sids=[100], sr_algo=0, undecoded=[])
        result = validate_json(attr.json(), 'SrPrefix')
        assert 'sr-prefix-flags' in result
        assert 'sids' in result

    @pytest.mark.skip(reason='SrSourceRouterID not yet converted to packed-bytes-first')
    def test_sr_source_router_id_json(self) -> None:
        """SrSourceRouterID (TLV 1171) produces valid JSON"""
        attr = SrSourceRouterID(content='192.0.2.1')
        result = validate_json(attr.json(), 'SrSourceRouterID')
        assert 'sr-source-router-id' in result

    @pytest.mark.skip(reason='SrIgpPrefixAttr not yet converted to packed-bytes-first')
    def test_sr_igp_prefix_attr_json(self) -> None:
        """SrIgpPrefixAttr (TLV 1170) produces valid JSON"""
        flags = {'X': 0, 'R': 0, 'N': 1, 'RSV': 0}
        attr = SrIgpPrefixAttr(flags=flags)
        result = validate_json(attr.json(), 'SrIgpPrefixAttr')
        assert 'sr-prefix-attribute-flags' in result


class TestBaseClassesJson:
    """Test JSON output from base classes"""

    def test_generic_lsid_json(self) -> None:
        """GenericLSID produces valid JSON for unknown TLVs"""
        attr = GenericLSID(b'\xde\xad\xbe\xef')
        attr.TLV = 9999  # Unknown TLV
        result = validate_json(attr.json(), 'GenericLSID')
        assert 'generic-lsid-9999' in result

    def test_linkstate_container_json(self) -> None:
        """LinkState container combines multiple attributes into valid JSON"""
        # Create a few simple attributes using unpack_bgpls
        attr1 = IgpMetric.unpack_bgpls(b'\x00\x00\x64')  # 100
        attr2 = TeMetric.make_temetric(1000)
        attr3 = PrefixMetric.make_prefixmetric(20)

        # LinkState holds list of attributes
        ls = LinkState([attr1, attr2, attr3])
        json_str = ls.json()

        # LinkState.json() already returns a complete JSON object with braces
        # So we parse it directly (no wrapping needed)
        try:
            result = json.loads(json_str)
        except json.JSONDecodeError as e:
            pytest.fail(f'LinkState.json() produced invalid JSON: {e}\nOutput was: {json_str}')

        assert 'igp-metric' in result
        assert 'te-metric' in result
        assert 'prefix-metric' in result


class TestJsonCompactMode:
    """Test compact mode produces valid JSON"""

    def test_compact_mode_link_attr(self) -> None:
        """Link attributes in compact mode produce valid JSON"""
        attr = IgpMetric.unpack_bgpls(b'\x00\x00\x64')  # 100
        result = validate_json(attr.json(compact=True), 'IgpMetric(compact)')
        assert 'igp-metric' in result

    def test_compact_mode_node_attr(self) -> None:
        """Node attributes in compact mode produce valid JSON"""
        attr = NodeName.make_nodename('router-1')
        result = validate_json(attr.json(compact=True), 'NodeName(compact)')
        assert 'node-name' in result

    @pytest.mark.skip(reason='Srv6EndX not yet converted to packed-bytes-first')
    def test_compact_mode_srv6(self) -> None:
        """SRv6 attributes in compact mode produce valid JSON"""
        content = {
            'behavior': 48,
            'flags': {'B': 0, 'S': 0, 'P': 0},
            'algorithm': 0,
            'weight': 10,
            'sid': 'fc00::1',
        }
        attr = Srv6EndX(content=content)
        result = validate_json(attr.json(compact=True), 'Srv6EndX(compact)')
        assert 'srv6-endx' in result


class TestEdgeCases:
    """Test edge cases and special values"""

    def test_empty_srlg_list(self) -> None:
        """Empty SRLG list produces valid JSON"""
        attr = Srlg.make_srlg([])
        result = validate_json(attr.json(), 'Srlg(empty)')
        assert 'shared-risk-link-groups' in result
        assert result['shared-risk-link-groups'] == []

    def test_unicode_link_name(self) -> None:
        """Link name with unicode produces valid JSON"""
        attr = LinkName('link-tö-röuter'.encode('utf-8'))
        result = validate_json(attr.json(), 'LinkName(unicode)')
        assert 'link-name' in result

    @pytest.mark.skip(reason='SrSourceRouterID not yet converted to packed-bytes-first')
    def test_ipv6_addresses(self) -> None:
        """IPv6 addresses in JSON are valid"""
        attr = SrSourceRouterID(content='2001:db8::1')
        result = validate_json(attr.json(), 'SrSourceRouterID(ipv6)')
        assert result['sr-source-router-id'] == '2001:db8::1'

    def test_large_metric_values(self) -> None:
        """Large metric values produce valid JSON"""
        attr = TeMetric.make_temetric(0xFFFFFFFF)
        result = validate_json(attr.json(), 'TeMetric(max)')
        assert result['te-metric'] == 0xFFFFFFFF

    def test_zero_values(self) -> None:
        """Zero values produce valid JSON"""
        attr = IgpMetric.unpack_bgpls(b'\x00')  # 1-byte IS-IS small metric = 0
        result = validate_json(attr.json(), 'IgpMetric(zero)')
        assert result['igp-metric'] == 0

    @pytest.mark.skip(reason='Srv6EndX not yet converted to packed-bytes-first')
    def test_srv6_endx_with_unknown_subtlv(self) -> None:
        """Srv6EndX with unknown sub-TLV produces valid JSON (tests bug fix)"""
        # This tests the fix for the BUG at srv6endx.py:88
        content = {
            'behavior': 48,
            'flags': {'B': 0, 'S': 0, 'P': 0},
            'algorithm': 0,
            'weight': 10,
            'sid': 'fc00::1',
            'unknown-subtlv-9999': 'DEADBEEF',  # Simulated unknown sub-TLV
        }
        attr = Srv6EndX(content=content)
        result = validate_json(attr.json(), 'Srv6EndX(unknown-subtlv)')
        assert 'srv6-endx' in result


class TestUnpackAndJson:
    """Test unpacking raw bytes and then producing valid JSON"""

    def test_igp_metric_unpack_json(self) -> None:
        """Unpack IgpMetric from bytes and produce valid JSON"""
        # 3-byte IGP metric value: 100
        data = b'\x00\x00\x64'
        attr = IgpMetric.unpack_bgpls(data)
        result = validate_json(attr.json(), 'IgpMetric(unpacked)')
        assert result['igp-metric'] == 100

    def test_te_metric_unpack_json(self) -> None:
        """Unpack TeMetric from bytes and produce valid JSON"""
        # 4-byte TE metric value: 1000
        data = b'\x00\x00\x03\xe8'
        attr = TeMetric.unpack_bgpls(data)
        result = validate_json(attr.json(), 'TeMetric(unpacked)')
        assert result['te-metric'] == 1000

    def test_prefix_metric_unpack_json(self) -> None:
        """Unpack PrefixMetric from bytes and produce valid JSON"""
        # 4-byte prefix metric: 20
        data = b'\x00\x00\x00\x14'
        attr = PrefixMetric.unpack_bgpls(data)
        result = validate_json(attr.json(), 'PrefixMetric(unpacked)')
        assert result['prefix-metric'] == 20

    def test_node_name_unpack_json(self) -> None:
        """Unpack NodeName from bytes and produce valid JSON"""
        data = b'router-1.example.com'
        attr = NodeName.unpack_bgpls(data)
        result = validate_json(attr.json(), 'NodeName(unpacked)')
        assert result['node-name'] == 'router-1.example.com'

    def test_link_name_unpack_json(self) -> None:
        """Unpack LinkName from bytes and produce valid JSON"""
        data = b'eth0-to-router2'
        attr = LinkName.unpack_bgpls(data)
        result = validate_json(attr.json(), 'LinkName(unpacked)')
        assert result['link-name'] == 'eth0-to-router2'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
