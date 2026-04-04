#!/usr/bin/env python3
# encoding: utf-8
"""parsing.py

Created by Thomas Mangin on 2009-09-06.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import unittest

import os
import sys
import glob

from exabgp.configuration.configuration import Configuration

from exabgp.environment import getenv


environ = getenv()
environ.log.enable = True
environ.log.all = False
environ.log.configuration = False
environ.log.parser = False


class TestControl(unittest.TestCase):
    def setUp(self) -> None:
        location = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'conf', '*.conf'))
        self.files = glob.glob(location)

    # These files contains invalid attribute we can not parse
    skip = 'attributes.conf'

    def test_all_configuration(self) -> None:
        for filename in self.files:
            if filename.endswith(self.skip):
                continue
            sys.stdout.write('-' * 80)
            sys.stdout.write('\n')
            sys.stdout.write(filename)
            sys.stdout.write('\n')
            sys.stdout.write('=' * 80)
            sys.stdout.write('\n')
            sys.stdout.flush()
            configuration = Configuration(
                [
                    filename,
                ],
            )
            configuration.reload()
            del configuration


if __name__ == '__main__':
    unittest.main()
