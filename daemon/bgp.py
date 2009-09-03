#!/usr/bin/env python
# encoding: utf-8
"""
bgp.py

Created by Thomas Mangin on 2009-08-30.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

from bgp.configuration import Configuration
from bgp.supervisor import Supervisor

if __name__ == '__main__':
	configuration = Configuration(self.text_configuration,True)
	supervisor = Supervisor(self.configuration)
	supervisor.run()
