# encoding: utf-8
"""
vpn.py

Created by Orange.
Copyright (c) 2014, Orange. All rights reserved.
"""

from struct import pack,unpack
import socket

from exabgp.structure.ip import _Prefix
from exabgp.structure.ip import _bgp as len_to_bytes
from exabgp.structure.ip import Inet
from exabgp.protocol.family import AFI,SAFI


class LabelStackEntry(object):

	MAX_LABEL = 2**20-1

	def __init__(self,value,bottomOfStack=False):
		self.labelValue = int(value)
		if int(value) > LabelStackEntry.MAX_LABEL :
			raise Exception("Label is beyond the limit (%d > %d)" % (int(value),LabelStackEntry.MAX_LABEL))
		self.bottomOfStack = bottomOfStack
		self.withdraw = (self.labelValue == 0)

	def __str__ (self):
		return "%s%s" % (str(self.labelValue), "-B" if self.bottomOfStack else "")

	def __repr__ (self):
		return str(self)

	def __len__(self):
		return 3

	def pack (self):
		number = (self.labelValue << 4) + self.bottomOfStack
		return pack('!L',number)[1:4]

	def __cmp__(self,other):
		if (isinstance(other,LabelStackEntry) and
			self.labelValue == other.labelValue and
			self.bottomOfStack == other.bottomOfStack
			):
			return 0
		else:
			return -1

	@staticmethod
	def unpack(data):
		# data is supposed to be 3 bytes, the last 4 bits including the TC code and BOS bit
		if len(data)!=3:
			raise Exception("MPLS Label stack entry cannot be created from %d bytes (must be 3)" % len(data))

		number = unpack('!L', "\0"+data) [0]
		value = number >> 4
		# tc =   #FIXME: not done yet
		bos = bool(number & 1)

		return LabelStackEntry(value,bos)

NO_LABEL=LabelStackEntry(0)

def unpackLabelStack(data):
	# returns the amount of bytes consumed
	initial_length = len(data)
	stack=[]
	while(len(data)>3):
		stack.append(LabelStackEntry.unpack(data[0:3]))
		data = data[3:]
		if stack[-1].bottomOfStack or stack[-1].withdraw : break

	return stack, initial_length - len(data)

class RouteDistinguisher (object):

	TYPE_AS2_LOC = 0  # Format AS(2bytes):AN(4bytes)
	TYPE_IP_LOC  = 1  # Format IP address:AN(2bytes)
	TYPE_AS4_LOC = 2  # Format AS(4bytes):AN(2bytes)

	def __init__(self,rdtype,asn,ip,loc):
		self.type = rdtype

		if rdtype in (self.TYPE_AS2_LOC, self.TYPE_AS4_LOC):
			self.asn = asn
			self.loc = loc
			self.ip = ""
		elif rdtype == self.TYPE_IP_LOC:
			self.ip = ip
			self.loc = loc
			self.asn = 0
		else:
			raise Exception("unsupported rd rdtype")

	def __str__ (self):
		if self.type in(self.TYPE_AS2_LOC,self.TYPE_AS4_LOC):
			return "%s:%s" % (self.asn, self.loc)
		elif self.type == self.TYPE_IP_LOC:
			return "%s:%s" % (self.ip, self.loc)
		else:
			raise "BROKEN RD / UNKNOWN TYPE"

	def __len__(self):
		return 8

	def __repr__ (self):
		return str(self)

	def __cmp__(self,other):
		if (isinstance(other,RouteDistinguisher)
			and self.type == other.type and
			self.asn == other.asn and
			self.ip == other.ip and
			self.loc == other.loc):
			return 0
		else:
			return -1

	def pack(self):
		if self.type == self.TYPE_AS2_LOC:
			return pack('!HHL', self.type, self.asn, self.loc)
		elif self.type == self.TYPE_IP_LOC:
			encoded_ip = socket.inet_pton(socket.AF_INET, self.ip)
			return pack('!H4sH', self.type, encoded_ip, self.loc)
		elif self.type == self.TYPE_AS4_LOC:
			return pack('!HLH', self.type, self.asn, self.loc)
		else:
			raise Exception("Incorrect RD type %d // not supposed to happen !!" % self.type)

	@staticmethod
	def unpack(data):
		rdtype = unpack('!H', data[0:2])[0]
		data = data[2:]

		if rdtype == RouteDistinguisher.TYPE_AS2_LOC:
			asn,loc = unpack("!HL",data)
			ip = None
		elif rdtype == RouteDistinguisher.TYPE_IP_LOC:
			ip = socket.inet_ntop(socket.AF_INET, data[0:4])
			loc = unpack('!H', data[4:])[0]
			asn = None
		elif rdtype == RouteDistinguisher.TYPE_AS4_LOC:
			asn,loc = unpack("!LH",data)
			ip = None
		else:
			raise Exception("unsupported rd rdtype: %d" % rdtype)

		return RouteDistinguisher(rdtype,asn,ip,loc)


class VPNLabelledPrefix(object):

	def __init__(self,afi,safi,prefix,rd,labelStack):
		self.afi = AFI(afi)
		self.safi = SAFI(safi)
		self.rd = rd
		self.labelStack = labelStack  # an array of LabelStackEntry's
		if type(labelStack) != list or len(labelStack)==0:
			raise Exception("Labelstack has to be a non-empty array")
		self.prefix = prefix

	def __str__ (self):
		return "RD:%s %s MPLS:[%s]" % (self.rd, self.prefix, "|".join(map(str,self.labelStack)))

	def __repr__(self):
		return self.__str__()

	def pack (self):
		bitlen = (len(self)-len(self.prefix))*8 + self.prefix.mask

		stack = ''.join(map(lambda x:x.pack(), self.labelStack))

		return chr(bitlen) + stack + self.rd.pack() + self.prefix.pack()[1:]

	def __len__ (self):
		# returns the length in bits!
		return len(self.labelStack) * len(self.labelStack[0]) + len(self.rd) + len(self.prefix)


	def __cmp__(self,other):
		#
		# Note well: we need an advertise and a withdraw for the same RD:prefix to result in
		# objects that are equal for Python, this is why the test below does not look at self.labelstack
		#
		if (isinstance(other,VPNLabelledPrefix) and
			self.rd == other.rd and
			self.prefix == other.prefix):
			return 0
		else:
			return -1

	def __hash__(self):  # XXX: FIXME: improve for better performance?
		return hash("%s:%s" % (self.rd,self.prefix))

	@staticmethod
	def unpack(afi,safi,data):

		# prefix len
		bitlen = ord(data[0])
		data=data[1:]
		initial_len = len(data)

		# data is supposed to be: label stack, rd, prefix
		labelStack,consummed = unpackLabelStack(data)
		data=data[consummed:]

		rd = RouteDistinguisher.unpack(data[:8])
		data=data[8:]

		prefix_len_in_bits = bitlen - (initial_len - len(data))*8
		last_byte = len_to_bytes[prefix_len_in_bits]
		prefix = _Prefix(afi, data[0:last_byte] + '\0'*(Inet._length[afi]-last_byte) , prefix_len_in_bits )

		return VPNLabelledPrefix(afi,safi,prefix,rd,labelStack)
