# encoding: utf-8
"""
route.py

Created by Thomas Mangin on 2012-07-08.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

# from exabgp.protocol.ip.address import Address
# from exabgp.bgp.message.update.attributes import Attributes

# class Route (object):
# 	def __init__ (self,nlri,action):
# 		self.action = action  # announce, announced, withdraw or withdrawn
# 		self.nlri = nlri
# 		self.attributes = Attributes()

# 	def __str__ (self):
# 		return "%s route %s%s" % (self.action,str(self.nlri),str(self.attributes))

# 	def __hash__(self):
# 		return hash(str(self))

# 	def __eq__(self, other):
# 		return str(self) == str(other)

# 	def __ne__ (self,other):
# 		return not self.__eq__(other)

# 	def extensive (self):
# 		return "%s %s%s" % (str(Address(self.nlri.afi,self.nlri.safi)),str(self.nlri),str(self.attributes))

# 	def index (self):
# 		return self.nlri.pack(True)+self.nlri.rd.rd
