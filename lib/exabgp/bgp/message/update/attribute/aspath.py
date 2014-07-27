# encoding: utf-8
"""
aspath.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
"""

from struct import unpack
from struct import error

from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify

# =================================================================== ASPath (2)
# only 2-4% of duplicated data therefore it is not worth to cache

class ASPath (Attribute):
	AS_SET      = 0x01
	AS_SEQUENCE = 0x02
	ASN4        = False

	ID = Attribute.ID.AS_PATH
	FLAG = Attribute.Flag.TRANSITIVE
	MULTIPLE = False

	__slots__ = ['as_seq','as_set','segments','packed','index','_str','_json']

	def __init__ (self,as_sequence,as_set,index=None):
		self.as_seq = as_sequence
		self.as_set = as_set
		self.segments = ''
		self.packed = {True:'',False:''}
		self.index = index  # the original packed data, use for indexing
		self._str = ''
		self._json = {}

	def __cmp__(self,other):
		if not isinstance(other, self.__class__):
			return -1
		if self.ASN4 != other.ASN4:
			return -1
		if self.as_seq != other.as_seq:
			return -1
		if self.as_set != other.as_set:
			return -1
		return 0

	def _segment (self,seg_type,values,negotiated):
		l = len(values)
		if l:
			if l>255:
				return self._segment(seg_type,values[:255]) + self._segment(seg_type,values[255:])
			return "%s%s%s" % (chr(seg_type),chr(len(values)),''.join([v.pack(negotiated) for v in values]))
		return ""

	def _segments (self,negotiated):
		segments = ''
		if self.as_seq:
			segments = self._segment(self.AS_SEQUENCE,self.as_seq,negotiated)
		if self.as_set:
			segments += self._segment(self.AS_SET,self.as_set,negotiated)
		return segments

	def _pack (self,negotiated,force_asn4=False):
		asn4 = True if force_asn4 else negotiated.asn4
		if not self.packed[asn4]:
			self.packed[asn4] = self._attribute(self._segments(negotiated))
		return self.packed[asn4]

	def pack (self,negotiated):
		# if the peer does not understand ASN4, we need to build a transitive AS4_PATH
		if negotiated.asn4:
			return self._pack(negotiated)

		as2_seq = [_ if not _.asn4() else AS_TRANS for _ in self.as_seq]
		as2_set = [_ if not _.asn4() else AS_TRANS for _ in self.as_set]

		message = ASPath(as2_seq,as2_set)._pack(negotiated)
		if AS_TRANS in as2_seq or AS_TRANS in as2_set:
			message += AS4Path(self.as_seq,self.as_set)._pack(negotiated,True)
		return message

	def __len__ (self):
		raise RuntimeError('it makes no sense to ask for the size of this object')

	def __str__ (self):
		if not self._str:
			lseq = len(self.as_seq)
			lset = len(self.as_set)
			if lseq == 1:
				if not lset:
					string = '%d' % self.as_seq[0]
				else:
					string = '[ %s %s]' % (self.as_seq[0],'( %s ) ' % (' '.join([str(_) for _ in self.as_set])))
			elif lseq > 1 :
				if lset:
					string = '[ %s %s]' % ((' '.join([str(_) for _ in self.as_seq])),'( %s ) ' % (' '.join([str(_) for _ in self.as_set])))
				else:
					string = '[ %s ]' % ' '.join([str(_) for _ in self.as_seq])
			else:  # lseq == 0
				string = '[ ]'
			self._str = string
		return self._str

	def json (self,name):
		if name not in self._json:
			if name == 'as-path':
				if self.as_seq:
					self._json[name] = '[ %s ]' % ', '.join([str(_) for _ in self.as_seq])
				else:
					self._json[name] = '[]'
			elif name == 'as-set':
				if self.as_set:
					self._json[name] = '[ %s ]' % ', '.join([str(_) for _ in self.as_set])
				else:
					self._json[name] = ''
			else:
				# very wrong ,,,,
				return "[ 'bug in ExaBGP\'s code' ]"
		return self._json[name]

	@classmethod
	def __new_aspaths (cls,data,asn4,klass=None):
		as_set = []
		as_seq = []
		backup = data

		unpacker = {
			False : '!H',
			True  : '!L',
		}
		size = {
			False: 2,
			True : 4,
		}
		as_choice = {
			ASPath.AS_SEQUENCE : as_seq,
			ASPath.AS_SET      : as_set,
		}

		upr = unpacker[asn4]
		length = size[asn4]

		try:

			while data:
				stype = ord(data[0])
				slen  = ord(data[1])

				if stype not in (ASPath.AS_SET, ASPath.AS_SEQUENCE):
					raise Notify(3,11,'invalid AS Path type sent %d' % stype)

				end = 2+(slen*length)
				sdata = data[2:end]
				data = data[end:]
				asns = as_choice[stype]

				for i in range(slen):
					asn = unpack(upr,sdata[:length])[0]
					asns.append(ASN(asn))
					sdata = sdata[length:]

		except IndexError:
			raise Notify(3,11,'not enough data to decode AS_PATH or AS4_PATH')
		except error:  # struct
			raise Notify(3,11,'not enough data to decode AS_PATH or AS4_PATH')

		if klass:
			return klass(as_seq,as_set,backup)
		return cls(as_seq,as_set,backup)

	@classmethod
	def unpack (cls,data,negotiated):
		if not data:
			return None  # ASPath.Empty
		return cls.__new_aspaths(data,negotiated.asn4,ASPath)


ASPath.Empty = ASPath([],[])
ASPath.register_attribute()


# ================================================================= AS4Path (17)
#

class AS4Path (ASPath):
	ID = Attribute.ID.AS4_PATH
	FLAG = Attribute.Flag.TRANSITIVE|Attribute.Flag.OPTIONAL
	ASN4 = True

	def pack (self,negotiated=None):
		ASPath.pack(self,True)

	@classmethod
	def unpack (cls,data,negotiated):
		if not data:
			return None  # AS4Path.Empty
		return cls.__new_aspaths(data,True,AS4Path)

AS4Path.Empty = AS4Path([],[])
AS4Path.register_attribute()
