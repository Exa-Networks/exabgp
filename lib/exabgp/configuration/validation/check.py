# encoding: utf-8
'''
check.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
'''

from exabgp.structure.enumeration import Enumeration

TYPE = Enumeration (
	'boolean',     # -  1
	'integer',     # -  2
	'string',      # -  4
	'list',        # -  8
	'dictionary',  # - 16
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
def list (data):
	return type(data) == type([])
def dict (data):
	return type(data) == type({})

CHECK_TYPE = {
	TYPE.boolean : boolean,
	TYPE.integer : integer,
	TYPE.string : string,
	TYPE.list : list,
	TYPE.dictionary : dict,
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

def asn (data):
	return data >= 1

# LIST DATA CHECK
def aspath (data):
	return type(data) == type(0) and data < pow(2,32)
def community (data):
	return type(data) == type([]) and \
		len(data) == 2 and \
			type(data[0]) == type(0) and \
			type(data[1]) == type(0)
def dscp (data):
	return integer(data) and uint8(data)

# FLOW DATA CHECK
def flow_ipv4_range (data):  # TODO
	return True
def flow_port (data):  # TODO
	return True
def flow_length (data):  # TODO
	return True

def redirect (data):  # TODO
	return True

