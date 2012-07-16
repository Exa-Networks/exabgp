#!/usr/bin/python

# based on netlink.py at ....
# https://gforge.inria.fr/scm/viewvc.php/canso/trunk/tools/netlink.py?view=markup&revision=1360&root=mehani&pathrev=1360
# http://www.linuxjournal.com/article/7356?page=0,1
# http://smacked.org/docs/netlink.pdf
# RFC 3549

import socket
from struct import pack,unpack,calcsize
from collections import namedtuple

class GlobalError (Exception):
	pass

class NetLinkError (GlobalError):
	pass

class _Sequence (object):
	instance = None

	def __init__ (self):
		self._next = 0

	def next (self):
		# XXX: should protect this code with a Mutex
		self._next += 1
		return self._next

def Sequence ():
	# XXX: should protect this code with a Mutex
	if not _Sequence.instance:
		_Sequence.instance = _Sequence()
	return _Sequence.instance

class NetLinkRoute (object):
	_IGNORE_SEQ_FAULTS = True

	NETLINK_ROUTE = 0

	format = namedtuple('Message','type flags seq pid data')
	pid = 0 # os.getpid()

	class Header (object):
		## linux/netlink.h
		PACK  = 'IHHII'
		LEN = calcsize(PACK)

	class Command (object):
		NLMSG_NOOP    = 0x01
		NLMSG_ERROR   = 0x02
		NLMSG_DONE    = 0x03
		NLMSG_OVERRUN = 0x04

	class Flags (object):
		NLM_F_REQUEST = 0x01 # It is query message.
		NLM_F_MULTI   = 0x02 # Multipart message, terminated by NLMSG_DONE
		NLM_F_ACK     = 0x04 # Reply with ack, with zero or error code
		NLM_F_ECHO    = 0x08 # Echo this query

		# Modifiers to GET query
		NLM_F_ROOT   = 0x100 # specify tree root
		NLM_F_MATCH  = 0x200 # return all matching
		NLM_F_DUMP   = NLM_F_ROOT | NLM_F_MATCH
		NLM_F_ATOMIC = 0x400 # atomic GET

		# Modifiers to NEW query
		NLM_F_REPLACE = 0x100 # Override existing
		NLM_F_EXCL    = 0x200 # Do not touch, if it exists
		NLM_F_CREATE  = 0x400 # Create, if it does not exist
		NLM_F_APPEND  = 0x800 # Add to end of list

	errors = {
		Command.NLMSG_ERROR : 'netlink error',
		Command.NLMSG_OVERRUN : 'netlink overrun',
	}

	def __init__ (self):
		self.socket = socket.socket(socket.AF_NETLINK, socket.SOCK_RAW, self.NETLINK_ROUTE)
		self.sequence = Sequence()

	def encode (self, type, seq, flags, body, attributes):
		attrs = Attributes().encode(attributes)
		length = self.Header.LEN + len(attrs) + len(body)
		return pack(self.Header.PACK, length, type, flags, seq, self.pid) + body + attrs

	def decode (self,data):
		while data:
			length, ntype, flags, seq, pid = unpack(self.Header.PACK,data[:self.Header.LEN])
			if len(data) < length:
				raise NetLinkError("Buffer underrun")
			yield self.format(ntype, flags, seq, pid, data[self.Header.LEN:length])
			data = data[length:]

	def query (self, type, family=socket.AF_UNSPEC):
		sequence = self.sequence.next()

		message = self.encode(
			type,
			sequence,
			self.Flags.NLM_F_REQUEST | self.Flags.NLM_F_DUMP,
            		pack('Bxxx', family),
			{}
		)

		self.socket.send(message)

		while True:
			data = self.socket.recv(640000)
			for mtype, flags, seq, pid, data in self.decode(data):
				if seq != sequence:
					if self._IGNORE_SEQ_FAULTS:
						continue
					raise NetLinkError("netlink seq mismatch")
            			if mtype == self.Command.NLMSG_DONE:
					raise StopIteration()
				elif type in self.errors:
					raise NetLinkError(self.errors[mtype])
				else:
					yield data

	def change (self, type, family=socket.AF_UNSPEC):
		sequence = self.sequence.next()

		message = self.encode(
			type,
			self.Flags.NLM_F_REQUEST | self.Flags.NLM_F_CREATE,
            		pack('Bxxx', family)
		)

		self.socket.send(message)

		while True:
			data = self.socket.recv(640000)
			for mtype, flags, seq, pid, data in self.decode(data):
				if seq != sequence:
					if self._IGNORE_SEQ_FAULTS:
						continue
					raise NetLinkError("netlink seq mismatch")
            			if mtype == self.Command.NLMSG_DONE:
					raise StopIteration()
				elif type in self.errors:
					raise NetLinkError(self.errors[mtype])
				else:
					yield data


