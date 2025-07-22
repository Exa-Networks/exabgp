# encoding: utf-8
"""
edge_intelligence_test.py

Created by Jules on 2025-07-21.
Copyright (c) 2024-2025 Your Company. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import unittest
from unittest.mock import Mock, patch
from exabgp.bgp.edge_intelligence_architecture import EdgeIntelligenceArchitecture, MicroField
from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.message.update.nlri.flow import EdgeFlow, Flow4Source

class EdgeIntelligenceTest(unittest.TestCase):

    def setUp(self):
        self.neighbor = Neighbor()
        self.edge_intelligence = EdgeIntelligenceArchitecture(self.neighbor)

    def test_micro_field(self):
        micro_field = MicroField("device1", {"foo": "bar"})
        self.assertEqual(micro_field.device_id, "device1")
        self.assertEqual(micro_field.context, {"foo": "bar"})
        self.assertEqual(micro_field.version, 0)

        micro_field.update_context({"foo": "baz"})
        self.assertEqual(micro_field.context, {"foo": "baz"})
        self.assertEqual(micro_field.version, 1)

    def test_edge_intelligence_architecture(self):
        self.edge_intelligence.update_micro_field("device1", {"foo": "bar"})
        micro_field = self.edge_intelligence.get_micro_field("device1")
        self.assertIsNotNone(micro_field)
        self.assertEqual(micro_field.device_id, "device1")

    def test_fog_layer_integration(self):
        with patch('random.random', return_value=0.9):
            self.assertEqual(self.edge_intelligence.decide_local_or_central(), "local")
        with patch('random.random', return_value=0.96):
            self.assertEqual(self.edge_intelligence.decide_local_or_central(), "central")

    def test_federated_learning(self):
        initial_model = self.edge_intelligence.model.copy()
        update = {"weights": [0.2, 0.3, 0.5], "bias": 0.2}
        self.edge_intelligence.handle_federated_learning_update(update)
        self.assertNotEqual(self.edge_intelligence.model, initial_model)

    def test_dynamic_peering(self):
        neighbor = Neighbor(dynamic=True)
        initial_peer_address = neighbor['peer-address']
        neighbor.update_peer({})
        self.assertNotEqual(neighbor['peer-address'], initial_peer_address)

    def test_edge_flowspec(self):
        import socket
        edge_flow = EdgeFlow(device_id="device1")
        edge_flow.add(Flow4Source(socket.inet_pton(socket.AF_INET, '1.2.3.4'), 32))
        self.assertIn("device-id", str(edge_flow))

if __name__ == '__main__':
    unittest.main()
