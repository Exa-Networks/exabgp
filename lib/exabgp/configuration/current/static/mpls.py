from struct import pack

from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.nlri.qualifier import Labels
from exabgp.bgp.message.update.nlri.qualifier import RouteDistinguisher
from exabgp.bgp.message.update.nlri.qualifier import PathInfo

def path_information (self, name, command, tokens):
	try:
		pi = tokens.pop(0)
		if pi.isdigit():
			self.scope.content[-1]['announce'][-1].nlri.path_info = PathInfo(integer=int(pi))
		else:
			self.scope.content[-1]['announce'][-1].nlri.path_info = PathInfo(ip=pi)
		return True
	except ValueError:
		return self.error.set(self.syntax)


def label (self, name, command, tokens):
	labels = []
	label = tokens.pop(0)
	try:
		if label == '[':
			while True:
				try:
					label = tokens.pop(0)
				except IndexError:
					return self.error.set(self.syntax)
				if label == ']':
					break
				labels.append(int(label))
		else:
			labels.append(int(label))
	except ValueError:
		return self.error.set(self.syntax)

	nlri = self.scope.content[-1]['announce'][-1].nlri
	if not nlri.safi.has_label():
		nlri.safi = SAFI(SAFI.nlri_mpls)
	nlri.labels = Labels(labels)
	return True


def rd (self, name, command, tokens, safi):
	try:
		try:
			data = tokens.pop(0)
		except IndexError:
			return self.error.set(self.syntax)

		separator = data.find(':')
		if separator > 0:
			prefix = data[:separator]
			suffix = int(data[separator+1:])

		if '.' in prefix:
			data = [chr(0),chr(1)]
			data.extend([chr(int(_)) for _ in prefix.split('.')])
			data.extend([chr(suffix >> 8),chr(suffix & 0xFF)])
			rd = ''.join(data)
		else:
			number = int(prefix)
			if number < pow(2,16) and suffix < pow(2,32):
				rd = chr(0) + chr(0) + pack('!H',number) + pack('!L',suffix)
			elif number < pow(2,32) and suffix < pow(2,16):
				rd = chr(0) + chr(2) + pack('!L',number) + pack('!H',suffix)
			else:
				raise ValueError('invalid route-distinguisher %s' % data)

		nlri = self.scope.content[-1]['announce'][-1].nlri
		# overwrite nlri-mpls
		nlri.safi = SAFI(safi)
		nlri.rd = RouteDistinguisher(rd)
		return True
	except ValueError:
		return self.error.set(self.syntax)
