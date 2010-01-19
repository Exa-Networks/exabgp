#!/usr/bin/env python
# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import time
import socket
from struct import pack,unpack

from bgp.rib.table import Table
from bgp.rib.delta import Delta

from bgp.utils                import *
from bgp.structure.address    import AFI,SAFI
from bgp.structure.ip         import BGPPrefix
from bgp.network.connection   import Connection
# XXX: defix should be renamed and moved ...
from bgp.message.parent       import Message,Failure,defix
from bgp.message.nop          import NOP
from bgp.message.open         import Open,Parameter,Capabilities,RouterID,MultiProtocol,RouteRefresh,CiscoRouteRefresh,Graceful
from bgp.message.update       import Update,NLRIS
from bgp.message.update.eor   import EOR
from bgp.message.keepalive    import KeepAlive
from bgp.message.notification import Notification, Notify, NotConnected
from bgp.message.update.attributes     import Attributes
from bgp.message.update.attribute      import AttributeID
from bgp.message.update.attribute.flag        import Flag
from bgp.message.update.attribute.origin      import *	# 01
from bgp.message.update.attribute.aspath      import *	# 02
from bgp.message.update.attribute.nexthop     import *	# 03
from bgp.message.update.attribute.med         import * 	# 04
from bgp.message.update.attribute.localpref   import *	# 05
from bgp.message.update.attribute.aggregate   import *	# 06
from bgp.message.update.attribute.aggregator  import *	# 07
from bgp.message.update.attribute.communities import *	# 08


