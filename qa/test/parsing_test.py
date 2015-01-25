import unittest

import os
import glob

from exabgp.configuration.ancient import Configuration
from exabgp.configuration.check import check_neighbor

from exabgp.configuration.setup import environment
env = environment.setup('')
env.log.enable = True
env.log.all = False
env.log.configuration = False
env.log.parser = False

class TestControl (unittest.TestCase):
    def setUp (self):
        location = os.path.abspath(os.path.join(os.path.dirname(__file__),'..','conf','*.conf'))
        self.files = glob.glob(location)

    def test_all_configuration (self):
        neighbors = []
        for file in self.files:
            # print file.split('/')[-1]
            configuration = Configuration([file,])
            configuration.reload()
            self.assertEqual(check_neighbor(configuration.neighbor),True)
            del configuration

if __name__ == '__main__':
    unittest.main()
