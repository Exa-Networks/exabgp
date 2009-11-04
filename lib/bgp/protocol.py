#!/usr/bin/env python
# encoding: utf-8
"""
protocol.py

Created by Thomas Mangin on 2009-08-25.
Copyright (c) 2009 Exa Networks. All rights reserved.
"""

import math
import time
import socket
from struct import pack,unpack

from bgp.table import Table
from bgp.data import AFI,SAFI,Parameter,Capabilities,Flag,Attribute,Origin,HoldTime,IP,Route
from bgp.message import Message, Open, Update, Failure,Notification, SendNotification, KeepAlive
from bgp.network import Network
from bgp.display import Display



class Protocol (Display):
	trace = False
	decode = True
	
	def __init__ (self,neighbor,network=None):
		Display.__init__(self,neighbor.peer_address,neighbor.peer_as)
		self.neighbor = neighbor
		self.network = network
		self._table = Table()
		self._update = Update(self._table)
		self._table.update(self.neighbor.routes)

	def connect (self):
		# allows to test the protocol code using modified StringIO with a extra 'pending' function
		if not self.network:
			peer = self.neighbor.peer_address
			local = self.neighbor.local_address
			asn = self.neighbor.peer_as
			self.network = Network(peer,local,asn)
	
	def check_keepalive (self):
		left = int (self.network.last_read  + self.neighbor.hold_time - time.time())
		if left <= 0:
			raise SendNotification(4,0)
		return left
	
	def close (self):
		self._update.last = 0
		if self.network:
			self.network.close()
			self.network = None
	
	
	# Read from network .......................................................
	
	# XXX: the name is HORRIBLE, fix this !!
	def _defix (self,data):
		l = unpack('!H',data[0:2])[0]
		return l,data[2:l+2],data[l+2:]
	
	def _read_header (self):
		# Read it as a block as it is better for the timer code
		data = self.network.read(19)
		
		marker = data[:16]
		if marker != Message.MARKER:
			# We are speaking BGP - send us a valid Marker
			raise SendNotification(1,1)
		
		raw_length = data[16:18]
		length = unpack('!H',raw_length)[0]
		if ( length < 19 or length > 4096):
			# BAD Message Length
			raise SendNotification(1,2)
		
		msg = data[18]
		if (
			(msg == Open.TYPE and length < 29) or
			(msg == Update.TYPE and length < 23) or
			(msg == Notification.TYPE and length < 21) or
			(msg == KeepAlive.TYPE and length != 19)
		):
			# MUST send the faulty length back
			raise SendNotification(1,2,raw_length)
			#(msg == RouteRefresh.TYPE and length != 23)
		
		return msg,length-19
	
	def _key_values (self,name,data):
		if len(data) < 2:
			raise SendNotification(2,0,"bad length for OPEN %s (<2)" % name)
		l = ord(data[1])
		boundary = l+2
		if len(data) < boundary:
			raise SendNotification(2,0,"bad length for OPEN %s (buffer underrun)" % name)
		key = ord(data[0])
		value = data[2:boundary]
		rest = data[boundary:]
		return key,value,rest
	
	def read_open (self):
		msg,l = self._read_header()
		data = self.network.read(l)
		
		if msg == Notification.TYPE:
			# You did not like our open .. grrr who has an ASN mismatch (most likely) :p ..
			raise Notification(ord(data[0]),ord(data[1]))
		
		if msg != Open.TYPE:
			# We are speaking BGP - send us an OPEN ..
			raise SendNotification(1,1,chr(msg))
		
		version = ord(data[0])
		if version != 4:
			# Only version 4 is supported nowdays..
			raise SendNotification(2,1,data[0])
		
		asn = unpack('!H',data[1:3])[0]
		if asn != self.neighbor.peer_as:
			# ASN sent did not match ASN expected
			raise SendNotification(2,2,data[1:3])
		
		hold_time = unpack('!H',data[3:5])[0]
		if hold_time == 0:
			# Hold Time of zero not accepted
			raise SendNotification(2,6,data[3:5])
		if hold_time >= 3:
			self.neighbor.hold_time = HoldTime(min(self.neighbor.hold_time,hold_time))
		
		numeric = unpack('!L',data[5:9])[0]
		router_id = "%d.%d.%d.%d" % (numeric>>24,(numeric>>16)&0xFF,(numeric>>8)&0xFF,numeric&0xFF)

		capabilities = Capabilities()
		option_len = ord(data[9])
		if option_len:
			opts = data[10:]
			#self.hexdump(opts)
			while opts:
				key,value,opts = self._key_values('parameter',opts)
				# Paramaters must only be sent once.
				if key == Parameter.AUTHENTIFICATION_INFORMATION:
					raise SendNotification(2,5)
				elif key == Parameter.CAPABILITIES:
					k,v,r = self._key_values('capability',value)
					if r:
						raise SendNotification(2,0,"bad length for OPEN %s (size mismatch)" % 'capability')
					if k not in capabilities:
						capabilities[k] = []
					if k == 1:
						afi = AFI(unpack('!H',value[2:4])[0])
						safi = SAFI(ord(value[5]))
						capabilities[k].append((afi,safi))
					else:
						if value[2:]:
							capabilities[k].append([ord(_) for _ in value[2:]])
				else:
					raise SendNotification(2,0,'unknow OPEN parameter %s' % hex(key))
		o = Open(version,asn,router_id,capabilities,hold_time)
		return o

	def absorb_message (self):
		if not self.network.pending():
			return chr(0),''

		msg,l = self._read_header()
		data = self.network.read(l)

		if msg not in [KeepAlive.TYPE,Update.TYPE,Notification.TYPE]:
			raise SendNotification(1,3,chr(msg))

		self.logIf(self.trace and msg == Update.TYPE,"UPDATE RECV: %s " % [hex(ord(c)) for c in data])

		if msg == Notification.TYPE:
			# The other side wants to close
			raise Notification(ord(data[0]),ord(data[1]))

		# The KeepAlive (dealt at Network level - or should it not)
		return msg, data

	def read_message (self):
		if not self.network.pending():
			return chr(0),''
		
		msg,l = self._read_header()
		data = self.network.read(l)
		
		if msg not in [KeepAlive.TYPE,Update.TYPE,Notification.TYPE]:
			raise SendNotification(1,3,chr(msg))
		self.logIf(self.trace and msg == Update.TYPE,"UPDATE RECV: %s " % [hex(ord(c)) for c in data])

		if msg == Notification.TYPE:
			raise Notification(ord(data[0]),ord(data[1]))
		
		if msg == Update.TYPE:
			return msg,self.read_update(l,data)

		# ignore KeepAlive
		return msg,data
	
	def read_keepalive (self):
		msg,data = self.read_message()
		if msg and msg != KeepAlive.TYPE:
			raise SendNotification(5,0)
		return msg,data
	
	def read_update (self,length,data):
		try:
			return self._read_update(length,data)
		except IndexError:
			# something went wrong parsing .. do not know what
			raise SendNotification(3,0)
	
	def _read_update (self,length,data):
