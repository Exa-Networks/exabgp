from exabgp.bgp.message.update.nlri.bgpls.tlvs.ipreach import IpReach
from exabgp.bgp.message.update.attribute.bgpls.prefix.igptags import IgpTags
from exabgp.bgp.message.update.attribute.bgpls.prefix.prefixmetric import PrefixMetric
from exabgp.bgp.message.update.nlri.bgpls.tlvs.ospfroute import OspfRoute
from exabgp.bgp.message.update.nlri.bgpls.tlvs.node import NodeDescriptor

import unittest


class TestTlvs(unittest.TestCase):

    def test_ip_reach(self,):
        data = b'\n\n\x00'
        tlv = IpReach.unpack(data)
        self.assertEqual(tlv.json(), '"ip-reachability-tlv": "10.0.0.0", "ip-reach-prefix": "10.0.0.0/10"')

    def test_igp_tags(self,):
        data = b'\x00\x00\xff\xfe'
        tlv = IgpTags.unpack(data, len(data))
        self.assertEqual(tlv.json(), '"igp-route-tags": [65534]')

    def test_prefix_metric(self,):
        data = b'\x00\x00\x00\x14'
        tlv = PrefixMetric.unpack(data, len(data))
        self.assertEqual(tlv.json(), '"prefix-metric": 20')

    def test_ospf_route_type(self,):
        data = b'\x04'
        tlv = OspfRoute.unpack(data)
        self.assertEqual(tlv.json(), '"ospf-route-type": 4')


class TestDescriptors(unittest.TestCase):

    def test_node_descriptor(self,):
        data = b'\x02\x00\x00\x04\x00\x00\xff\xfd\x02\x01\x00\x04\x00\x00\x00\x00\x02\x03\x00\x04\nq?\xf0'
        igp_type = 3
        descriptor, remain = NodeDescriptor.unpack(data, igp_type)
        self.assertEqual(descriptor.json(), '"autonomous-system": 65533')
        descriptor, remain = NodeDescriptor.unpack(remain, igp_type)
        self.assertEqual(descriptor.json(), '"bgp-ls-identifier": "0"')
        descriptor, remain = NodeDescriptor.unpack(remain, igp_type)
        self.assertEqual(descriptor.json(), '"router-id": "10.113.63.240"')


if __name__ == '__main__':
    unittest.main()