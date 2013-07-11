# encoding: utf-8
"""
cache.py

Created by David Farrar on 2012-12-27.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""


import time

class Cache (dict):
	def __init__ (self, min_items=10, max_items=2000, cache_life=3600):
		dict.__init__(self)
		self.ordered = []
		self.min_items = min_items
		self.max_items = max_items
		self.cache_life = cache_life
		self.last_accessed = int(time.time())

	def cache (self, key, value):
		now = int(time.time())

		if now - self.last_accessed >= self.cache_life:
			self.truncate(self.min_items)

		elif len(self) >= self.max_items:
			self.truncate(self.max_items/2)

		if key not in self:
			self.ordered.append(key)

		self.last_accessed = now
		self[key] = value

		return value

	def retrieve (self, key):
		now = int(time.time())
		res = self[key]

		if now - self.last_accessed >= self.cache_life:
			self.truncate(self.min_items)

			# only update the access time if we modified the cache
			self.last_accessed = now

		return res

	def truncate (self, pos):
		pos = len(self.ordered) - pos
		expiring = self.ordered[:pos]
		self.ordered = self.ordered[pos:]

		for _key in expiring:
			self.pop(_key)

if __name__ == '__main__':
	class klass1:
		def __init__ (self, data):
			pass

	class klass2 (object):
		def __init__ (self, data):
			pass

	class klass3:
		def __init__ (self, data):
			self.a = data[0]
			self.b = data[1]
			self.c = data[2]
			self.d = data[3]
			self.e = data[4]

	class klass4:
		def __init__ (self, data):
			self.a = data[0]
			self.b = data[1]
			self.c = data[2]
			self.d = data[3]
			self.e = data[4]

	class _kparent1:
		def __init__ (self, data):
			self.a = data[0]
			self.b = data[1]

	class _kparent2 (object):
		def __init__ (self, data):
			self.a = data[0]
			self.b = data[1]

	class klass5 (_kparent1):
		def __init__ (self, data):
			_kparent1.__init__(self,data)
			self.c = data[2]
			self.d = data[3]
			self.e = data[4]

	class klass6 (_kparent2):
		def __init__ (self, data):
			_kparent2.__init__(self,data)
			self.c = data[2]
			self.d = data[3]
			self.e = data[4]

	class klass7 (klass6):
		pass

	class klass8 (klass6):
		def __init__ (self, data):
			klass6.__init__(self,data)
			self.s = self.a + self.b + self.c + self.d + self.e

	class klass9 (klass6):
		def __init__ (self, data):
			klass6.__init__(self,data)
			self.s1 = self.a + self.b + self.c + self.d + self.e
			self.s2 = self.b + self.c + self.d + self.e
			self.s3 = self.c + self.d + self.e
			self.s4 = self.d + self.e
			self.s5 = self.a + self.b + self.c + self.d
			self.s6 = self.a + self.b + self.c
			self.s7 = self.a + self.b

	COUNT = 100000
	UNIQUE = 5000

	samples = set()
	chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:"|;<>?,./[]{}-=_+!@£$%^&*()'

	from random import choice

	while len(samples) != UNIQUE:
		samples.add(choice(chars)+choice(chars)+choice(chars)+choice(chars)+choice(chars))

	samples = list(samples)

	for klass in [klass1,klass2,klass3,klass4,klass5,klass6,klass7,klass8,klass9]:
		cache = {}

		start = time.time()
		for val in xrange(COUNT):
			val = val % UNIQUE
			_ = klass(samples[val])
		end = time.time()
		time1 = end-start

		print COUNT,'iterations of',klass.__name__,'with',UNIQUE,'uniques classes'
		print "time instance %d" % time1

		cache = Cache()
		start = time.time()
		for val in xrange(COUNT):
			val = val % UNIQUE

			if val in cache:
				_ = cache.retrieve(val)
			else:
				_ = cache.cache(val, klass(samples[val]))

		end = time.time()
		time2 = end-start

		print "time cached  %d" % time2
		print "speedup %.3f" % (time1/time2)
		print
