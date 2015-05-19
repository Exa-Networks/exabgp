# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2014-12-31.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""


def run_exabgp ():
	from exabgp.application.bgp import main
	main()


def run_exabmp ():
	from exabgp.application.bmp import main
	main()


def run_healthcheck ():
	from exabgp.application.healthcheck import main
	main()


def run_cli ():
	from exabgp.application.cli import main
	main()


def run_as_cli ():
	import sys
	from exabgp.reactor.api.control import Control
	location = dict(zip(range(len(sys.argv)),sys.argv)).get(1,'/var/run/exabgp.sock')
	Control(location).run()