class Protocol (object):
	trace = False
	decode = True
	strict = False

	def __init__ (self,neighbor,connection=None):
		self.log = Log(neighbor.peer_address,neighbor.peer_as)
		self.neighbor = neighbor
		self.connection = connection
		self._table = Table()
		self._table.update(self.neighbor.routes)
		self._delta = Delta(self._table)

	def connect (self):
		# allows to test the protocol code using modified StringIO with a extra 'pending' function
		if not self.connection:
			peer = self.neighbor.peer_address
			local = self.neighbor.local_address
			asn = self.neighbor.peer_as
			self.connection = Connection(peer,local)

	def check_keepalive (self):
		left = int (self.connection.last_read  + self.neighbor.hold_time - time.time())
		if left <= 0:
			raise Notify(4,0)
		return left

	def close (self):
		#self._delta.last = 0
		if self.connection:
			self.connection.close()
			self.connection = None


	# Read from network .......................................................

	def read_message (self):
		if not self.connection.pending():
			return NOP('')

		data = self.connection.read(19)

		# It seems that select tells us there is data even when there isn't
		if not data:
			raise NotConnected(self.neighbor.peer_address)

		if data[:16] != Message.MARKER:
			# We are speaking BGP - send us a valid Marker
			raise Notify(1,1)

		raw_length = data[16:18]
		length = unpack('!H',raw_length)[0]
		msg = data[18]

		if ( length < 19 or length > 4096):
			# BAD Message Length
			raise Notify(1,2)

		if (
			(msg == Open.TYPE and length < 29) or
			(msg == Update.TYPE and length < 23) or
			(msg == Notification.TYPE and length < 21) or
			(msg == KeepAlive.TYPE and length != 19)
		):
			# MUST send the faulty length back
			raise Notify(1,2,raw_length)
			#(msg == RouteRefresh.TYPE and length != 23)

		length -= 19
		data = self.connection.read(length)

		if len(data) != length:
			raise SendNotificaiton(ord(msg),0)

		self.log.outIf(self.trace and msg == Update.TYPE,"UPDATE RECV: %s " % hexa(data))

		if msg == Notification.TYPE:
			raise Notification(ord(data[0]),ord(data[1]))

		if msg == KeepAlive.TYPE:
			return self.KeepAliveFactory(data)

		if msg == Open.TYPE:
			return self.OpenFactory(data)

		if msg == Update.TYPE:
			return self.UpdateFactory(data)

		if self.strict:
			raise Notify(1,3,msg)

		return NOP(data)

	def read_open (self,ip):
		message = self.read_message()

		if message.TYPE not in [Open.TYPE,]:
			raise Notify(1,1,'first packet not an open message (%s)' % str(message.TYPE))

		if message.asn != self.neighbor.peer_as:
			# ASN sent did not match ASN expected
			raise Notify(2,2,data[1:3])

		if message.hold_time == 0:
			# Hold Time of zero not accepted
			raise Notify(2,6,data[3:5])
		if message.hold_time >= 3:
			self.neighbor.hold_time = min(self.neighbor.hold_time,message.hold_time)

		if message.router_id == '0.0.0.0':
			message.router_id = RouterID(ip)

		return message

	def read_keepalive (self):
		message = self.read_message()
		if message.TYPE != KeepAlive.TYPE:
			raise Notify(5,0)
		return message

	# Sending message to peer .................................................

	def new_open (self,graceful,restarted):
		o = Open(4,self.neighbor.local_as,self.neighbor.router_id.ip(),Capabilities().default(graceful,restarted),self.neighbor.hold_time)
		self.connection.write(o.message())
		return o

	def new_announce (self):
		m = self._delta.announce(self.neighbor.local_as,self.neighbor.peer_as)
		updates = ''.join(m)
		self.log.outIf(self.trace,"UPDATE (update)   SENT: %s" % hexa(updates[19:]))
		if m:
			self.connection.write(updates)
			return m
		return []

	def new_eors (self,families):
		eor = EOR()
		eors = eor.eors(families)
		self.log.outIf(self.trace,"UPDATE (eors) SENT: %s" % hexa(eors[19:]))
		self.connection.write(eors)
		return eor.announced()

	def new_update (self):
		m = self._delta.update(self.neighbor.local_as,self.neighbor.peer_as)
		updates = ''.join(m)
		self.log.outIf(self.trace,"UPDATE (update)   SENT: %s" % hexa(updates[19:]))
		if m:
			self.connection.write(updates)
			return m
		return []

	def new_keepalive (self,force=False):
		left = int(self.connection.last_write + self.neighbor.hold_time.keepalive() - time.time())
		if force or left <= 0:
			k = KeepAlive()
			self.connection.write(k.message())
			return left,k
		return left,None

	def new_notification (self,notification):
		return self.connection.write(notification.message())

	# Message Factory .................................................

	def KeepAliveFactory (self,data):
		return KeepAlive()

	def _key_values (self,name,data):
		if len(data) < 2:
			raise Notify(2,0,"bad length for OPEN %s (<2)" % name)
		l = ord(data[1])
		boundary = l+2
		if len(data) < boundary:
			raise Notify(2,0,"bad length for OPEN %s (buffer underrun)" % name)
		key = ord(data[0])
		value = data[2:boundary]
		rest = data[boundary:]
		return key,value,rest


	def CapabilitiesFactory (self,data):
		capabilities = Capabilities()
		option_len = ord(data[0])
		if option_len:
			data = data[1:]
			while data:
				key,value,data = self._key_values('parameter',data)
				# Paramaters must only be sent once.
				if key == Parameter.AUTHENTIFICATION_INFORMATION:
					raise Notify(2,5)
					continue

				if key == Parameter.CAPABILITIES:
					k,v,r = self._key_values('capability',value)
					if r:
						raise Notify(2,0,"bad length for OPEN %s (size mismatch)" % 'capability')

					if k == Capabilities.MULTIPROTOCOL_EXTENSIONS:
						if k not in capabilities:
							capabilities[k] = MultiProtocol()
						afi = AFI(unpack('!H',value[2:4])[0])
						safi = SAFI(ord(value[5]))
						capabilities[k].append((afi,safi))
						continue

					if k == Capabilities.GRACEFUL_RESTART:
						restart = unpack('!H',value[2:4])[0]
						restart_flag = restart >> 12
						restart_time = restart & Graceful.TIME_MASK
						value = value[4:]
						families = []
						while value:
							afi = AFI(unpack('!H',value[:2])[0])
							safi = SAFI(ord(value[2]))
							flag_family = ord(value[0])
							families.append((afi,safi,flag_family))
							value = value[4:]
						capabilities[k] = Graceful(restart_flag,restart_time,families)
						continue

					if k == Capabilities.FOUR_BYTES_ASN:
						capabilities[k] = ASN(unpack('!L',value[2:6])[0]).four()
						continue

					if k == Capabilities.ROUTE_REFRESH:
						capabilities[k] = RouteRefresh()
						continue

					if k == Capabilities.CISCO_ROUTE_REFRESH:
						capabilities[k] = CiscoRouteRefresh()
						continue

					if k not in capabilities:
						capabilities[k] = Unknown(k)
					if value[2:]:
						capabilities[k].append([ord(_) for _ in value[2:]])
				else:
					raise Notify(2,0,'unknow OPEN parameter %s' % hex(key))
		return capabilities

	def OpenFactory (self,data):
		version = ord(data[0])
		if version != 4:
			# Only version 4 is supported nowdays..
			raise Notify(2,1,data[0])
		asn = unpack('!H',data[1:3])[0]
		hold_time = unpack('!H',data[3:5])[0]
		numeric = unpack('!L',data[5:9])[0]
		router_id = "%d.%d.%d.%d" % (numeric>>24,(numeric>>16)&0xFF,(numeric>>8)&0xFF,numeric&0xFF)
		capabilities = self.CapabilitiesFactory(data[9:])
		return Open(version,asn,router_id,capabilities,hold_time)


	def UpdateFactory (self,data):
		length = len(data)
		# withdrawn
		lw,withdrawn,data = defix(data)
		if len(withdrawn) != lw:
			raise Notify(3,1)
		la,attribute,announced = defix(data)
		if len(attribute) != la:
			raise Notify(3,1)
		# The RFC check ...
		#if lw + la + 23 > length:
		if 2 + lw + 2+ la + len(announced) != length:
			raise Notify(3,1)

		remove = NLRIS()
		while withdrawn:
			nlri = BGPPrefix(AFI.ipv4,withdrawn)
			withdrawn = withdrawn[len(nlri):]
			remove.append(Update(nlri,'-'))

		attributes = self.AttributesFactory(attribute)

		announce = NLRIS()
		while announced:
			nlri = BGPPrefix(AFI.ipv4,announced)
			announced = announced[len(nlri):]
			announce.append(nlri)

		return Update(remove,announce,attributes)


	def AttributesFactory (self,data):
		try:
			self.attributes = Attributes()
			return self._AttributesFactory(data).attributes
		except IndexError:
			raise Notify(3,2,data)


	def _AttributesFactory (self,data):
		if not data:
			return self

		# We do not care if the attribute are transitive or not as we do not redistribute
		flag = Flag(ord(data[0]))
		code = AttributeID(ord(data[1]))

		if flag & Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			offset = 4
		else:
			length = ord(data[2])
			offset = 3

		data = data[offset:]

		if not length:
			return self._AttributesFactory(data[length:])

		if code == AttributeID.ORIGIN:
			self.attributes.add(Origin(ord(data[0])))
			return self._AttributesFactory(data[length:])

		if code == AttributeID.AS_PATH:
			def new_ASPath (data):
				stype = ord(data[0])
				slen = ord(data[1])
				sdata = data[2:2+(slen*2)]

				ASPS = ASPath(stype)
				for c in unpack('!'+('H'*slen),sdata):
					ASPS.add(c)
				return ASPS
			self.attributes.add(new_ASPath(data))
			return self._AttributesFactory(data[length:])

		if code == AttributeID.NEXT_HOP:
			self.attributes.add(NextHop(Inet(AFI.ipv4,data[:4])))
			return self._AttributesFactory(data[length:])

		if code == AttributeID.MED:
			self.attributes.add(MED(unpack('!L',data[:4])[0]))
			return self._AttributesFactory(data[length:])

		if code == AttributeID.LOCAL_PREF:
			self.attributes.add(LocalPreference(unpack('!L',data[:4])[0]))
			return self._AttributesFactory(data[length:])

		if code == AttributeID.ATOMIC_AGGREGATE:
			# ignore
			return self._AttributesFactory(data[length:])

		if code == AttributeID.AGGREGATOR:
			# content is 6 bytes
			return self._AttributesFactory(data[length:])

		if code == AttributeID.COMMUNITY:
			def new_Communities (data):
				communities = Communities()
				while data:
					community = unpack('!L',data[:4])
					data = data[4:]
					communities.add(Community(community))
				return communities
			self.attributes.add(new_Communities(data))
			return self._AttributesFactory(data[length:])

		if code == AttributeID.MP_UNREACH_NLRI:
			next_attributes = data[length:]
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			# XXX: See RFC 5549 for better support
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				print 'we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi)
				return self._AttributesFactory(next_attributes)
			data = data[offset:]
			while data:
				route = BGPPrefix(afi,data)
				data = data[len(route):]
				# XXX: we need to create one route per NLRI and then attribute them
				#self.attributes.add(MPURNLRI(AFI(afi),SAFI(safi),route))
				print 'removing MP route %s' % str(route)
			return self._AttributesFactory(next_attributes)

		if code == AttributeID.MP_REACH_NLRI:
			next_attributes = data[length:]
			data = data[:length]
			afi,safi = unpack('!HB',data[:3])
			offset = 3
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				print 'we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi)
				return self._AttributesFactory(next_attributes)
			len_nh = ord(data[offset])
			offset += 1
			if afi == AFI.ipv4 and not len_nh != 4:
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv4 next-hop length (%d)' % len_nh
				return self._AttributesFactory(next_attributes)
			if afi == AFI.ipv6 and not len_nh in (16,32):
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				print 'bad IPv6 next-hop length (%d)' % len_nh
				return self._AttributesFactory(next_attributes)
			nh = data[offset:offset+len_nh]
			offset += len_nh
			if len_nh == 32:
				# we have a link-local address in the next-hop we ideally need to ignore
				if nh[0] == 0xfe: nh = nh[16:]
				elif nh[16] == 0xfe: nh = nh[:16]
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				else: self(next_attributes)
			if len_nh >= 16: nh = socket.inet_ntop(socket.AF_INET6,nh)
			else: nh = socket.inet_ntop(socket.AF_INET,nh)
			nb_snpa = ord(data[offset])
			offset += 1
			snpas = []
			for i in range(nb_snpa):
				len_snpa = ord(offset)
				offset += 1
				snpas.append(data[offset:offset+len_snpa])
				offset += len_snpa
			data = data[offset:]
			while data:
				route = new_Route(afi,data)
				data = data[len(route.nlri):]
				# XXX: we are not storing the NextHop Anymore
				#route.next_hop = nh
				#self.attributes.add(MPRNLRI(AFI(afi),SAFI(safi),route))
				print 'adding MP route %s' % str(route)
			return self._AttributesFactory(next_attributes)

		import warnings
		warnings.warn("Could not parse attribute %s %s" % (str(code),[hex(ord(_)) for _ in data]))
		return self._AttributesFactory(data[length:])

