# encoding: utf-8
'''
check.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
'''

from exabgp.structure.enumeration import Enumeration

TYPE = Enumeration (
	'boolean',  # -  1
	'integer',  # -  2
	'string',   # -  4
	'array',    # -  8
	'object',   # - 16
)

PRESENCE = Enumeration(
	'optional',   # -  1
	'mandatory',  # -  2
)

# TYPE CHECK
def boolean (data):
	return type(data) == type(True)
def integer (data):
	return type(data) == type(0)
def string (data):
	return type(data) == type(u'') or type(data) == type('')
def array (data):
	return type(data) == type([])
def object (data):
	return type(data) == type({})
# XXX: Not very good to redefine the keyword object, but this class uses no OO ...

CHECK_TYPE = {
	TYPE.boolean : boolean,
	TYPE.integer : integer,
	TYPE.string : string,
	TYPE.array : array,
	TYPE.object : dict,
}

def kind (kind,data):
	for t in CHECK_TYPE:
		if kind & t:
			if CHECK_TYPE[t](data):
				return True
	return False

# DATA CHECK
def nop (data):
	return True

def uint8 (data):
	return data >= 0 and data < pow(2,8)
def uint16 (data):
	return data >= 0 and data < pow(2,16)
def uint32 (data):
	return data >= 0 and data < pow(2,32)
def float (data):
	return data >=0 and data < 3.4 * pow(10,38)  # approximation of max from wikipedia

def ip (data,):
	return ipv4(data) or ipv6(data)

def ipv4 (data):  # XXX: improve
	return type(data) == type(u'') and data.count('.') == 3
def ipv6 (data):  # XXX: improve
	return type(data) == type(u'') and ':' in data

def range4 (data):
	return type(data) == type(0) and data > 0 and data <= 32
def range6 (data):
	return type(data) == type(0) and data > 0 and data <= 128

def ipv4_range (data):
	if not data.count('/') == 1:
		return False
	ip,r = data
	if not ipv4(ip):
		return False
	if not range4(r):
		return False
	return True

def asn16 (data):
	return data >= 1 and data < pow(2,16)
def asn32 (data):
	return data >= 1 and data < pow(2,32)
asn = asn32

def md5 (data):
	return len(data) <= 18

def localpreference (data):
	return uint32(data)

def med (data):
	return uint32(data)

def originator (data):
	return ipv4(data)

def distinguisher (data):
	parts = data.split(':')
	if len(parts) != 2:
		return False
	_,__ = parts
	return (_.isdigit() and asn16(int(_)) and ipv4(__)) or (ipv4(_) and __.isdigit() and asn16(int(__)))

def pathinformation (data):
	if integer(data):
		return uint32(data)
	if string(data):
		return ipv4(data)
	return False

def watchdog (data):
	return ' ' not in data  # TODO: improve

def split (data):
	return range6(data)


# LIST DATA CHECK
# Those function need to perform type checks before using the data


def aspath (data):
	return type(data) == type(0) and data < pow(2,32)

def assequence (data):
	return type(data) == type(0) and data < pow(2,32)

def community (data):
	if integer(data):
		return uint32(data)
	if string(data) and data.lower() in ('no-export', 'no-advertise', 'no-export-subconfed', 'nopeer', 'no-peer'):
		return True
	return array(data) and len(data) == 2 and \
		integer(data[0]) and integer(data[1]) and \
		asn16(data[0]) and uint16(data[1])

def extendedcommunity (data):  # TODO: improve, incomplete see http://tools.ietf.org/rfc/rfc4360.txt
	if integer(data):
		return True
	if string(data) and data.count(':') == 2:
		_,__,___ = data.split(':')
		if _.lower() not in ('origin','target'):
			return False
		return (__.isdigit() and asn16(__) and ipv4(___)) or (ipv4(__) and ___.isdigit() and asn16(___))
	return False

def label (data):
	return integer(data) and \
		data >= 0 and data < pow(2,20)  # XXX: SHOULD be taken from Label class

def clusterlist (data):
	return integer(data) and uint8(data)

def aggregator (data):
	if not array(data):
		return False
	if len(data) == 0:
		return True
	if len(data) == 2:
		return \
			integer(data[0]) and string(data[1]) and \
			asn(data[0]) and ipv4(data[1])
	return False

def dscp (data):
	return integer(data) and uint8(data)


# FLOW DATA CHECK
#


def flow_ipv4_range (data):  # TODO
	return True
def flow_port (data):  # TODO
	return True
def flow_length (data):  # TODO
	return True

def redirect (data):  # TODO
	return True

