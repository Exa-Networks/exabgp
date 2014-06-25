# encoding: utf-8
"""
registry.py

Created by Thomas Mangin on 2014-06-22.
Copyright (c) 2014-2014 Exa Networks. All rights reserved.
"""

# the replace Fxception, and give line etc.
class Raised (Exception):
	pass

class Entry (object):
	_klass = {}
	_handler = {}

	@classmethod
	def register_class (cls):
		print "class %s registered" % cls.__name__
		if not cls in cls._klass:
			cls._klass[cls] = cls()

	@classmethod
	def register_hook (cls,action,position,function):
		key = '/'.join(position)
		cls._handler.setdefault(key,{})[action] = getattr(cls,function)
		print "%-35s %-7s %s.%-20s registered" % (key if key else 'root',action,cls.__name__,function)


class Registry (object):
	_location = ['root']

	def __init__ (self):
		self.stack = []

	def handle (self,tokeniser):
		while True:
			token = tokeniser()
			if not token: break
			#print "[[ %s ]]" % token

			if token == '}':
				key = '/'.join(self.stack)
				function = Entry._handler.get(key,{}).get('exit',None)
				if function:
					section = 'exit'
					self.stack.pop()
			else:
				key = '/'.join(self.stack + [token,])
				function = Entry._handler.get(key,{}).get('enter',None)
				if function:
					section = 'enter'
					self.stack.append(token)

			if not function:
				key = '/'.join(self.stack + [token,])
				function = Entry._handler.get(key,{}).get('action',None)
				if function:
					section = 'action'

			if function is not None:
				print 'hit %s/%s' % (key,section)
				instance = Entry._klass.setdefault(function.im_class,function.im_class())
				function(instance,tokeniser)
				continue

			print 'hit %s/%s' % (key)
			# we need the line and position at this level
			raise Exception('no parser for %s' % token)


class Data (object):
	def boolean (self,tokeniser,default):
		boolean = tokeniser()
		if boolean == ';':
			return default
		if boolean in ('true','enable','enabled'):
			value = True
		elif boolean in ('false','disable','disabled'):
			value = False
		elif boolean in ('unset',):
			value = None
		else:
			raise Exception("")

		if tokeniser() != ';':
			raise Exception("")

		return value

	def _drop_colon (self,tokeniser):
		if tokeniser() != ';':
			raise Raised('missing semi-colon')