class AttributesError (GlobalError):
	pass

class Attributes (object):
	class Header (object):
		PACK = 'HH'
		LEN = calcsize(PACK)

	class Type (object):
		IFA_UNSPEC     = 0x00
		IFA_ADDRESS    = 0x01
		IFA_LOCAL      = 0x02
		IFA_LABEL      = 0x03
		IFA_BROADCAST  = 0x04
		IFA_ANYCAST    = 0x05
		IFA_CACHEINFO  = 0x06
		IFA_MULTICAST  = 0x07

	def pad (self,len,to=4):
		return (len+to-1) & ~(to-1)

	def decode (self,data):
		while data:
			length, atype, = unpack(self.Header.PACK,data[:self.Header.LEN])
			if len(data) < length:
				raise AttributesError("Buffer underrun %d < %d" % (len(data),length))
			payload = data[self.Header.LEN:length]
			yield atype, payload
			data = data[int((length + 3) / 4) * 4:]

	def _encode (self,atype,payload):
		len = self.Header.LEN + len(payload)
		raw = pack(self.Header.PACK,len,atype) + payload
		pad = self.pad(len) - len(raw)
		if pad: raw += '\0'*pad
		return raw

	def encode (self,attributes):
		return ''.join([self._encode(k,v) for (k,v) in attributes.items()])

class _InfoMessage (object):
	def __init__ (self,route):
		self.route = route

	def decode (self,data):
    		extracted = list(unpack(self.Header.PACK,data[:self.Header.LEN]))
		attributes = Attributes().decode(data[self.Header.LEN:])
		extracted.append(dict(attributes))
    		return self.format(*extracted)

	def extract (self,type):
		for data in self.route.query(type):
			yield self.decode(data)


# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|   Family    |   Reserved  |          Device Type              |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                     Interface Index                           |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                      Device Flags                             |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                      Change Mask                              |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

class Link(_InfoMessage):
	class Header (object):
		PACK = 'BxHiII'
		LEN = calcsize(PACK)

	## linux/if_link.h
	format = namedtuple('Info', 'family type index flags change attributes')

	class Command (object):
		## linux/rtnetlink.h
		RTM_NEWLINK = 0x10  # Create a new network interface
		RTM_DELLINK = 0x11  # Destroy a network interface
		RTM_GETLINK = 0x12  # Retrieve information about a network interface (ifinfomsg)
		RTM_SETLINK = 0x13  #

	class Type (object):
		class Family (object):
			AF_INET  = socket.AF_INET
			AF_INET6 = socket.AF_INET6

		class Device (object):
			IFF_UP            = 0x0001 # Interface is administratively up.
			IFF_BROADCAST     = 0x0002 # Valid broadcast address set.
			IFF_DEBUG         = 0x0004 # Internal debugging flag.
			IFF_LOOPBACK      = 0x0008 # Interface is a loopback interface.
			IFF_POINTOPOINT   = 0x0010 # Interface is a point-to-point link.
			IFF_NOTRAILERS    = 0x0020 # Avoid use of trailers.
			IFF_RUNNING       = 0x0040 # Interface is operationally up.
			IFF_NOARP         = 0x0080 # No ARP protocol needed for this interface.
			IFF_PROMISC       = 0x0100 # Interface is in promiscuous mode.
			IFF_ALLMULTI      = 0x0200 # Receive all multicast packets.
			IFF_MASTER        = 0x0400 # Master of a load balancing bundle.
			IFF_SLAVE         = 0x0800 # Slave of a load balancing bundle.
			IFF_MULTICAST     = 0x1000 # Supports multicast.

			IFF_PORTSEL       = 0x2000 # Is able to select media type via ifmap.
			IFF_AUTOMEDIA     = 0x4000 # Auto media selection active.
			IFF_DYNAMIC       = 0x8000 # Interface was dynamically created.

			IFF_LOWER_UP      = 0x10000 # driver signals L1 up
			IFF_DORMANT       = 0x20000 # driver signals dormant
			IFF_ECHO          = 0x40000 # echo sent packet

		class Attribute (object):
			IFLA_UNSPEC      = 0x00
			IFLA_ADDRESS     = 0x01
			IFLA_BROADCAST   = 0x02
			IFLA_IFNAME      = 0x03
			IFLA_MTU         = 0x04
			IFLA_LINK        = 0x05
		        IFLA_QDISC       = 0x06
			IFLA_STATS       = 0x07

	def getLinks (self):
		return self.extract(self.Command.RTM_GETLINK)


