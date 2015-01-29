# encoding: utf-8
"""
check.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2015 Exa Networks. All rights reserved.
"""


class TYPE (object):
	NULL     = 0x01
	BOOLEAN  = 0x02
	INTEGER  = 0x04
	STRING   = 0x08
	ARRAY    = 0x10
	HASH     = 0x20


class PRESENCE (object):
	OPTIONAL  = 0x01
	MANDATORY = 0x02


# TYPE CHECK

def null (data):
	return type(data) == type(None)  # noqa


def boolean (data):
	return type(data) == type(True)  # noqa


def integer (data):
	return type(data) == type(0)  # noqa


def string (data):
	return type(data) == type(u'') or type(data) == type('')  # noqa


def array (data):
	return type(data) == type([])  # noqa


def hashtable (data):
	return type(data) == type({})  # noqa


# XXX: Not very good to redefine the keyword object, but this class uses no OO ...

CHECK_TYPE = {
	TYPE.NULL: null,
	TYPE.BOOLEAN: boolean,
	TYPE.INTEGER: integer,
	TYPE.STRING: string,
	TYPE.ARRAY: array,
	TYPE.HASH: hashtable,
}


def kind (kind, data):
	for t in CHECK_TYPE:
		if kind & t:
			if CHECK_TYPE[t](data):
				return True
	return False

# DATA CHECK


def nop (data):
	return True


def uint8 (data):
	return 0 <= data < pow(2,8)


def uint16 (data):
	return 0 <= data < pow(2,16)


def uint32 (data):
	return 0 <= data < pow(2,32)


def float (data):
	return 0 <= data < 3.4 * pow(10,38)  # approximation of max from wikipedia


def ip (data):
	return ipv4(data) or ipv6(data)


def ipv4 (data):  # XXX: improve
	return string(data) and data.count('.') == 3


def ipv6 (data):  # XXX: improve
	return string(data) and ':' in data


def range4 (data):
	return 0 < data <= 32


def range6 (data):
	return 0 < data <= 128


def ipv4_range (data):
	if not data.count('/') == 1:
		return False
	ip,r = data.split('/')
	if not ipv4(ip):
		return False
	if not r.isdigit():
		return False
	if not range4(int(r)):
		return False
	return True


def port (data):
	return 0 <= data < pow(2,16)


def asn16 (data):
	return 1 <= data < pow(2,16)


def asn32 (data):
	return 1 <= data < pow(2,32)
asn = asn32


def md5 (data):
	return len(data) <= 18


def localpreference (data):
	return uint32(data)


def med (data):
	return uint32(data)


def aigp (data):
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
	return integer(data) and data < pow(2,32)


def assequence (data):
	return integer(data) and data < pow(2,32)


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
	return integer(data) and 0 <= data < pow(2, 20)  # XXX: SHOULD be taken from Label class


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


def flow_ipv4_range (data):
	if array(data):
		for r in data:
			if not ipv4_range(r):
				return False
	if string(data):
		return ipv4_range(data)
	return False


def _flow_numeric (data, check):
	if not array(data):
		return False
	for et in data:
		if not (array(et) and len(et) == 2 and et[0] in ('>', '<', '=','>=', '<=') and integer(et[1]) and check(et[1])):
			return False
	return True


def flow_port (data):
	return _flow_numeric(data,port)


def _length (data):
	return uint16(data)


def flow_length (data):
	return _flow_numeric(data,_length)


def redirect (data):  # TODO: check that we are not too restrictive with our asn() calls
	parts = data.split(':')
	if len(parts) != 2:
		return False
	_,__ = parts
	if not __.isdigit() and asn16(int(__)):
		return False
	return ipv4(_) or (_.isdigit() and asn16(int(_)))
