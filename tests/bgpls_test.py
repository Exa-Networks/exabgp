from exabgp.bgp.message.update.nlri.bgpls.tlvs.ipreach import IpReach
from exabgp.bgp.message.update.attribute.bgpls.prefix.igptags import IgpTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ospfroute import OspfRoute
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor
from exabgp.bgp.message.update.nlri.bgpls.tlvs.srv6sidinformation import Srv6SIDInformation
from exabgp.bgp.message.update.attribute.bgpls.link.srv6endpointbehavior import Srv6EndpointBehavior
from exabgp.bgp.message.update.attribute.bgpls.link.srv6sidstructure import Srv6SidStructure

import unittest


class TestTlvs(unittest.TestCase):
    def test_ip_reach_ipv4(self):
        data = b'\n\n\x00'

        tlv = IpReach.unpack(data, 3)
        self.assertEqual(
            tlv.json(),
            '"ip-reachability-tlv": "10.0.0.0", "ip-reach-prefix": "10.0.0.0/10"',
        )

    def test_ip_reach_ipv6(self):
        data = b'\x7f \x01\x07\x00\x00\x00\x80'
        tlv = IpReach.unpack(data, 4)
        self.assertEqual(
            tlv.json(),
            '"ip-reachability-tlv": "2001:700:0:8000::", "ip-reach-prefix": "2001:700:0:8000::/127"',
        )

    def test_igp_tags(self):
        data = b'\x00\x00\xff\xfe'
        tlv = IgpTags.unpack(data)
        self.assertEqual(tlv.json(), '"igp-route-tags": [65534]')

    def test_prefix_metric(self):
        data = b'\x00\x00\x00\x14'
        tlv = PrefixMetric.unpack(data)
        self.assertEqual(tlv.json(), '"prefix-metric": 20')

    def test_ospf_route_type(self):
        data = b'\x04'
        tlv = OspfRoute.unpack(data)
        self.assertEqual(tlv.json(), '"ospf-route-type": 4')

    def test_srv6_sid_information(self):
        data = b'\xfc0"\x01\x00\x0d\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        tlv = Srv6SIDInformation.unpack(data)
        self.assertEqual(
            tlv.json(),
            '"srv6-sid": "fc30:2201:d::"',
        )


class TestDescriptors(unittest.TestCase):
    def test_node_descriptor(self):
        data = b'\x02\x00\x00\x04\x00\x00\xff\xfd\x02\x01\x00\x04\x00\x00\x00\x00\x02\x03\x00\x04\nq?\xf0'
        igp_type = 3
        descriptor, remain = NodeDescriptor.unpack(data, igp_type)
        self.assertEqual(descriptor.json(), '{ "autonomous-system": 65533 }')
        descriptor, remain = NodeDescriptor.unpack(remain, igp_type)
        self.assertEqual(descriptor.json(), '{ "bgp-ls-identifier": "0" }')
        descriptor, remain = NodeDescriptor.unpack(remain, igp_type)
        self.assertEqual(descriptor.json(), '{ "router-id": "10.113.63.240" }')


class TestSrv6LinkAttributes(unittest.TestCase):
    def test_srv6_endpoint_behavior(self):
        data = b'\x000\x00\x80'
        tlv = Srv6EndpointBehavior.unpack(data)
        self.assertEqual(
            tlv.json(),
            '"srv6-endpoint-behavior": {"endpoint-behavior": 48, "flags": [], "algorithm": 128}',
        )

    def test_srv6_sid_structure(self):
        data = b' \x10\x00P'
        tlv = Srv6SidStructure.unpack(data)
        self.assertEqual(
            tlv.json(),
            '"srv6-sid-structure": {"loc_block_len": 32, "loc_node_len": 16, "func_len": 0, "arg_len": 80}',
        )

if __name__ == '__main__':
    unittest.main()
