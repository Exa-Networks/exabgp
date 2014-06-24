

# the replace Fxception, and give line etc.
class Raised (Exception):
	pass

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

class Registry (object):
	_location = ['root']
	_klass = {}
	_handler = {}

	def __init__ (self):
		self.stack = []


	@classmethod
	def register_class (cls,klass):
		print "class %s registered" % klass.__name__
		if not klass in cls._klass:
			cls._klass[klass] = klass(cls)

	@classmethod
	def register (cls,action,position,klass,function):
		instance = cls._klass[klass]
		key = '/'.join(position)
		cls._handler.setdefault(key,{})[action] = getattr(instance,function)
		print "%-20s %-15s %s.%-10s registered" % (key if key else 'root',action,klass.__name__,function)

	def handle (self,tokeniser):
		while True:
			token = tokeniser()
			if not token: break
			#print "[[ %s ]]" % token

			if token == '}':
				key = '/'.join(self.stack)
				function = self._handler.get(key,{}).get('exit',None)
				if function:
					section = 'exit'
					self.stack.pop()
			else:
				key = '/'.join(self.stack + [token,])
				function = self._handler.get(key,{}).get('enter',None)
				if function:
					section = 'enter'
					self.stack.append(token)

			if not function:
				key = '/'.join(self.stack + [token,])
				function = self._handler.get(key,{}).get('action',None)
				if function:
					section = 'action'

			if function is not None:
				print 'hit %s/%s' % (key,section)
				function(self,tokeniser)
				continue

			print 'hit %s/%s' % (key)
			# we need the line and position at this level
			raise Exception('no parser for %s' % token)
