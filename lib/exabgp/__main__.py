# encoding: utf-8
"""
__init__.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import sys

from exabgp.application import run_exabgp
from exabgp.application import run_exabmp
from exabgp.application import run_cli
from exabgp.application import run_healthcheck

def main ():
	if len(sys.argv) == 1:
		run_exabgp()
		return

	if sys.argv[1] == 'bgp':
		sys.argv = sys.argv[1:]
		run_exabgp()
		return

	if sys.argv[1] == 'bmp':
		sys.argv = sys.argv[1:]
		run_exabgp()
		return

	if sys.argv[1] == 'healthcheck':
		sys.argv = sys.argv[1:]
		run_healthcheck()
		return

	if sys.argv[1] == 'cli':
		sys.argv = sys.argv[1:]
		run_cli()
		return

	run_exabgp()

if __name__ == '__main__':
	main()
