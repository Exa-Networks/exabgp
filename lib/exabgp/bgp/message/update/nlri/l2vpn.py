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
	def __init__ (self,rd=None,ve=None,label_base=None,block_offset=None,block_size=None):
		self.rd = rd
		self.label_base = label_base
		self.block_offset = block_offset
		self.block_size = block_size
		self.ve = ve

	@staticmethod
	def unpack (bgp):
		# label is 20bits, stored using 3 bytes, 24 bits
		length, = unpack('!H',bgp[0:2])
		if len(bgp) != length+2:
			raise Notify(3,10,'l2vpn vpls message length is not consistent with encoded data')
		rd = RouteDistinguisher(bgp[2:10])
		ve,block_offset,block_size = unpack('!HHH',bgp[10:16])
		label_base = unpack('!L',bgp[16:19]+'\x00')[0]>>12
		return L2VPN(rd,ve,label_base,block_offset,block_size)

	def extensive (self):
		return "vpls %s endpoint %s base %s offset %s size %s" % (
			self.rd,
			self.ve,
			self.label_base,
			self.block_offset,
			self.block_size,
		)

	def __call__ (self):
		return self.extensive()

	def __str__ (self):
		return self.extensive()


class L2VPNNLRI (Address):
	def __init__ (self,bgp=None,action=OUT.announce,nexthop=None):
		Address.__init__(self,AFI.l2vpn,SAFI.vpls)
		self.action = action
		self.nexthop = nexthop
		self.nlri = L2VPN.unpack(bgp) if bgp else L2VPN()

	def index (self):
		return self.pack()

	def pack (self, addpath=None):
		return '%s%s%s%s' % (
			'\x00\x11',  # pack('!H',17)
			self.rd.pack(),
			pack('!HHH',
				self.nlri.ve,
				self.nlri.block_offset,
				self.nlri.block_size
			),
			pack('!L',self.nlri.label_base<<12|0x111)[0:3]  # no idea ... deserve a comment ...
		)