#0                   1                   2                   3
#0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|   Family    |     Length    |     Flags     |    Scope      |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                     Interface Index                         |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

class Address (_InfoMessage):
	class Header (object):
		PACK = '4Bi'
		LEN = calcsize(PACK)

	format = namedtuple('Address', 'family prefixlen flags scope index attributes')

	class Command (object):
		RTM_NEWADDR = 0x14
		RTM_DELADDR = 0x15
		RTM_GETADDR = 0x16

	class Type (object):
		class Family (object):
			AF_INET  = socket.AF_INET
			AF_INET6 = socket.AF_INET6

		class Flag (object):
			IFA_F_SECONDARY  = 0x00 # For secondary address (alias interface)
			IFA_F_PERMANENT  = 0x00 # For a permanent address set by the user.  When this is not set, it means the address was dynamically created (e.g., by stateless autoconfiguration).
			IFA_F_DEPRECATED = 0x00 # Defines deprecated (IPV4) address
			IFA_F_TENTATIVE  = 0x00 # Defines tentative (IPV4) address (duplicate address detection is still in progress)

		class Scope (object):
			RT_SCOPE_UNIVERSE = 0x00 # Global route
			RT_SCOPE_SITE     = 0x00 # Interior route in the local autonomous system
			RT_SCOPE_LINK     = 0x00 # Route on this link
			RT_SCOPE_HOST     = 0x00 # Route on the local host
			RT_SCOPE_NOWHERE  = 0x00 # Destination does not exist

		class Attribute (object):
			IFLA_UNSPEC      = 0x00
			IFLA_ADDRESS     = 0x01
			IFLA_BROADCAST   = 0x02
			IFLA_IFNAME      = 0x03
			IFLA_MTU         = 0x04
			IFLA_LINK        = 0x05
		        IFLA_QDISC       = 0x06
			IFLA_STATS       = 0x07
			IFLA_COST        = 0x08
			IFLA_PRIORITY    = 0x09
			IFLA_MASTER      = 0x0A
		        IFLA_WIRELESS    = 0x0B
			IFLA_PROTINFO    = 0x0C
			IFLA_TXQLEN      = 0x0D
			IFLA_MAP         = 0x0E
			IFLA_WEIGHT      = 0x0F
		        IFLA_OPERSTATE   = 0x10
			IFLA_LINKMODE    = 0x11
			IFLA_LINKINFO    = 0x12
			IFLA_NET_NS_PID  = 0x13
		        IFLA_IFALIAS     = 0x14
			IFLA_NUM_VF      = 0x15
			IFLA_VFINFO_LIST = 0x16
			IFLA_STATS64     = 0x17
		        IFLA_VF_PORTS    = 0x18
			IFLA_PORT_SELF   = 0x19

	def getAddresses (self):
		return self.extract(self.Command.RTM_GETADDR)

#0                   1                   2                   3
#0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|   Family    |    Reserved1  |           Reserved2           |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                     Interface Index                         |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|           State             |     Flags     |     Type      |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

