# encoding: utf-8
'''
definition.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
'''

class Enumeration (object):
	def __init__(self, *names):
		for number, name in enumerate(names):
			setattr(self, name, number)

	def text (self,number):
		for name in dir(self):
			if getattr(self,name) == number:
				return name


TYPE = Enumeration (
	'error',
	'boolean',
	'int8',
	'int16',
	'int32',
	'string',
	'list',
	'dictionary',
	'ip',
	'ipv4',
	'ipv6',
	'reference',
	'references'
)

PRESENCE = Enumeration(
	'optional',
	'mandatory'
)

# TYPE CHECK
def check_boolean (data):
	return type(data) == type(True)
def check_int8 (data):
	return type(data) == type(0) and data < pow(2,8)
def check_int16 (data):
	return type(data) == type(0) and data < pow(2,16)
def check_int32 (data):
	return type(data) == type(0) and data < pow(2,32)
def check_string (data):
	return type(data) == type(u'')
def check_list (data):
	return type(data) == type([])
def check_dict (data):
	return type(data) == type({})
def check_reference (data):
	return True

CHECK_TYPE = {
	TYPE.boolean : check_boolean,
	TYPE.int8 : check_int8,
	TYPE.int16 : check_int16,
	TYPE.int32 : check_int32,
	TYPE.string : check_string,
	TYPE.list : check_list,
	TYPE.dictionary : check_dict,
	TYPE.reference : check_reference,
}

# DATA CHECK
def check_nop (data):
	return True
def check_ip (data,):
	return check_ipv4(data) or check_ipv6(data)
def check_ipv4 (data):  # XXX: improve
	return type(data) == type(u'') and data.count('.') == 3
def check_ipv6 (data):  # XXX: improve
	return type(data) == type(u'') and ':' in data
def check_positive (data):
	return data >= 0
def check_asn (data):
	return data >= 1

# LIST DATA CHECK
def check_aspath (data):
	return type(data) == type(0) and data < pow(2,32)
def check_community (data):
	return type(data) == type([]) and len(data) == 2 and type(data[0]) == type(0) and type(data[1]) == type(0)

def check_flow_port (data):
	return True

class OrderedDict (dict):
	def __init__(self, args):
		dict.__init__(self, args)
		self._order = [_ for _,__ in args]

	def __setitem__(self, key, value):
		dict.__setitem__(self, key, value)
		if key in self._order:
			self._order.remove(key)
		self._order.append(key)

	def __delitem__(self, key):
		dict.__delitem__(self, key)
		self._order.remove(key)

	def order(self):
		return self._order[:]

	def ordered_items(self):
		return [(key,self[key]) for key in self._order]

	def keys(self):
		return self.order()

definition = (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
	('exabgp' , (TYPE.int8, PRESENCE.mandatory, [4,])),
	('neighbor' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
		('tcp' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
			('local' , (TYPE.string, PRESENCE.mandatory , check_ip)),
			('peer' , (TYPE.string, PRESENCE.mandatory , check_ip)),
			('ttl-security' , (TYPE.int8, PRESENCE.optional , check_nop)),
			('md5' , (TYPE.string, PRESENCE.optional , check_nop))
		)))),
		('api' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			('<*>' , (TYPE.list, PRESENCE.mandatory, ['neighbor-changes','send-packets','receive-packets','receive-routes'])),
		)))),
		('session' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
			('router-id' , (TYPE.string, PRESENCE.mandatory , check_ipv4)),
			('hold-time' , (TYPE.int16, PRESENCE.mandatory , check_positive)),
			('asn' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
				('local' , (TYPE.int32, PRESENCE.mandatory , check_asn)),
				('peer' , (TYPE.int32, PRESENCE.mandatory , check_asn)),
			)))),
			('capability' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
				('family' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
					('inet'  , (TYPE.list, PRESENCE.optional, ['unicast','multicast','nlri-mpls','mpls-vpn','flow-vpnv4','flow'])),
					('inet4' , (TYPE.list, PRESENCE.optional, ['unicast','multicast','nlri-mpls','mpls-vpn','flow-vpnv4','flow'])),
					('inet6' , (TYPE.list, PRESENCE.optional, ['unicast','flow'])),
					('alias' , (TYPE.string, PRESENCE.optional, ['all','minimal'])),
				)))),
				('asn4' , (TYPE.boolean, PRESENCE.optional , check_nop)),
				('route-refresh' , (TYPE.boolean, PRESENCE.optional , check_nop)),
				('graceful-restart' , (TYPE.boolean, PRESENCE.optional , check_nop)),
				('multi-session' , (TYPE.boolean, PRESENCE.optional , check_nop)),
				('add-path' , (TYPE.boolean, PRESENCE.optional , check_nop)),
			))))
		)))),
		('announce' , (TYPE.references, PRESENCE.optional,'attributes.updates.prefix.*'))
	)))),
	('api' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
		('<*>' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			('encoder' , (TYPE.string, PRESENCE.optional, ['json','text'])),
			('program' , (TYPE.string, PRESENCE.mandatory, check_nop)),
		)))),
	)))),
	('attributes' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
		('<*>' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			('next-hop', (TYPE.string, PRESENCE.optional, check_ipv4)),
			('origin' , (TYPE.string, PRESENCE.optional, ['igp','egp','incomplete'])),
			('as-path' , (TYPE.list, PRESENCE.optional, check_aspath)),
			('local-preference', (TYPE.int32, PRESENCE.optional, check_positive)),
			('med', (TYPE.int32, PRESENCE.optional, check_positive)),
			('aggregator' , (TYPE.string , PRESENCE.optional, check_ipv4)),
			('aggregator-id' , (TYPE.string , PRESENCE.optional, check_ipv4)),
			('atomic-aggregate' , (TYPE.boolean , PRESENCE.optional, check_nop)),
			('community' , (TYPE.list , PRESENCE.optional, check_community)),
#			'cluster-list'
#			'extended-community'
#			more ?
		)))),
	)))),
	('flow' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
		('filtering-condition' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			('<*>' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
				('source' , (TYPE.list, PRESENCE.optional, check_ipv4)),
				('destination' , (TYPE.list, PRESENCE.optional, check_ipv4)),
				('port' , (TYPE.list, PRESENCE.optional, check_flow_port)),
			)))),
		)))),
		('filtering-action' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			('<*>' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			)))),
		)))),
	)))),
	('updates' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
	))))
)))

