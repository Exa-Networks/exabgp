# encoding: utf-8
"""
parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import os
import sys
import uuid

from exabgp.configuration.core import Section

from exabgp.configuration.process.parser import encoder
from exabgp.configuration.process.parser import run


class ParseProcess (Section):
	syntax = \
		'process name-of-process {\n' \
		'   run /path/to/command with its args;\n' \
		'   encoder text|json;\n' \
		'}' \

	known = {
		'encoder': encoder,
		'run':     run,
	}

	action = {
		'encoder': 'set-command',
		'run':     'set-command',
	}

	name = 'process'

	def __init__ (self, tokeniser, scope, error, logger):
		Section.__init__(self,tokeniser,scope,error,logger)
		self.processes = {}
		self._processes = []
		self.named = ''

	def clear (self):
		self.processes = {}
		self._processes = []

	def pre (self):
		self.named = self.tokeniser.line[1]
		if self.named in self._processes:
			return self.error.set('a process section called "%s" already exists' % self.named)
		self._processes.append(self.named)
		return True

	def post (self):
		difference = set(self.known.keys()).difference(self.scope.get().keys())
		if difference:
			return self.error.set('unset process sections: %s' % ', '.join(difference))
		self.processes.update({self.named: self.scope.pop()})
		return True

	def add_api (self):
		if not os.environ.get('exabgp_cli_pipe',''):
			return
		name = 'api-internal-cli-%x' % uuid.uuid1().fields[0]
		api = {
			name: {
				'run': [sys.executable, os.path.join(os.environ.get('PWD',''),sys.argv[0])],
				'encoder': 'text'
			}
		}
		self._processes.append(name)
		self.processes.update(api)
