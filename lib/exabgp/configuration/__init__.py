# encoding: utf-8
"""
parser.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

if __name__ == '__main__':
	from exabgp.configuration.engine.reader import Reader
	from exabgp.configuration.engine.tokeniser import Tokeniser
	from exabgp.configuration.engine.registry import Registry

	from exabgp.configuration.neighbor.family import SectionFamily
	from exabgp.configuration.neighbor.capability import SectionCapability
	from exabgp.configuration.process import SectionProcess

	class Parser (object):
		def __init__ (self,fname,text=False):
			#self.debug = environment.settings().debug.configuration
			#self.logger = Logger()
			self._text = text
			self._fname = fname

		def reload (self):
			registry = Registry()
			registry.register(SectionFamily,['family'])
			registry.register(SectionCapability,['capability'])
			registry.register(SectionProcess,['process'])

			with Reader(self._fname) as r:
				tokeniser = Tokeniser(r)
				registry.handle(tokeniser)

			return registry

	p = Parser('/Users/thomas/source/git/exabgp/master/dev/test-new-config.txt')
	registry = p.reload()

	for klass in registry._klass:
		print klass, registry._klass[klass].content
