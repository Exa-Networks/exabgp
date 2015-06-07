#!/usr/bin/env python
# encoding: utf-8
"""
cli.py

Created by Thomas Mangin on 2014-12-22.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""

import sys
import select

from exabgp.dep.cmd2 import cmd

from exabgp.version import version


class Completed (cmd.Cmd):
	# use_rawinput = False
	# prompt = ''

	# doc_header = 'doc_header'
	# misc_header = 'misc_header'
	# undoc_header = 'undoc_header'

	ruler = '-'
	completion = {}

	def __init__ (self, intro=''):
		self.prompt = '%s> ' % intro
		cmd.Cmd.__init__(self)

	def completedefault (self, text, line, begidx, endidx):  # pylint: disable=W0613
		commands = line.split()
		local = self.completion

		for command in commands:
			if command in local:
				local = local[command]
				continue
			break

		return [_ for _ in local.keys() if _.startswith(text)]

	def default (self, line):
		print 'unrecognised syntax: ', line

	def do_EOF (self):
		return True


class SubMenu (Completed):
	def do_exit (self, _):
		return True

	do_x = do_exit


class Attribute (SubMenu):
	chars = ''.join(chr(_) for _ in range(ord('a'),ord('z')+1) + range(ord('0'),ord('9')+1) + [ord ('-')])

	attribute = None

	completion = {
		'origin':  {
			'igp': {
			},
			'egp': {
			},
			'incomplete': {
			},
		},
	}

	def __init__ (self, name):
		self.name = name
		SubMenu.__init__(self,'attribute %s' % name)

	def do_origin (self, line):
		if line in ('igp','egp','incomplete'):
			self.attribute['origin'] = line
		else:
			print 'invalid origin'

	def do_as_path (self, line):
		pass

	# next-hop

	def do_med (self, line):
		if not line.isdigit():
			print 'invalid med, %s is not a number' % line
			return

		med = int(line)
		if 0 > med < 65536:
			print 'invalid med, %s is not a valid number' % line
		self.attribute['origin'] = line

	# local-preference
	# atomic-aggregate
	# aggregator
	# community
	# originator-id
	# cluster-list
	# extended-community
	# psmi
	# aigp

	def do_show (self, _):
		print 'attribute %s ' % self.name + ' '.join('%s %s' % (key,value) for key,value in self.attribute.iteritems())


class Syntax (Completed):
	completion = {
		'announce':  {
			'route':  {
			},
			'l2vpn':  {
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
		'attribute':  {
		},
		'show': {
			'routes':  {
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

	def _update_prompt (self):
		if self._neighbors:
			self.prompt = '\n# neighbor ' + ', '.join(self._neighbors) + '\n> '
		else:
			self.prompt = '\n> '

	#
	# repeat last command
	#

	# last = 'help'

	# def do_last (self, line):
	# 	"Print the input, replacing '$out' with the output of the last shell command"
	# 	# Obviously not robust
	# 	if hasattr(self, 'last_output'):
	# 		print line.replace('$out', self.last_output)

	_neighbors = set()

	def do_neighbor (self, line):
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
		print "neighbor include <ip>:  limit the action to the defined neighbors"
		print "neighbor exclude <ip>:  remove a particular neighbor"
		print "neighbor reset       :  clear the neighbor previous set "

	_attribute = {}

	def do_attribute (self, name):
		if not name:
			self.help_attribute()
			return
		invalid = ''.join([_ for _ in name if _ not in Attribute.chars])
		if invalid:
			print 'invalid character(s) in attribute name: %s' % invalid
			return
		cli = Attribute(name)
		cli.attribute = self._attribute.get(name,{})
		cli.cmdloop()

	def help_attribute (self):
		print 'attribute <name>'

	def do_quit (self, _):
		return True

	do_q = do_quit


class Connection (object):
	def __init__ (self,name):
		self.read = open(name,'r+')
		self.write = open(name,'w+')

	def request (self,command):
		self.write.write(command + '\n')

	def report (self):
		while select.select([self.read],[],[],5):
			print self.read.readline()

	def close (self):
		self.read.close()
		self.write.close()


class ExaBGP (Connection,Syntax):
	def __init__ (self,name='exabgp.cmd'):
		Connection.__init__(self,name)
		Syntax.__init__(self,'')

	def do_show (self, line):
		self.request('show routes')
		self.report()


def main():
	if len(sys.argv) > 1:
		ExaBGP().onecmd(' '.join(sys.argv[1:]))
	else:
		print "ExaBGP %s CLI" % version
		ExaBGP('').cmdloop()


if __name__ == '__main__':
	main()
