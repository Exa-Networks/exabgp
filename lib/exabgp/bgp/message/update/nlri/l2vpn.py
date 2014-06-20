from struct import unpack, pack
from exabgp.bgp.message.update.nlri.bgp import RouteDistinguisher
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.direction import OUT
from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address


class L2VPN (object):
	'''
	all parameters are mandatory, however want to be able to init w/o knowing everything
	in advance. actual check that all of them are configured in configuration.file
	_check_l2vpn_route() and checkValues()
	'''
	def __init__ (self,rd=None,label_base=None,block_offset=None,block_size=None,ve=None):
		self.rd = rd
		self.label_base = label_base
		self.block_offset = block_offset
		self.block_size = block_size
		self.ve = ve


	def setLabelBase (self,data):
		_str_bad_label = "you tried to config invalid label"
		number = int(data)
		if self.block_size:
			block_size = self.block_size
		else:
			block_size = 0
		if number < 0 or number > (0xFFFFF - block_size):  # 20 bits 5 bytes
			raise ValueError(_str_bad_label)
		self.label_base = number
		return True

	def setBlockOffset (self,data):
		_str_bad_offset = "you tried to config invalid block-offset"
		number = int(data)
		if number < 0 or number > 0xFFFF:
			raise ValueError(_str_bad_offset)
		self.block_offset = number
		return True

	def setBlockSize (self,data):
		_str_bad_size = "you tried to config invalid block size"
		number = int(data)
		if number < 0 or number > 0xFFFF:
			raise ValueError(_str_bad_size)
		self.block_size = number
		return True

	def setVE (self,data):
		_str_bad_size = "you tried to config invalid ve id"
		number = int(data)
		if number < 0 or number > 0xFFFF:
			raise ValueError(_str_bad_size)
		self.ve = number
		return True

	def checkValues (self):
		if (self.ve and self.label_base and self.block_offset
			and self.block_size):
			return True
		return False

	@staticmethod
	def unpack (bgp):
		msg_len = unpack('!H',bgp[0:2])[0]
		if msg_len+2 != len(bgp):
			raise Notify(3,10,'invalid length of l2vpn msg')
		rd = RouteDistinguisher(bgp[2:10])
		ve = unpack('!H',bgp[10:12])[0]
		block_offset = unpack('!H',bgp[12:14])[0]
		block_size = unpack('!H',bgp[14:16])[0]
		"""
		label_base cant be more than 20bit (label's size); I = 32bit
		anyway, this is somehow hacking; but i can parse real msg with it
		"""
		label_base = unpack('!I',bgp[16:19]+'\x00')[0]>>12
		return cls(rd,label_base,block_offset,block_size,ve)

	def pprint (self):
		return "vpls endpoint %s base %s offset %s size %s %s" % (
			self.ve,
			self.label_base,
			self.block_offset,
			self.block_size,
			self.rd
		)

	def __call__ (self):
		return self.pprint()

	def __str__ (self):
		return self.pprint()


class L2VPNNLRI (Address):
	def __init__ (self,bgp=None,action=OUT.announce,nexthop=None):
		Address.__init__(self,AFI.l2vpn,SAFI.vpls)
		self.action = action
		self.nexthop = nexthop
		self.nlri = L2VPN.unpack(bgp) if bgp else L2VPN()

	def index (self):
		return self.pack()

	def pack (self, addpath=None):
		msg_len = pack('!H',17)
		rd = self.rd.pack()
		ve = pack('!H',self.nlri.ve)
		block_offset = pack('!H',self.nlri.block_offset)
		block_size = pack('!H',self.nlri.block_size)
		label_base = pack('!I',(self.nlri.label_base<<12)|0x111)[0:3]
		data = msg_len+rd+ve+block_offset+block_size+label_base
		return data
