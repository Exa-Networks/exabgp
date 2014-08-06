# encoding: utf-8
"""
process.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.registry import Raised
from exabgp.configuration.engine.registry import Entry
from exabgp.configuration.engine.parser import boolean

import os
import sys
import stat


# =============================================================== process_syntax

process_syntax = \
'process <name> {\n' \
'   run </path/to/command with its args>  # the command can be quoted\n' \
'   encoder text|json\n' \
'   received {\n' \
'     # "message" in notification,open,keepalive,update,refresh,operational,all\n' \
'     <message> [\n' \
'       parsed          # send parsed BGP data for "message"\n' \
'       packets         # send raw BGP message for "message"\n' \
'       consolidated    # group parsed and raw information in one JSON object\n' \
'     ]\n' \
'   }\n' \
'   sent {\n' \
'     packets           # send all generated BGP messages\n' \
'   }\n' \
'}\n'


# ================================================================ RaisedProcess

class RaisedProcess (Raised):
	syntax = process_syntax


# =============================================================== SectionProcess
#

class SectionProcess (Entry):
	syntax = process_syntax
	name = 'process'

	def enter_process (self,tokeniser):
		self.content = self.create_section(self.name,tokeniser)
		self.content['encoder'] = 'text'

	def exit_process (self,tokeniser):
		pass

	def encoder (self,tokeniser):
		token = tokeniser()
		if token == '}':
			return
		if token not in ('text','json'):
			raise RaisedProcess(tokeniser,'invalid encoder')
		self.content['encoder'] = token

	def respawn (self,tokeniser):
		self.content['respawn'] = boolean(tokeniser,False)

	def run (self,tokeniser):
		command = tokeniser()

		prg,args = command.split(None,1)
		if prg[0] != '/':
			if prg.startswith('etc/exabgp'):
				parts = prg.split('/')
				path = [os.environ.get('ETC','etc'),] + parts[2:]
				prg = os.path.join(*path)
			else:
				prg = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(sys.argv[0])),prg))

		if not os.path.exists(prg):
			raise RaisedProcess(tokeniser,'can not locate the the program "%s"' % prg)

		# XXX: Yep, race conditions are possible, those are sanity checks not security ones ...
		s = os.stat(prg)

		if stat.S_ISDIR(s.st_mode):
			raise RaisedProcess(tokeniser,'can not execute directories "%s"' % prg)

		if s.st_mode & stat.S_ISUID:
			raise RaisedProcess(tokeniser,'refusing to run setuid programs "%s"' % prg)

		check = stat.S_IXOTH
		if s.st_uid == os.getuid():
			check |= stat.S_IXUSR
		if s.st_gid == os.getgid():
			check |= stat.S_IXGRP

		if not check & s.st_mode:
			raise RaisedProcess(tokeniser,'exabgp will not be able to run this program "%s"' % prg)

		self.content['run'] = '%s %s' % (prg,args)

	# all the action are the same

	def message (self,tokeniser):
		direction = self.location[-3]
		message = self.location[-2]
		action = self.location[-1]
		self.content.setdefault(direction,{}).setdefault(message,[]).append(action)

	def neighbor_changes (self,tokeniser):
		self.content.setdefault('received',{}).setdefault('neighbor-changes',[]).append('negotiated')

	# reveived global level

	def received_packets (self,tokeniser):
		for message in ['notification','open','keepalive','update','refresh','operational']:
			self.content.setdefault('received',{}).setdefault(message,[]).append('packets')

	def received_parsed (self,tokeniser):
		for message in ['notification','open','keepalive','update','refresh','operational']:
			self.content.setdefault('received',{}).setdefault(message,[]).append('parsed')

	def received_consolidated (self,tokeniser):
		for message in ['notification','open','keepalive','update','refresh','operational']:
			self.content.setdefault('received',{}).setdefault(message,[]).append('consolidated')

	# sent global level

	def sent_packets (self,tokeniser):
		for message in ['notification','open','keepalive','update','refresh','operational']:
			self.content.setdefault('sent',{}).setdefault(message,[]).append('packets')

	@classmethod
	def register (cls,registry,location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter_process')

		registry.register_hook(cls,'action',location+['run'],'run')
		registry.register_hook(cls,'action',location+['encoder'],'encoder')
		registry.register_hook(cls,'action',location+['respawn'],'respawn')

		for received in (location+['received'],):

			registry.register_hook(cls,'enter',received,'unamed_enter')

			registry.register_hook(cls,'action',received+['neighbor-changes'],'neighbor_changes')

			for message in ['notification','open','keepalive','update','refresh','operational']:
				registry.register_hook(cls,'enter',received+[message],'unamed_enter')
				registry.register_hook(cls,'action',received+[message,'parsed'],'message')
				registry.register_hook(cls,'action',received+[message,'packets'],'message')
				registry.register_hook(cls,'action',received+[message,'consolidated'],'message')
				registry.register_hook(cls,'exit',received+[message],'unamed_exit')

			message = 'all'
			registry.register_hook(cls,'enter',received+[message],'unamed_enter')
			registry.register_hook(cls,'action',received+[message,'parsed'],'message')
			registry.register_hook(cls,'action',received+[message,'packets'],'message')
			registry.register_hook(cls,'action',received+[message,'consolidated'],'message')
			registry.register_hook(cls,'exit',received+[message],'unamed_exit')

			registry.register_hook(cls,'exit', received,'unamed_exit')

		registry.register_hook(cls,'enter',location+['sent'],'unamed_enter')
		registry.register_hook(cls,'action',location+['sent','packets'],'sent_packets')
		registry.register_hook(cls,'exit',location+['sent'],'unamed_exit')

		registry.register_hook(cls,'exit',location,'exit_process')

		# name = tokens[0] if len(tokens) >= 1 else 'conf-only-%s' % str(time.time())[-6:]
		# self.process.setdefault(name,{})['neighbor'] = scope[-1]['peer-address'] if 'peer-address' in scope[-1] else '*'

		# run = scope[-1].pop('process-run','')
		# if run:
		# 	if len(tokens) != 1:
		# 		self._error = self._str_process_error
		# 		if self.debug: raise
		# 		return False
		# 	return True