#		self.log('- UPDATE -----------------')
#		self.hexdump(data)
#		self.log('--------------------------')
		# withdrawn
		lw,withdrawn,data = self._defix(data)
		if len(withdrawn) != lw:
			raise SendNotification(3,1)
		la,announce,nlri = self._defix(data)
		if len(announce) != la:
			raise SendNotification(3,1)
		if 2 + lw + 2+ la + len(nlri) != length:
			raise SendNotification(3,1)

		# The RFC check ...
		#if lw + la + 23 > length:
		#	raise SendNotification(3,1)
		
#		print 'w   ', [hex(ord(c)) for c in withdrawn]
#		print 'pa  ', [hex(ord(c)) for c in announce]
#		print 'nlri', [hex(ord(c)) for c in nlri]

		remove = []
		while withdrawn:
			route, withdrawn = self.read_bgp(withdrawn)
			remove.append(route)
			self.logIf(True,'removing route %s' % str(route))

		add = []
		while nlri:
			route,nlri = self.read_bgp(nlri)
			add.append(route)
			self.logIf(True,'adding route %s' % str(route))

		self.set_path_attribute(add,remove,announce)

		routes = []
		for route in remove:
			routes.append(('-',route))
		for route in add:
			routes.append(('+',route))
		return routes

	def set_path_attribute (self,add,remove,data):
		if not data: return
		
		# We do not care if the attribute are transitive or not as we do not redistribute
		flag = Flag(ord(data[0]))
		code = Attribute(ord(data[1]))
		
		if flag & Flag.EXTENDED_LENGTH == Flag.EXTENDED_LENGTH:
			length = unpack('!H',data[2:4])[0]
			offset = 4
		else:
			length = ord(data[2])
			offset = 3
		
		if code == Attribute.ORIGIN:
			origin = ord(data[offset:offset+length])
			# we do not care yet
			self.set_path_attribute(add,remove,data[offset+length:])
			return
		if code == Attribute.AS_PATH:
			if not length:
				self.set_path_attribute(add,remove,data[offset+length:])
				return
			segment_type = ord(data[offset])
			segment_len = ord(data[offset+1])
			segment_data = data[offset+2:offset+2+(segment_len*2)]
			asns = unpack('!H'*segment_len,segment_data)
			# ignore it
			self.set_path_attribute(add,remove,data[offset+length:])
			return
		if code == Attribute.NEXT_HOP:
			nhn = unpack('!L',data[offset:offset+length])[0]
			next_hop = "%d.%d.%d.%d" % (nhn>>24,(nhn>>16)&0xFF,(nhn>>8)&0xFF,nhn&0xFF)
			for route in add:
				route.set_next_hop(next_hop)
			self.set_path_attribute(add,remove,data[offset+length:])
			return
		if code == Attribute.MULTI_EXIT_DISC:
			med = unpack('!L',data[offset:offset+4])[0]
			# ignore
			self.set_path_attribute(add,remove,data[offset+length:])
			return
		if code == Attribute.LOCAL_PREFERENCE:
			pref = unpack('!L',data[offset:offset+4])[0]
			# if length != 4 we should really raise as you can not have multiple LOCAL_PREF
			for route in add:
				route.set_local_preference(pref)
			self.set_path_attribute(add,remove,data[offset+length:])
			return
		if code == Attribute.ATOMIC_AGGREGATE:
			# ignore
			self.set_path_attribute(add,remove,data[offset+length:])
			return
		if code == Attribute.AGGREGATOR:
			# content is 6 bytes
			self.set_path_attribute(add,remove,data[offset+length:])
			return
		if code == Attribute.MP_UNREACH_NLRI:
			afi = AFI(unpack('!H',data[offset:offset+2])[0])
			offset += 2
			safi = SAFI(ord(data[offset]))
			offset += 1
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				log('we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi))
				return
			nlri = data[offset:]
			while nlri:
				route,nlri = read_bgp(nlri,afi)
				remove.append(route)
				self.logIf(True,'removing MP route %s' % str(route))
			return
		if code == Attribute.MP_REACH_NLRI:
			afi = AFI(unpack('!H',data[offset:offset+2])[0])
			offset += 2
			safi = SAFI(ord(data[offset]))
			offset += 1
			if not afi in (AFI.ipv4,AFI.ipv6) or safi != SAFI.unicast:
				log('we only understand IPv4/IPv6 and should never have received this route (%s %s)' % (afi,safi))
				return
			len_nh = ord(data[offset])
			offset += 1
			if afi == AFI.ipv4 and not len_nh != 4:
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				log('bad IPv4 next-hop length (%d)' % len_nh)
				return
			if afi == AFI.ipv6 and not len_nh in (16,32):
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				log('bad IPv6 next-hop length (%d)' % len_nh)
				return
			nh = data[offset:offset+len_nh]
			if len_nh == 32:
				# we have a link-local address in the next-hop we ideally need to ignore
				if nh[0] == 0xfe: nh = nh[16:]
				elif nh[16] == 0xfe: nh = nh[:16]
				# We are not following RFC 4760 Section 7 (deleting route and possibly tearing down the session)
				else: return
			nh = socket.inet_ntop(socket.AF_INET6 if len_nh >= 16 else socket.AF_INET,nh)
			offset += len_nh
			nb_snpa = ord(data[offset])
			offset += 1
			snpas = []
			for i in range(nb_snpa):
				len_snpa = ord(offset)
				offset += 1
				snpas.append(data[offset:offset+len_snpa])
				offset += len_snpa
			nlri = data[offset:]
			while nlri:
				#self.hexdump(nlri)
				route,nlri = self.read_bgp(nlri,afi)
				route.set_next_hop(nh)
				add.append(route)
				self.logIf(True,'adding MP route %s' % str(route))
			return
		return
	
	def read_bgp (self,data,afi=AFI.ipv4):
		mask = ord(data[0])
		size = size = int(math.ceil(float(mask)/8))
		
		if afi == AFI.ipv4:
			fill = 4
			afi = socket.AF_INET
		elif afi == AFI.ipv6:
			fill = 16
			afi = socket.AF_INET6
		else:
			return None,None
			
		parsed  = data[1:size+1] + '\0'* (fill-size), data[size+fill+1:]
		ip = socket.inet_ntop(afi,parsed[0])
		return Route(ip,mask),parsed[1]
	
	# Sending message to peer .................................................
	
	
	def new_open (self):
		o = Open(4,self.neighbor.local_as,self.neighbor.router_id,Capabilities().default(),self.neighbor.hold_time)
		self.network.write(o.message())
		return o
	
	def new_announce (self):
		m = self._update.announce(self.neighbor.local_as,self.neighbor.peer_as)
		self.logIf(self.trace,"UPDATE (announce) SENT: %s" % [hex(ord(c)) for c in m][19:])
		self.network.write(m)
		return self._update if m else None
	
	def new_update (self):
		m = self._update.update(self.neighbor.local_as,self.neighbor.peer_as)
		self.logIf(self.trace,"UPDATE (update)   SENT: %s" % [hex(ord(c)) for c in m][19:])
		if m: self.network.write(m)
		return self._update if m else None
	
	def new_keepalive (self,force=False):
		left = int(self.network.last_write + self.neighbor.hold_time.keepalive() - time.time())
		if force or left <= 0:
			k = KeepAlive()
			self.network.write(k.message())
			return left,k
		return left,None
	
	def new_notification (self,notification):
		return self.network.write(notification.message())
	
	
