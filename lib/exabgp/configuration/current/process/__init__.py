# encoding: utf-8
"""
parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import stat
import shlex

from exabgp.bgp.message import Message

from exabgp.configuration.current.generic import Generic


class ParseProcess (Generic):
	syntax = \
		'syntax:\n' \
		'process name-of-process {\n' \
		'   run /path/to/command with its args;\n' \
		'   encoder text|json;\n' \
		'   neighbor-changes;\n' \
		'   send {\n' \
		'      parsed;\n' \
		'      packets;\n' \
		'      consolidate;\n' \
		'      open;\n' \
		'      update;\n' \
		'      notification;\n' \
		'      keepalive;\n' \
		'      refresh;\n' \
		'      operational;\n' \
		'   }\n' \
		'   receive {\n' \
		'      parsed;\n' \
		'      packets;\n' \
		'      consolidate;\n' \
		'      open;\n' \
		'      update;\n' \
		'      notification;\n' \
		'      keepalive;\n' \
		'      refresh;\n' \
		'      operational;\n' \
		'   }\n' \
		'}\n\n' \


	def __init__ (self, scope, error, logger):
		self.scope = scope
		self.error = error
		self.logger = logger

	def clear (self):
		pass

	def configuration (self, name):
		self._fname = name

	def command (self, name, command, tokens):
		if command in ('packets','parsed','consolidate','neighbor-changes'):
			self.scope.content[-1]['%s-%s' % (name,command)] = True
			return True

		message = Message.from_string(command)
		if message == Message.CODE.NOP:
			return self.error.set('unknown process message')

		self.scope.content[-1]['%s-%d' % (name,message)] = True
		return True


	def encoder (self, name, command, tokens):
		if tokens and tokens[0] in ('text','json'):
			self.scope.content[-1][command] = tokens[0]
			return True

		return self.error.set(self.syntax)

	def run (self, name, command, tokens):
		line = ' '.join(tokens).strip()
		if len(line) > 2 and line[0] == line[-1] and line[0] in ['"',"'"]:
			line = line[1:-1]
		if ' ' in line:
			args = shlex.split(line,' ')
			prg,args = args[0],args[1:]
		else:
			prg = line
			args = ''

		if not prg:
			return self.error.set('prg requires the program to prg as an argument (quoted or unquoted)')

		if prg[0] != '/':
			if prg.startswith('etc/exabgp'):
				parts = prg.split('/')

				env = os.environ.get('ETC','')
				if env:
					options = [
						os.path.join(env.rstrip('/'),*os.path.join(parts[2:])),
						'/etc/exabgp'
					]
				else:
					options = []
					options.append('/etc/exabgp')
					pwd = os.environ.get('PWD','').split('/')
					if pwd:
						# without abspath the path is not / prefixed !
						if pwd[-1] in ('etc','sbin'):
							options.append(os.path.abspath(os.path.join(os.path.join(*pwd[:-1]),os.path.join(*parts))))
						if 'etc' not in pwd:
							options.append(os.path.abspath(os.path.join(os.path.join(*pwd),os.path.join(*parts))))
			else:
				options = [
					os.path.abspath(os.path.join(os.path.dirname(self._fname),prg)),
					'/etc/exabgp'
				]
			for option in options:
				if os.path.exists(option):
					prg = option

		if not os.path.exists(prg):
			return self.error.set('can not locate the the program "%s"' % prg)

		# race conditions are possible, those are sanity checks not security ones ...
		s = os.stat(prg)

		if stat.S_ISDIR(s.st_mode):
			return self.error.set('can not execute directories "%s"' % prg)

		if s.st_mode & stat.S_ISUID:
			return self.error.set('refusing to run setuid programs "%s"' % prg)

		check = stat.S_IXOTH
		if s.st_uid == os.getuid():
			check |= stat.S_IXUSR
		if s.st_gid == os.getgid():
			check |= stat.S_IXGRP

		if not check & s.st_mode:
			return self.error.set('exabgp will not be able to run this program "%s"' % prg)

		if args:
			self.scope.content[-1][command] = [prg] + args
		else:
			self.scope.content[-1][command] = [prg,]
		return True

		# we want to have a socket for the cli
		# if self.fifo:
		# 	_cli_name = 'CLI'
		# 	configuration.processes[_cli_name] = {
		# 		'neighbor': '*',
		# 		'encoder': 'json',
		# 		'run': [sys.executable, sys.argv[0]],
		#
		# 		'neighbor-changes': False,
		#
		# 		'receive-consolidate': False,
		# 		'receive-packets': False,
		# 		'receive-parsed': False,
		#
		# 		'send-consolidate': False,
		# 		'send-packets': False,
		# 		'send-parsed': False,
		# 	}
		#
		# 	for direction in ['send','receive']:
		# 		for message in [
		# 			Message.CODE.NOTIFICATION,
		# 			Message.CODE.OPEN,
		# 			Message.CODE.KEEPALIVE,
		# 			Message.CODE.UPDATE,
		# 			Message.CODE.ROUTE_REFRESH,
		# 			Message.CODE.OPERATIONAL
		# 		]:
		# 			configuration.processes[_cli_name]['%s-%d' % (direction,message)] = False
		#
		# for name in configuration.processes.keys():
		# 	process = configuration.processes[name]
		#
		# 	neighbor.api.set('neighbor-changes',process.get('neighbor-changes',False))
		#
		# 	for direction in ['send','receive']:
		# 		for option in ['packets','consolidate','parsed']:
		# 			neighbor.api.set_value(direction,option,process.get('%s-%s' % (direction,option),False))
		#
		# 		for message in [
		# 			Message.CODE.NOTIFICATION,
		# 			Message.CODE.OPEN,
		# 			Message.CODE.KEEPALIVE,
		# 			Message.CODE.UPDATE,
		# 			Message.CODE.ROUTE_REFRESH,
		# 			Message.CODE.OPERATIONAL
		# 		]:
		# 			neighbor.api.set_message(direction,message,process.get('%s-%d' % (direction,message),False))

		# XXX: check that if we have any message, we have parsed/packets
		# XXX: and vice-versa