# 	'filtering-condition': {
# 		'simple-ddos': {
# 			'source': '10.0.0.1/32',
# 			'destination': '192.168.0.1/32',
# 			'port': [[['=',80]]],
# 			'protocol': 'tcp'
# 		},
# 		'port-block': {
# 			'port': [ [['=',80 ]],[['=',8080]] ],
# 			'destination-port': [ [['>',8080],['<',8088]], [['=',3128]] ],
# 			'source-port': [[['>',1024]]],
# 			'protocol': [ 'tcp', 'udp' ]
# 		},
# 		'complex-attack': {
# 			'packet-length': [ [['>',200],['<',300]], [['>',400],['<',500]] ],
# 			'_fragment': ['not-a-fragment'],
# 			'fragment': ['first-fragment','last-fragment' ],
# 			'_icmp-type': [ 'unreachable', 'echo-request', 'echo-reply' ],
# 			'icmp-code': [ 'host-unreachable', 'network-unreachable' ],
# 			'tcp-flags': [ 'urgent', 'rst' ],
# 			'dscp': [ 10, 20 ]
# 		}
# 	},
# 	'fitering-action': {
# 		'make-it-slow': {
# 				'rate-limit': 9600
# 		},
# 		'drop-it': {
# 				'discard': true
# 		},
# 		'send-it-elsewhere': {
# 				'redirect': [65500,12345]
# 		},
# 		'send-it-community': {
# 			'redirect': ['1.2.3.4',5678],
# 			'community': [[30740,0], [30740,30740]]
# 		}
# 	},
# 	'updates': {
# 		'prefix': {
# 			'local-routes': {
# 				'normal-ebgp-attributes': {
# 					'192.168.0.0/24': {
# 						'next-hop': '192.0.2.1'
# 					},
# 					'192.168.0.0/24': {
# 						'next-hop': '192.0.2.2'
# 					}
# 				},
# 				'simple-attributes': {
# 					'_': 'it is possible to overwrite some previously defined attributes',
# 					'192.168.1.0/24': {
# 						'next-hop': '192.0.2.1'
# 					},
# 					'192.168.2.0/24': {
# 					}
# 				}
# 			},
# 			'remote-routes': {
# 				'simple-attributes': {
# 					'10.0.0.0/16': {
# 						'_': 'those three can be defined everywhere too, but require the right capability',
# 						'label': '0',
# 						'path-information': '0',
# 						'route-distinguisher': '0',
# 						'split': 24
# 					}
# 				}
# 			}
# 		},
# 		'flow': {
# 			'off-goes-the-ddos': {
# 				'simple-ddos': 'make-it-slow',
# 				'port-block': 'drop-it'
# 			},
# 			'saved_just_in_case': {
# 				'complex-attack': 'send-it-elsewhere'
# 			}
# 		}
# 	}
# }

from exabgp.configuration.loader import read

json = read('/Users/thomas/source/hg/exabgp/tip/QA/configuration/first.exa')

def validate (root,json,definition,location=[]):
	kind,presence,valid = definition

	if kind == TYPE.error:
		print valid, ' '.join(location)
		return False

	# ignore missing optional elements
	if not json:
		print '/'.join(location), 'not present'
		return presence == PRESENCE.optional

	# check that the value of the right type
	if not CHECK_TYPE[kind](json):
		return False

	# for dictionary check all the elements inside
	if kind == TYPE.dictionary:
		keys = valid.keys()
		wildcard = True

		while keys:
			key = keys.pop()
			if key.startswith('_'):
				print "skipping", key
				continue

			if key in ['announce','flow']:
				print "skipping", key
				continue

			if type(json) != type({}):
				print "bad data, not a dict", json
				return False

			if key == '<*>' and wildcard:
				keys = json.keys()
				wildcard = False
				continue

			print 'key',key
			subtest = valid.get(key,valid.get('<*>',(TYPE.error,None,'problem validating configuration')))
			if not validate(root,json.get(key,None),subtest,location + [key]):
				return False
		return True

	if kind == TYPE.list:
		check = definition[2]
		# This is a function
		if hasattr(check, '__call__'):
			for data in json:
				if not check(data):
					return False
			return True
		# This is a list of valid option
		elif type(valid) == type([]):
			for data in json:
				if not data in valid:
					return False
			return True
		# no idea what the data is - so something is wrong with the program
		else:
			return False

	else:
		check = definition[2]
		# check that the value of the data
		if hasattr(check, '__call__'):
			if not check(json):
				return False
			return True
		elif type(valid) == type([]):
			if not json in valid:
				return False
			return True
		else:
			return False

print validate(json,json,definition)

