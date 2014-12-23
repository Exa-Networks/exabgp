#!/usr/bin/env python
# encoding: utf-8
"""
cli.py

Created by Thomas Mangin on 2014-12-22.
Copyright (c) 2009-2012 Exa Networks. All rights reserved.
"""

import sys
from exabgp.dep.cmd2 import cmd

from exabgp.version import version

class ExaBGP (cmd.Cmd):

	doc_header = 'doc_header'
	misc_header = 'misc_header'
	undoc_header = 'undoc_header'

	ruler = '-'

	##
	## Completion
	##

	_completion = {
		'announce' : {
			'route' : {
			},
			'l2vpn' : {
			},
		},
		'neighbor': {
			'include': {
			},
			'exclude': {
			},
			'reset': {
			},
			'list': {
			},
		},
		'show': {
			'routes' : {
				'extensive': {
				},
				'minimal': {
				},
			},
		},
		'reload': {
		},
		'restart': {
		},
	}

	def completedefault (self, text, line, begidx, endidx):
		commands = line.split()
		local = self._completion

		for command in commands:
			if command in local:
				local = local[command]
				continue
			break

		return [_ for _ in local.keys() if _.startswith(text)]

	def default (self,line):
		print 'unrecognised syntax: ', line


	##
	## prompt
	##

	# use_rawinput = False
	# prompt = ''
	prompt = '\n> '

	def _update_prompt (self):
		if self._neighbors:
			self.prompt = '\n# neighbor ' + ', '.join(self._neighbors) + '\n> '
		else:
			self.prompt = '\n> '
	##
	## repeat last command
	##

	last = 'help'

	def do_last (self, line):
		"Print the input, replacing '$out' with the output of the last shell command"
		# Obviously not robust
		print line.replace('$out', self.last_output)


	##
	##
	##

	_neighbors = set()

	def do_neighbor (self,line):
		try:
			action,ip = line.split()
		except ValueError:
			if line == 'reset':
				print 'removed neighbors', ', '.join(self._neighbors)
				self._neighbors = set()
				self._update_prompt()
			else:
				print 'invalid syntax'
				self.help_neighbor()
			return

		if action == 'include':
			# check ip is an IP
			# check ip is a known IP
			self._neighbors.add(ip)
			self._update_prompt()
		elif action == 'exclude':
			if ip in self._neighbors:
				self._neighbors.remove(ip)
				print 'neighbor excluded'
				self._update_prompt()
			else:
				print 'invalid neighbor'
		elif action == 'list':
			print 'removed neighbors', ', '.join(self._neighbors)
		else:
			print 'invalid syntax'
			self.help_neighbor()

	def help_neighbor (self):
		print "neighbor include <ip> : limit the action to the defined neighbors"
		print "neighbor exclude <ip> : remove a particular neighbor"
		print "neighbor reset        : clear the neighbor previous set "

	##
	## show
	##

	def do_show (self, line):
		command = line.split()[0]

		if line == 'route':
			return _show_routes(line)

		if not line:
			return help_show()

		print 'not implemented'


	def do_exit (self, line):
		return True

	def do_quit (self, line):
		return True

	do_q = do_quit


	# def do_prompt (self, line):
	# 	self.prompt = line + ' '

	def preloop (self):
		pass

	def precmd (self, line):
		self.last = line
		return cmd.Cmd.precmd(self,line)

	def postcmd (self, stop, line):
		return cmd.Cmd.postcmd(self, stop, line)

	def postloop (self):
		pass

	def parseline (self, line):
		ret = cmd.Cmd.parseline(self, line)
		return ret

	def cmdloop (self, intro=''):
		return cmd.Cmd.cmdloop(self, intro)

	def onecmd (self, s):
		return cmd.Cmd.onecmd(self, s)

	def emptyline (self):
		return cmd.Cmd.emptyline(self)

	def default (self, line):
		return cmd.Cmd.default(self, line)

if __name__ == '__main__':
	if len(sys.argv) > 1:
		ExaBGP().onecmd(' '.join(sys.argv[1:]))
	else:
		ExaBGP().cmdloop("""\
ExaBGP %s CLI""" % version)