class Neighbor (_InfoMessage):
	class Header (object):
		## linux/if_addr.h
		PACK = 'BxxxiHBB'
		LEN = calcsize(PACK)

	format = namedtuple('Neighbor', 'family index state flags type attributes')

	class Command (object):
		RTM_NEWNEIGH = 0x1C
		RTM_DELNEIGH = 0x1D
		RTM_GETNEIGH = 0x1E

	class Type (object):
		class Family (object):
			AF_INET  = socket.AF_INET
			AF_INET6 = socket.AF_INET6

		class State (object):
			NUD_INCOMPLETE = 0x01 # Still attempting to resolve
			NUD_REACHABLE  = 0x02 # A confirmed working cache entry
			NUD_STALE      = 0x04 # an expired cache entry
			NUD_DELAY      = 0x08 # Neighbor no longer reachable.  Traffic sent, waiting for confirmatio.
			NUD_PROBE      = 0x10 # A cache entry that is currently being re-solicited
			NUD_FAILED     = 0x20 # An invalid cache entry
			# Dummy states
			NUD_NOARP      = 0x40 # A device which does not do neighbor discovery (ARP)
			NUD_PERMANENT  = 0x80 # A static entry
			NUD_NONE       = 0x00

		class Flag (object):
			NTF_USE        = 0x01
			NTF_PROXY      = 0x08 # A proxy ARP entry
			NTF_ROUTER     = 0x80 # An IPv6 router

		class Attribute (object):
			# XXX : Not sure - starts at zero or one ... ??
			NDA_UNSPEC     = 0x00 # Unknown type
			NDA_DST        = 0x01 # A neighbour cache network. layer destination address
			NDA_LLADDR     = 0x02 # A neighbor cache link layer address.
			NDA_CACHEINFO  = 0x03 # Cache statistics
			NDA_PROBES     = 0x04

	def getNeighbors (self):
		return self.extract(self.Command.RTM_GETNEIGH)


#0                   1                   2                   3
#0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|   Family    |  Src length   |  Dest length  |     TOS       |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|  Table ID   |   Protocol    |     Scope     |     Type      |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                          Flags                              |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
class Network (_InfoMessage):
	class Header (object):
		## linux/if_addr.h
		PACK = '8BI' # or is it 8Bi ?
		LEN = calcsize(PACK)

	format = namedtuple('Neighbor', 'family src_len dst_len tos table proto scope type flags attributes')

	class Command (object):
		RTM_NEWROUTE = 0x18
		RTM_DELROUTE = 0x19
		RTM_GETROUTE = 0x1A

	class Type (object):
		class Table (object):
			RT_TABLE_UNSPEC   = 0x00 # An unspecified routing table
			RT_TABLE_DEFAULT  = 0xFD # The default table
			RT_TABLE_MAIN     = 0xFE # The main table
			RT_TABLE_LOCAL    = 0xFF # The local table

		class Protocol (object):
			RTPROT_UNSPEC     = 0x00 # Identifies what/who added the route
			RTPROT_REDIRECT   = 0x01 # By an ICMP redirect
			RTPROT_KERNEL     = 0x02 # By the kernel
			RTPROT_BOOT       = 0x03 # During bootup
			RTPROT_STATIC     = 0x04 # By the administrator
			RTPROT_GATED      = 0x08 # GateD
			RTPROT_RA         = 0x09 # RDISC/ND router advertissements
			RTPROT_MRT        = 0x0A # Merit MRT
			RTPROT_ZEBRA      = 0x0B # ZEBRA
			RTPROT_BIRD       = 0x0C # BIRD
			RTPROT_DNROUTED   = 0x0D # DECnet routing daemon
			RTPROT_XORP       = 0x0E # XORP
			RTPROT_NTK        = 0x0F # Netsukuku
			RTPROT_DHCP       = 0x10 # DHCP client
			# YES WE CAN !
			RTPROT_EXABGP     = 0x11 # Exa Networks ExaBGP

		class Scope (object):
			RT_SCOPE_UNIVERSE = 0x00 # Global route
			RT_SCOPE_SITE     = 0xC8 # Interior route in the local autonomous system
			RT_SCOPE_LINK     = 0xFD # Route on this link
			RT_SCOPE_HOST     = 0xFE # Route on the local host
			RT_SCOPE_NOWHERE  = 0xFF # Destination does not exist

		class Type (object):
			RTN_UNSPEC        = 0x00 # Unknown route.
			RTN_UNICAST       = 0x01 # A gateway or direct route.
			RTN_LOCAL         = 0x02 # A local interface route.
			RTN_BROADCAST     = 0x03 # A local broadcast route (sent as a broadcast).
			RTN_ANYCAST       = 0x04 # An anycast route.
			RTN_MULTICAST     = 0x05 # A multicast route.
			RTN_BLACKHOLE     = 0x06 # A silent packet dropping route.
			RTN_UNREACHABLE   = 0x07 # An unreachable destination.  Packets dropped and host unreachable ICMPs are sent to the originator.
			RTN_PROHIBIT      = 0x08 # A packet rejection route.  Packets are dropped and communication prohibited ICMPs are sent to the originator.
			RTN_THROW         = 0x09 # When used with policy routing, continue routing lookup in another table.  Under normal routing, packets are dropped and net unreachable ICMPs are sent to the originator.
			RTN_NAT           = 0x0A # A network address translation rule.
			RTN_XRESOLVE      = 0x0B # Refer to an external resolver (not implemented).

		class Flag (object):
			RTM_F_NOTIFY      = 0x100 # If the route changes, notify the user
			RTM_F_CLONED      = 0x200 # Route is cloned from another route
			RTM_F_EQUALIZE    = 0x400 # Allow randomization of next hop path in multi-path routing (currently not implemented)
			RTM_F_PREFIX      = 0x800 # Prefix Address

		class Attribute (object):
			RTA_UNSPEC        = 0x00 # Ignored.
			RTA_DST           = 0x01 # Protocol address for route destination address.
			RTA_SRC           = 0x02 # Protocol address for route source address.
			RTA_IIF           = 0x03 # Input interface index.
			RTA_OIF           = 0x04 # Output interface index.
			RTA_GATEWAY       = 0x05 # Protocol address for the gateway of the route
			RTA_PRIORITY      = 0x06 # Priority of route.
			RTA_PREFSRC       = 0x07 # Preferred source address in cases where more than one source address could be used.
			RTA_METRICS       = 0x08 # Route metrics attributed to route and associated protocols (e.g., RTT, initial TCP window, etc.).
			RTA_MULTIPATH     = 0x09 # Multipath route next hop's attributes.
