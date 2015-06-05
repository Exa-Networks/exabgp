# encoding: utf-8
"""
parse_process.py

Created by Thomas Mangin on 2015-06-05.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import os
import stat
import shlex

from exabgp.configuration.current.basic import Basic


class ParseProcess (Basic):
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


	def __init__ (self, error):
		self.error = error

	def clear (self):
		pass

	def configuration (self, name):
		self._fname = name

	def command (self, scope, command, value):
		scope[-1][command] = True
		return True

	def encoder (self, scope, command, value):
		if value and value[0] in ('text','json'):
			scope[-1][command] = value[0]
			return True

		return self.error.set(self._str_process_error)

	def run (self, scope, command, value):
		line = ' '.join(value).strip()
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
			if self.debug: raise Exception()  # noqa
			return False

		# race conditions are possible, those are sanity checks not security ones ...
		s = os.stat(prg)

		if stat.S_ISDIR(s.st_mode):
			return self.error.set('can not execute directories "%s"' % prg)
			if self.debug: raise Exception()  # noqa
			return False

		if s.st_mode & stat.S_ISUID:
			return self.error.set('refusing to run setuid programs "%s"' % prg)
			if self.debug: raise Exception()  # noqa
			return False

		check = stat.S_IXOTH
		if s.st_uid == os.getuid():
			check |= stat.S_IXUSR
		if s.st_gid == os.getgid():
			check |= stat.S_IXGRP

		if not check & s.st_mode:
			return self.error.set('exabgp will not be able to run this program "%s"' % prg)
			if self.debug: raise Exception()  # noqa
			return False

		if args:
			scope[-1][command] = [prg] + args
		else:
			scope[-1][command] = [prg,]
		return True
