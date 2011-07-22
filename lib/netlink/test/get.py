#!/usr/bin/python

from netlink.route import *

def main():
	netlink = NetLinkRoute()

	links = {}
	for ifi in Link(netlink).getLinks():
		links[ifi.index] = ifi

	addresses = {}
	for ifa in Address(netlink).getAddresses():
		addresses.setdefault(ifa.index,[]).append(ifa)

	neighbors = {}
	for neighbor in Neighbor(netlink).getNeighbors():
		neighbors.setdefault(neighbor.index,[]).append(neighbor)

	for index, ifi in links.items():
		hwaddr = '<no addr>'
		if Address.Type.Attribute.IFLA_ADDRESS in ifi.attributes:
			hwaddr = ':'.join(x.encode('hex') for x in ifi.attributes[Address.Type.Attribute.IFLA_ADDRESS])
		print "%d: %s %s" % (ifi.index,ifi.attributes[Address.Type.Attribute.IFLA_IFNAME][:-1],hwaddr)

		for ifa in addresses.get(ifi.index,{}):
			address = ifa.attributes.get(Attributes.Type.IFA_ADDRESS)
			if not address:
				continue

			if ifa.family == socket.AF_INET:
				print '  %s %s' % ('inet ', socket.inet_ntop(ifa.family, address))
			elif ifa.family == socket.AF_INET6:
				print '  %s %s' % ('inet6', socket.inet_ntop(ifa.family, address))
			else:
				print '  %d %s' % (ifa.family, address.encode('hex'))

		for neighbor in neighbors.get(ifi.index,{}):
			if neighbor.state == Neighbor.Type.State.NUD_REACHABLE:
				address = neighbor.attributes.get(Neighbor.Type.Flag.NTF_USE,'\0\0\0\0')
				if ifa.family == socket.AF_INET:
					print '  %s %s' % ('inet ', socket.inet_ntop(neighbor.family, address)),
				elif ifa.family == socket.AF_INET6:
					print '  %s %s' % ('inet ', socket.inet_ntop(neighbor.family, address)),
				else:
					print '  %d %s' % (ifa.family, address.encode('hex'))
				print 'mac',':'.join(_.encode('hex') for _ in neighbor.attributes[Neighbor.Type.State.NUD_REACHABLE])


if __name__ == '__main__':
	main()
