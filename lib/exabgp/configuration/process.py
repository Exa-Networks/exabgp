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

# ====================================================================== Process
#

class SectionProcess (Entry):
	syntax = \
	'process <name> {\n' \
	'   run </path/to/command with its args>;  # the command can be quoted\n' \
	'   encoder text|json;\n' \
	'   receive {\n' \
	'     # "message" in notification,open,keepalive,update,refresh,operational\n' \
	'     <message> {\n' \
	'       parsed;       # send parsed BGP data for "message"\n' \
	'       packets;      # send raw BGP message for "message"\n' \
	'       consolidate;  # group parsed and raw information in one JSON object\n' \
	'     }\n' \
	'     neighbor-changes;  # state of peer change (up/down)\n' \
	'   }\n' \
	'   send {\n' \
	'     packets;        # send all generated BGP messages\n' \
	'   }\n' \
	'}\n'

	def __init__ (self):
		self.content = dict()
		self.content['encoder'] = 'text'
		self.legacy = []

	def enter_process (self,tokeniser):
		# we should check that the names are unique if we are using a global struct
		token = tokeniser()
		if token == '{':
			self.content['name'] = 'unnamed'
		else:
			self.content['name'] = token
			self._drop_parenthesis(tokeniser)

	def exit_process (self,tokeniser):
		# implemnet backward compatibility with current format
		pass

	def enter (self,tokeniser):
		self._drop_parenthesis(tokeniser)

	def exit (self,tokeniser):
		pass

	def encoder (self,tokeniser):
		token = tokeniser()
		if token == '}':
			return
		if token not in ('text','json'):
			raise Raised('invalid encoder')
		self.content['encoder'] = token
		self._drop_colon(tokeniser)

	def respawn (self,tokeniser):
		self.content['respawn'] = boolean(tokeniser,False)
		self._drop_colon(tokeniser)

	def run (self,tokeniser):
		command = []

		while True:
			token = tokeniser()
			if token == ';': break
			command.append(token)

		if not command:
			raise Raised('run requires the program to prg as an argument (quoted or unquoted)')

		prg = ' '.join(command)
		if prg[0] != '/':
			if prg.startswith('etc/exabgp'):
				parts = prg.split('/')
				path = [os.environ.get('ETC','etc'),] + parts[2:]
				prg = os.path.join(*path)
			else:
				prg = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(sys.argv[0])),prg))

		if not os.path.exists(prg):
			raise Raised('can not locate the the program "%s"' % prg)

		# XXX: Yep, race conditions are possible, those are sanity checks not security ones ...
		s = os.stat(prg)

		if stat.S_ISDIR(s.st_mode):
			raise Raised('can not execute directories "%s"' % prg)

		if s.st_mode & stat.S_ISUID:
			raise Raised('refusing to run setuid programs "%s"' % prg)

		check = stat.S_IXOTH
		if s.st_uid == os.getuid():
			check |= stat.S_IXUSR
		if s.st_gid == os.getgid():
			check |= stat.S_IXGRP

		if not check & s.st_mode:
			raise Raised('exabgp will not be able to run this program "%s"' % prg)

		self.content['run'] = prg

	# all the action are the same

	def message (self,tokeniser):
		direction = self.location[1]
		message = self.location[2]
		action = self.location[3]
		self.content.setdefault(direction,{}).setdefault(message,[]).append(action)
		self._drop_colon(tokeniser)

	def neighbor_changes (self,tokeniser):
		self.content.setdefault('receive',{}).setdefault('neighbor-changes',[]).append('negotiated')
		self._drop_colon(tokeniser)

	def send_packets (self,tokeniser):
		self.content.setdefault('send',{}).setdefault('all',[]).append('packets')
		self._drop_colon(tokeniser)

	# legacy

	def _receive_neighbor_changes (self,tokeniser):
		self.legacy.append('receive-neighbor-changes')
		self._drop_colon(tokeniser)

	def _receive_notification (self,tokeniser):
		self.legacy.append('receive-notification')
		self._drop_colon(tokeniser)

	def _receive_open (self,tokeniser):
		self.legacy.append('receive-open')
		self._drop_colon(tokeniser)

	def _receive_keepalive (self,tokeniser):
		self.legacy.append('receive-keepalive')
		self._drop_colon(tokeniser)

	def _receive_update (self,tokeniser):
		self.legacy.append('receive-update')
		self._drop_colon(tokeniser)

	def _receive_refresh (self,tokeniser):
		self.legacy.append('receive-refresh')
		self._drop_colon(tokeniser)

	def _receive_operational (self,tokeniser):
		self.legacy.append('receive-operational')
		self._drop_colon(tokeniser)

	def _receive_parsed (self,tokeniser):
		self.legacy.append('receive-parsed')
		self._drop_colon(tokeniser)

	def _receive_packets (self,tokeniser):
		self.legacy.append('receive-packets')
		self._drop_colon(tokeniser)

	def _send_packets (self,tokeniser):
		self.legacy.append('send-packets')
		self._drop_colon(tokeniser)

	def _peer_update (self,tokeniser):
		self.content['receive'].append('receive-parsed')
		self.content['receive'].append('receive-neighbor-changes')
		self.content['receive'].append('receive-udpate')
		self._drop_colon(tokeniser)

	def _parse_routes (self,tokeniser):
		self.content['receive'].append('receive-parsed')
		self.content['receive'].append('receive-neighbor-changes')
		self.content['receive'].append('receive-udpate')
		self._drop_colon(tokeniser)

	def _receive_routes (self,tokeniser):
		self.content['receive'].append('receive-parsed')
		self.content['receive'].append('receive-udpate')
		self.content['receive'].append('receive-refresh')

	def _check_duplicate (self,key):
		if key in self.content:
			raise Raised("")

	@classmethod
	def register (cls,registry,location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter_process')

		registry.register_hook(cls,'action',location+['run'],'run')
		registry.register_hook(cls,'action',location+['encoder'],'encoder')
		registry.register_hook(cls,'action',location+['respawn'],'respawn')

		registry.register_hook(cls,'enter',location+['receive'],'enter')

		for message in ['notification','open','keepalive','update','refresh','operational']:
			registry.register_hook(cls,'enter',location+['receive',message],'enter')
			registry.register_hook(cls,'action',location+['receive',message,'parsed'],'message')
			registry.register_hook(cls,'action',location+['receive',message,'packets'],'message')
			registry.register_hook(cls,'action',location+['receive',message,'consolidate'],'message')
			registry.register_hook(cls,'exit',location+['receive',message],'exit')

		registry.register_hook(cls,'action',location+['receive','neighbor-changes'],'neighbor_changes')

		registry.register_hook(cls,'exit', location+['receive'],'exit')

		registry.register_hook(cls,'enter',location+['send'],'enter')
		registry.register_hook(cls,'action',location+['send','packets'],'send_packets')
		registry.register_hook(cls,'exit',location+['send'],'exit')

		registry.register_hook(cls,'exit',location,'exit_process')

		# legacy

		registry.register_hook(cls,'action',location+['peer-updates'],'_peer_update')
		registry.register_hook(cls,'action',location+['parse-routes'],'_parse_routes')
		registry.register_hook(cls,'action',location+['receive-routes'],'_receive_routes')
		registry.register_hook(cls,'action',location+['receive-packets'],'_receive_packets')
		registry.register_hook(cls,'action',location+['neighbor-changes'],'_receive_neighbor_changes')
		registry.register_hook(cls,'action',location+['receive-updates'],'_receive_update')
		registry.register_hook(cls,'action',location+['receive-refresh'],'_receive_refresh')
		registry.register_hook(cls,'action',location+['receive-operational'],'_receive_operational')



		# name = tokens[0] if len(tokens) >= 1 else 'conf-only-%s' % str(time.time())[-6:]
		# self.process.setdefault(name,{})['neighbor'] = scope[-1]['peer-address'] if 'peer-address' in scope[-1] else '*'

		# run = scope[-1].pop('process-run','')
		# if run:
		# 	if len(tokens) != 1:
		# 		self._error = self._str_process_error
		# 		if self.debug: raise
		# 		return False
		# 	return True
