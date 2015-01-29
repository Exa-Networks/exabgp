# encoding: utf-8
"""
process.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2015 Exa Networks. All rights reserved.
"""

from exabgp.configuration.engine.location import Location
from exabgp.configuration.engine.raised import Raised
from exabgp.configuration.engine.section import Section
from exabgp.configuration.engine.parser import boolean

import os
import sys
import stat


# =============================================================== syntax_process

syntax_process = """\
process <name> {
	run </path/to/command with its args>  # the command can be quoted
	encoder text|json
	received {
		# "message" in notification,open,keepalive,update,refresh,operational,all
		<message> [
			parsed          # send parsed BGP data for "message"
			packets         # send raw BGP message for "message"
			consolidated    # group parsed and raw information in one JSON object
		]
		neighbor-changes  # state of peer change (up/down)
		parsed            # send parsed BGP data for all messages
		packets           # send raw BGP message for all messages
		consolidated      # group parsed and raw information for all messages
	}
	sent {
		packets           # send all generated BGP messages
	}
}
"""


# ================================================================ RaisedProcess

class RaisedProcess (Raised):
	syntax = syntax_process


# =============================================================== SectionProcess
#

class SectionProcess (Section):
	syntax = syntax_process
	name = 'process'

	def enter (self, tokeniser):
		Section.enter(self,tokeniser)
		self.content['encoder'] = 'text'

	def encoder (self, tokeniser):
		token = tokeniser()
		if token == '}':
			return
		if token not in ('text','json'):
			raise RaisedProcess(tokeniser,'invalid encoder')
		self.content['encoder'] = token

	def respawn (self, tokeniser):
		self.content['respawn'] = boolean(tokeniser,False)

	def run (self, tokeniser):
		command = tokeniser()

		prg,args = command.split(None,1)
		if prg[0] != '/':
			if prg.startswith('etc/exabgp'):
				parts = prg.split('/')
				path = [os.environ.get('ETC','etc'),] + parts[2:]
				prg = os.path.join(*path)
			else:
				prg = os.path.abspath(os.path.join(os.path.dirname(sys.argv[0]),prg))

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

	def message (self, tokeniser):
		valid_messages = ['notification','open','keepalive','update','refresh','operational']
		valid_options = ['parsed','packets','consolidated']

		def printf (string):
			return (string[::-1].replace(',', ' and'[::-1], 1))[::-1]

		# location is set by our caller
		direction = self.location[-2]  # pylint: disable=E1101
		message = self.location[-1]    # pylint: disable=E1101
		actions = tokeniser()

		for (idx_line,idx_column,line,action) in actions:
			if action not in valid_options:
				raise RaisedProcess(Location(idx_line,idx_column,line),'invalid message option %s, valid options are "%s"' % (action,printf('", "'.join(valid_options))))

			messages = valid_messages if message == 'all' else [message]

			for m in messages:
				section = self.content.setdefault(direction,{}).setdefault(m,[])

				if action in section:
					raise RaisedProcess(Location(idx_line,idx_column,line),'duplicate action (%s) for message %s%s' % (
						action,
						m,
						" using the alis 'all'" if message == 'all' else ''
					))

				if 'consolidated' in section and len(section) > 0:
					raise RaisedProcess(Location(idx_line,idx_column,line),'consolidated can not be used with another keyword')

				section.append(action)

	def neighbor_changes (self, tokeniser):
		self.content.setdefault('received',{})['neighbor-changes'] = True

	# reveived global level

	def received_packets (self, tokeniser):
		for message in ['notification','open','keepalive','update','refresh','operational']:
			self.content.setdefault('received',{}).setdefault(message,[]).append('packets')

	def received_parsed (self, tokeniser):
		for message in ['notification','open','keepalive','update','refresh','operational']:
			self.content.setdefault('received',{}).setdefault(message,[]).append('parsed')

	def received_consolidated (self, tokeniser):
		for message in ['notification','open','keepalive','update','refresh','operational']:
			self.content.setdefault('received',{}).setdefault(message,[]).append('consolidated')

	# sent global level

	def sent_packets (self, tokeniser):
		for message in ['notification','open','keepalive','update','refresh','operational']:
			self.content.setdefault('sent',{}).setdefault(message,[]).append('packets')

	@classmethod
	def register (cls, registry, location):
		registry.register_class(cls)

		registry.register_hook(cls,'enter',location,'enter')

		registry.register_hook(cls,'action',location+['run'],'run')
		registry.register_hook(cls,'action',location+['encoder'],'encoder')
		registry.register_hook(cls,'action',location+['respawn'],'respawn')

		for received in (location+['received'],):

			registry.register_hook(cls,'enter',received,'enter_nameless')

			registry.register_hook(cls,'action',received+['neighbor-changes'],'neighbor_changes')

			for message in ['notification','open','keepalive','update','refresh','operational','all']:
				registry.register_hook(cls,'action',received+[message],'message')

			registry.register_hook(cls,'exit', received,'exit_nameless')

		registry.register_hook(cls,'enter',location+['sent'],'enter_nameless')
		registry.register_hook(cls,'action',location+['sent','packets'],'sent_packets')
		registry.register_hook(cls,'exit',location+['sent'],'exit_nameless')

		registry.register_hook(cls,'exit',location,'exit')
