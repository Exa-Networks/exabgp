from struct import unpack, pack
from exabgp.bgp.message.update.nlri.bgp import RouteDistinguisher
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.direction import OUT
from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address


class L2vpn(object):
	def __init__(self, rd = None, label_base = None, block_offset = None,
				 block_size = None, ve = None):
		self.rd = rd
		self.label_base = label_base
		self.block_offset = block_offset
		self.block_size = block_size
		self.ve = ve
	
	@classmethod
	def parse_bgp(cls,bgp):
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

	def nlri(self):
		return "l2vpn:ve:%s:base:%s:offset:%s:size:%s:%s"%(self.ve,
							 self.label_base,self.block_offset,
							 self.block_size, self.rd,)
	
	def __call__(self):
		return self.nlri()

	def __str__(self):
		return self.nlri()

class L2vpnNLRI(Address):
	def __init__(self, bgp, action, nexthop, parse=True):
		Address.__init__(self,AFI.l2vpn,SAFI.vpls)
		self.action = action
		self.nexthop = nexthop
		if parse == True:
			self.nlri = L2vpn.parse_bgp(bgp)
		else:
			self.nlri = L2vpn()
	
	@classmethod
	def blank_init_out(cls):
		return cls(None,OUT.announce,None,False)

	def index(self):
		return self.pack()


	def pack(self, addpath=None):
		msg_len = pack('!H',17)
		rd = self.rd.pack()
		ve = pack('!H',self.nlri.ve)
		block_offset = pack('!H',self.nlri.block_offset)
		block_size = pack('!H',self.nlri.block_size)
		label_base = pack('!I',self.nlri.label_base<<12)[0:3]
		data = msg_len+rd+ve+block_offset+block_size+label_base
		return data