#			RTA_PROTOINFO     = 0x0A # Firewall based policy routing attribute.
			RTA_FLOW          = 0x0B # Route realm.
			RTA_CACHEINFO     = 0x0C # Cached route information.
#			RTA_SESSION       = 0x0D
#			RTA_MP_ALGO       = 0x0E
			RTA_TABLE         = 0x0F

	def getRoutes (self):
		return self.extract(self.Command.RTM_GETROUTE)


#0                   1                   2                   3
#0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|   Family    |  Reserved1    |         Reserved2             |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                     Interface Index                         |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                      Qdisc handle                           |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                     Parent Qdisc                            |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                        TCM Info                             |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class TC (_InfoMessage):
	class Header (object):
		PACK = "BxxxiIII"
		LEN = calcsize(PACK)

	class Command (object):
		RTM_NEWQDISC = 36
		RTM_DELQDISC = 37
		RTM_GETQDISC = 38

	class Type (object):
		class Attribute (object):
			TCA_UNSPEC  = 0x00
			TCA_KIND    = 0x01
			TCA_OPTIONS = 0x02
			TCA_STATS   = 0x03
			TCA_XSTATS  = 0x04
			TCA_RATE    = 0x05
			TCA_FCNT    = 0x06
			TCA_STATS2  = 0x07


#0                   1                   2                   3
#0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|   Mode    |    Reserved1  |           Reserved2             |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#|                         Range                               |
#+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                       Packet ID                             |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                          Mark                               |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                       timestamp_m                           |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                       timestamp_u                           |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                          hook                               |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                       indev_name                            |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                       outdev_name                           |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |           hw_protocol       |        hw_type                |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |         hw_addrlen          |           Reserved            |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                       hw_addr                               |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                       data_len                              |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#   |                      Payload . . .                          |
#   +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+


class Firewall (_InfoMessage):
	class Header (object):
		PACK = "BxxxI"
		LEN = calcsize(PACK)

	class Packet (object):
		class Header (object):
			PACK = "IIIIIIIHHHHII"
			LEN = calcsize(PACK)

