from struct import unpack, pack
from exabgp.bgp.message.update.nlri.bgp import RouteDistinguisher
from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.direction import OUT
from exabgp.protocol.family import AFI,SAFI
from exabgp.protocol.ip.address import Address

def _unique ():
	value = 0
	while True:
		yield value
		value += 1

unique = _unique()

class VPLSNLRI (Address):
	def __init__ (self,rd,ve,label_base,block_offset,block_size):
		Address.__init__(self,AFI.l2vpn,SAFI.vpls)
		self.action = OUT.announce
		self.nexthop = None
		self.rd = rd
		self.label_base = label_base
		self.block_offset = block_offset
		self.block_size = block_size
		self.ve = ve
		self.unique = unique.next()

	def index (self):
		return self.pack()

	def pack (self, addpath=None):
		return '%s%s%s%s' % (
			'\x00\x11',  # pack('!H',17)
			self.rd.pack(),
			pack('!HHH',
				self.ve,
				self.block_offset,
				self.block_size
			),
			pack('!L',self.label_base<<12|0x111)[0:3]  # no idea ... deserve a comment ...
		)

	# XXX: FIXME: we need an unique key here.
	# XXX: What can we use as unique key ?
	def json (self):
		content = ','.join([
			self.rd.json(),
			'"endpoint": "%s"' % self.ve,
			'"base": "%s"' % self.block_offset,
			'"offset": "%s"' % self.block_size,
			'"size": "%s"' % self.label_base,
		])
		return '"vpls-%s": { %s }' % (self.unique, content)

	def extensive (self):
		return "vpls%s endpoint %s base %s offset %s size %s %s" % (
			self.rd,
			self.ve,
			self.label_base,
			self.block_offset,
			self.block_size,
			'' if self.nexthop is None else 'next-hop %s' % self.nexthop,
		)

	def __str__ (self):
		return self.extensive()

	@staticmethod
	def unpack (bgp):
		# label is 20bits, stored using 3 bytes, 24 bits
		length, = unpack('!H',bgp[0:2])
		if len(bgp) != length+2:
			raise Notify(3,10,'l2vpn vpls message length is not consistent with encoded data')
		rd = RouteDistinguisher(bgp[2:10])
		ve,block_offset,block_size = unpack('!HHH',bgp[10:16])
		label_base = unpack('!L',bgp[16:19]+'\x00')[0]>>12
		return VPLSNLRI(rd,ve,label_base,block_offset,block_size)
