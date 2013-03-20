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


TYPE = Enumeration ('boolean','int8','int16','int32','string','list','dictionary','ip','ipv4','ipv6','reference','references')
PRESENCE = Enumeration('optional','mandatory')

def check_boolean (data,root,keys):
	return type(data) == type(True)
def check_int8 (data,root,keys):
	return type(data) == type(0) and data < pow(2,8)
def check_int16 (data,root,keys):
	return type(data) == type(0) and data < pow(2,16)
def check_int32 (data,root,keys):
	return type(data) == type(0) and data < pow(2,32)
def check_string (data,root,keys):
	return type(data) == type(u'')
def check_list (data,root,keys):
	return type(data) == type([])
def check_dict (data,root,keys):
	return type(data) == type({})
def check_ip (data,root,keys):
	return check_ipv4(data,root,keys) or check_ipv6(data,root,key)
def check_ipv4 (data,root,keys):  # XXX: improve
	return type(data) == type(u'') and data.count('.') == 3
def check_ipv6 (data,root,keys):  # XXX: improve
	return type(data) == type(u'') and ':' in data
def check_reference (data,root,keys):
	return True


CHECK = {
	TYPE.boolean : check_boolean,
	TYPE.int8 : check_int8,
	TYPE.int16 : check_int16,
	TYPE.int32 : check_int32,
	TYPE.string : check_string,
	TYPE.list : check_list,
	TYPE.dictionary : check_dict,
	TYPE.ip : check_ip,
	TYPE.ipv4 : check_ipv4,
	TYPE.ipv6 : check_ipv6,
	TYPE.reference : check_reference,
}

class OrderedDict (dict):
	def __init__(self, *args, **kwargs):
		dict.__init__(self, *args, **kwargs)
		self._order = self.keys()

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

definition = (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
	('exabgp' , (TYPE.int8, PRESENCE.mandatory, [4,])),
	('neighbor' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
		('tcp' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
			('local' , (TYPE.ip, PRESENCE.mandatory , None)),
			('peer' , (TYPE.ip, PRESENCE.mandatory , None)),
			('ttl-security' , (TYPE.boolean, PRESENCE.optional , None)),
			('md5' , (TYPE.string, PRESENCE.optional , None)),
		)))),
		('api' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			('<*>' , (TYPE.list, PRESENCE.mandatory, ['neighbor-changes','send-packets','receive-packets','receive-routes'])),
		)))),
		('session' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
			('router-id' , (TYPE.ipv4, PRESENCE.mandatory , None)),
			('hold-time' , (TYPE.int16, PRESENCE.mandatory , None)),
			('asn' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
				('local' , (TYPE.int32, PRESENCE.mandatory , None)),
				('peer' , (TYPE.int32, PRESENCE.mandatory , None)),
			)))),
			('capability' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
				('family' , (TYPE.dictionary, PRESENCE.mandatory, OrderedDict((
					('inet'  , (TYPE.list, PRESENCE.optional, ['unicast','multicast','nlri-mpls','mpls-vpn','flow-vpnv4','flow'])),
					('inet4' , (TYPE.list, PRESENCE.optional, ['unicast','multicast','nlri-mpls','mpls-vpn','flow-vpnv4','flow'])),
					('inet6' , (TYPE.list, PRESENCE.optional, ['unicast','flow'])),
					('alias' , (TYPE.string, PRESENCE.optional, ['all','minimal'])),
				)))),
				('asn4' , (TYPE.int32, PRESENCE.optional , None)),
				('route-refresh' , (TYPE.boolean, PRESENCE.optional , None)),
				('graceful-restart' , (TYPE.boolean, PRESENCE.optional , None)),
				('multi-session' , (TYPE.boolean, PRESENCE.optional , None)),
				('add-path' , (TYPE.boolean, PRESENCE.optional , None)),
			))))
		)))),
		('announce' , (TYPE.references, PRESENCE.optional,'attributes.updates.prefix.*'))
	)))),
	('api' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
		('<*>' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			('encoder' , (TYPE.string, PRESENCE.optional, ['json','text'])),
			('program' , (TYPE.string, PRESENCE.mandatory, '<*>')),
		)))),
	)))),
	('attributes' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
	)))),
	('flow' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
		('filtering-condition' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
			('<*>' , (TYPE.dictionary, PRESENCE.optional, OrderedDict((
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

# 	'attributes': {
# 		'normal-ebgp-attributes': {
# 			'origin': 'igp',
# 			'as-path': [ 3356, 1239, 38040, 9737 ],
# 			'local-preference': 500,
# 			'aggregator': '10.0.0.1',
# 			'atomic-aggregate': false,
# 			'originator-id': '10.0.0.1',
# 			'med': 10,
# 			'community': [[3356,2], [3356,22], [3356,86], [3356,500], [3356,666], [3356,2064]],
# 			'cluster-list': [],
# 			'extended-community': []
# 		},
# 		'simple-attributes': {
# 			'next-hop': '212.73.207.153',
# 			'origin': 'igp',
# 			'as-path': [ 3356, 1239, 38040, 9737 ],
# 			'local-preference': 500,
# 			'aggregator': '10.0.0.1',
# 			'atomic-aggregate': false,
# 			'originator-id': '10.0.0.1',
# 			'med': 10,
# 			'community': [[3356,2], [3356,22], [3356,86], [3356,500], [3356,666], [3356,2064]],
# 			'cluster-list': [],
# 			'extended-community': []
# 		}
# 	},
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

def validate (root,json,definition,keys=[]):
	kind,presence,compare = definition

	# ignore missing optional elements
	if presence == PRESENCE.optional and not json:
		print "not present"
		return True

	# for dictionary check all the elements inside
	if kind == TYPE.dictionary:
		keys = compare.keys()
		wildcard = True

		while keys:
			key = keys.pop()
			if key.startswith('_'):
				print "skipping", key
				continue

			if type(json) != type({}):
				print "bad data, not a dict", json
				return False

			if key == '<*>' and wildcard:
				keys = json.keys()
				wildcard = False
				continue

			print "checking", key
			if not validate(root,json.get(key,None),compare[key],keys + [key]):
				return False
		return True

	# check that the value is well in the list
	if not CHECK[kind](json,definition[2],keys):
		import pdb; pdb.set_trace()
		return False

	return True

print validate(json,json,definition)

