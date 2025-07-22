# encoding: utf-8
"""
quantum_test.py

Created by Thomas Mangin on 2024-07-21.
Copyright (c) 2009-2024 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import unittest

from exabgp.bgp.neighbor import Neighbor
from exabgp.bgp.multipath import SuperpositionRouting
from exabgp.bgp.multipath import EntanglementProtocols
from exabgp.bgp.tunneling import Tunneling
from exabgp.protocol.ip import IP

class MultipathTest(unittest.TestCase):
    def setUp(self):
        self.neighbor = Neighbor()
        self.neighbor['local-as'] = 65000
        self.sr = SuperpositionRouting(self.neighbor)
        self.ep = EntanglementProtocols(self.neighbor)
        self.t = Tunneling(self.neighbor)

    def test_superposition_routing(self):
        paths = self.sr.generate_paths('192.168.0.0/24')
        self.assertEqual(len(paths), 3)

    def test_collapse_route_state(self):
        paths = self.sr.generate_paths('192.168.0.0/24')
        best_path = self.sr.collapse_route_state(paths)
        self.assertIsNotNone(best_path)

    def test_entanglement(self):
        peer = Neighbor()
        peer['local-as'] = 65001
        self.ep.establish_entanglement(peer)
        self.assertIn(peer.name(), self.neighbor.entangled_peers)
        self.ep.break_entanglement(peer)
        self.assertNotIn(peer.name(), self.neighbor.entangled_peers)

    def test_tunneling(self):
        nlri = self.t.create('10.0.0.1', '192.168.0.1')
        self.assertIsNotNone(nlri)

if __name__ == '__main__':
    unittest.main()
