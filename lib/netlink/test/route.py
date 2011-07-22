#!/usr/bin/python

from netlink.route import *

netmask = {
	32 : '255.255.255.255',
	31 : '255.255.255.254',
	30 : '255.255.255.252',
	29 : '255.255.255.248',
	28 : '255.255.255.240',
	27 : '255.255.255.224',
	26 : '255.255.255.192',
	25 : '255.255.255.128',
	24 : '255.255.255.0',
	23 : '255.255.254.0',
	22 : '255.255.252.0',
	21 : '255.255.248.0',
	20 : '255.255.240.0',
	19 : '255.255.224.0',
	8 : '255.255.192.0',
	17 : '255.255.128.0',
	16 : '255.255.0.0',
	15 : '255.254.0.0',
	14 : '255.252.0.0',
	13 : '255.248.0.0',
	12 : '255.240.0.0',
	11 : '255.224.0.0',
	10 : '255.192.0.0',
	 9 : '255.128.0.0',
	 8 : '255.0.0.0',
	 7 : '254.0.0.0',
	 6 : '252.0.0.0',
	 5 : '248.0.0.0',
	 4 : '240.0.0.0',
	 3 : '224.0.0.0',
	 2 : '192.0.0.0',
	 1 : '128.0.0.0',
	 0 : '0.0.0.0',
}

def main():
	netlink = NetLinkRoute()

	links = {}
	for ifi in Link(netlink).getLinks():
		links[ifi.index] = ifi.attributes.get(Link.Type.Attribute.IFLA_IFNAME).strip('\0')

	print 'Kernel IP routing table'
	print '%-18s %-18s %-18s %-7s %s' % ('Destination','Genmask','Gateway','Metric','Iface')

	for route in Network(netlink).getRoutes():
		if route.family != socket.AF_INET:
			continue

		if not route.type in (Network.Type.Type.RTN_LOCAL,Network.Type.Type.RTN_UNICAST):
			continue

		if route.src_len == 32:
			continue

		destination = route.attributes.get(Network.Type.Attribute.RTA_DST)
		gateway = route.attributes.get(Network.Type.Attribute.RTA_GATEWAY)

		oif = ord(route.attributes.get(Network.Type.Attribute.RTA_OIF)[0])
		metric = ord(route.attributes.get(Network.Type.Attribute.RTA_PRIORITY,'\0')[0])

		dst = '%s' % socket.inet_ntop(route.family, destination) if destination else ''
		gw  = '%s' % socket.inet_ntop(route.family, gateway) if gateway else '0.0.0.0'
		mask = netmask[route.src_len]
		iface = links[oif]

		print '%-18s %-18s %-18s %-7d %-s' % (dst or '0.0.0.0',mask,gw,metric,iface)
		#if gateway: print route


if __name__ == '__main__':
	main()

