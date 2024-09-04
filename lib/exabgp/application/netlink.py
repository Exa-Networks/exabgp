#!/usr/bin/python

from __future__ import print_function

import sys
import socket

from exabgp.netlink import NetMask
from exabgp.netlink.attributes import Attributes

from exabgp.netlink.route.link import Link
from exabgp.netlink.route.neighbor import Neighbor
from exabgp.netlink.route.address import Address
from exabgp.netlink.route.network import Network


def usage():
    print('%s' % sys.argv[0])
    print('  addr  : show the ip address on the interface')
    print('  route : show the ip routing')


def addresses():
    links = {}
    for ifi in Link.getLinks():
        links[ifi.index] = ifi

    addrs = {}
    for ifa in Address.getAddresses():
        addrs.setdefault(ifa.index, []).append(ifa)

    neighbors = {}
    for neighbor in Neighbor.getNeighbors():
        neighbors.setdefault(neighbor.index, []).append(neighbor)

    for index, ifi in links.items():
        hwaddr = '<no addr>'
        if Address.Type.Attribute.IFLA_ADDRESS in ifi.attributes:
            hwaddr = ':'.join(x.encode('hex') for x in ifi.attributes[Address.Type.Attribute.IFLA_ADDRESS])
        print("%d: %s %s" % (ifi.index, ifi.attributes[Address.Type.Attribute.IFLA_IFNAME][:-1], hwaddr))

        for ifa in addrs.get(ifi.index, {}):
            address = ifa.attributes.get(Attributes.Type.IFA_ADDRESS)
            if not address:
                continue

            if ifa.family == socket.AF_INET:
                print('  %s %s' % ('inet ', socket.inet_ntop(ifa.family, address)))
            elif ifa.family == socket.AF_INET6:
                print('  %s %s' % ('inet6', socket.inet_ntop(ifa.family, address)))
            else:
                print('  %d %s' % (ifa.family, address.encode('hex')))

        for neighbor in neighbors.get(ifi.index, {}):
            if neighbor.state == Neighbor.Type.State.NUD_REACHABLE:
                address = neighbor.attributes.get(Neighbor.Type.Flag.NTF_USE, '\0\0\0\0')
                if ifa.family == socket.AF_INET:
                    print('  %s %s' % ('inet ', socket.inet_ntop(neighbor.family, address)), end=' ')
                elif ifa.family == socket.AF_INET6:
                    print('  %s %s' % ('inet ', socket.inet_ntop(neighbor.family, address)), end=' ')
                else:
                    print('  %d %s' % (ifa.family, address.encode('hex')))
                print('mac', ':'.join(_.encode('hex') for _ in neighbor.attributes[Neighbor.Type.State.NUD_REACHABLE]))


def routes():
    links = {}
    for ifi in Link.getLinks():
        links[ifi.index] = ifi.attributes.get(Link.Type.Attribute.IFLA_IFNAME).strip('\0')

    print('Kernel IP routing table')
    print('%-18s %-18s %-18s %-7s %s' % ('Destination', 'Genmask', 'Gateway', 'Metric', 'Iface'))

    for route in Network.getRoutes():
        if route.family != socket.AF_INET:
            continue

        if route.type not in (Network.Type.Type.RTN_LOCAL, Network.Type.Type.RTN_UNICAST):
            continue

        if route.src_len == 32:
            continue

        destination = route.attributes.get(Network.Type.Attribute.RTA_DST)
        gateway = route.attributes.get(Network.Type.Attribute.RTA_GATEWAY)

        oif = ord(route.attributes.get(Network.Type.Attribute.RTA_OIF)[0])
        metric = ord(route.attributes.get(Network.Type.Attribute.RTA_PRIORITY, '\0')[0])

        dst = '%s' % socket.inet_ntop(route.family, destination) if destination else ''
        gw = '%s' % socket.inet_ntop(route.family, gateway) if gateway else '0.0.0.0'
        mask = NetMask.CIDR[route.src_len]
        iface = links[oif]

        print('%-18s %-18s %-18s %-7d %-s' % (dst or '0.0.0.0', mask, gw, metric, iface))
        # if gateway: print route


def new():
    links = {}
    for ifi in Link.getLinks():
        links[ifi.index] = ifi.attributes.get(Link.Type.Attribute.IFLA_IFNAME).strip('\0')

    for route in Network.newRoute():
        print(route)

        # if route.family != socket.AF_INET:
        # 	continue
        #
        # if route.type not in (Network.Type.Type.RTN_LOCAL,Network.Type.Type.RTN_UNICAST):
        # 	continue
        #
        # if route.src_len == 32:
        # 	continue
        #
        # destination = route.attributes.get(Network.Type.Attribute.RTA_DST)
        # gateway = route.attributes.get(Network.Type.Attribute.RTA_GATEWAY)
        #
        # oif = ord(route.attributes.get(Network.Type.Attribute.RTA_OIF)[0])
        # metric = ord(route.attributes.get(Network.Type.Attribute.RTA_PRIORITY,'\0')[0])
        #
        # dst = '%s' % socket.inet_ntop(route.family, destination) if destination else ''
        # gw  = '%s' % socket.inet_ntop(route.family, gateway) if gateway else '0.0.0.0'
        # mask = NetMask.CIDR[route.src_len]
        # iface = links[oif]
        #
        # print '%-18s %-18s %-18s %-7d %-s' % (dst or '0.0.0.0',mask,gw,metric,iface)


def main():
    if len(sys.argv) < 2:
        usage()
        sys.exit(1)
    if 'addr'.startswith(sys.argv[1]):
        if len(sys.argv) == 2:
            addresses()
            sys.exit(0)
        if sys.argv[2] in 'show':
            addresses()
            sys.exit(0)
    if 'route'.startswith(sys.argv[1]):
        if len(sys.argv) == 2:
            routes()
            sys.exit(0)
        if 'show'.startswith(sys.argv[2]):
            routes()
            sys.exit(0)
        if 'add'.startswith(sys.argv[2]):
            new()
            sys.exit(0)
        if 'delete'.startswith(sys.argv[2]):
            print('adding')

    usage()
    sys.exit(0)


if __name__ == '__main__':
    main()
