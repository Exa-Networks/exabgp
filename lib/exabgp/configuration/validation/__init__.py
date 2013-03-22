# encoding: utf-8
'''
validation.py

Created by Thomas Mangin on 2013-03-18.
Copyright (c) 2009-2013 Exa Networks. All rights reserved.
'''

__all__ = ["validation", "ValidationError"]

DEBUG = False

from exabgp.structure.ordereddict import OrderedDict
from exabgp.configuration.validation import check

TYPE=check.TYPE
PRESENCE=check.PRESENCE

class ValidationError (Exception):
	pass

_attributes = OrderedDict((
	('next-hop', (TYPE.string, PRESENCE.optional, '', check.ipv4)),
	('origin' , (TYPE.string, PRESENCE.optional, '', ['igp','egp','incomplete'])),
	('as-path' , (TYPE.list, PRESENCE.optional, '', check.aspath)),
	('local-preference', (TYPE.integer, PRESENCE.optional, '', check.uint32)),
	('med', (TYPE.integer, PRESENCE.optional, '', check.uint32)),
	('aggregator' , (TYPE.string , PRESENCE.optional, '', check.ipv4)),
	('aggregator-id' , (TYPE.string , PRESENCE.optional, '', check.ipv4)),
	('atomic-aggregate' , (TYPE.boolean , PRESENCE.optional, '', check.nop)),
	('community' , (TYPE.list , PRESENCE.optional, '', check.community)),
	# TODO: 'cluster-list'
	# TODO: 'extended-community'
	# TODO: more ?
))

_definition = (TYPE.dictionary, PRESENCE.mandatory, '', OrderedDict((
	('exabgp' , (TYPE.integer, PRESENCE.mandatory, '', [3,4,])),
	('neighbor' , (TYPE.dictionary, PRESENCE.mandatory, '', OrderedDict((
		('tcp' , (TYPE.dictionary, PRESENCE.mandatory, '', OrderedDict((
			('local' , (TYPE.string, PRESENCE.mandatory, '', check.ip)),
			('peer' , (TYPE.string, PRESENCE.mandatory, '', check.ip)),
			('ttl-security' , (TYPE.integer, PRESENCE.optional, '', check.uint8)),
			('md5' , (TYPE.string, PRESENCE.optional, '', check.nop))
		)))),
		('api' , (TYPE.dictionary, PRESENCE.optional, 'api', OrderedDict((
			('<*>' , (TYPE.list, PRESENCE.mandatory, '', ['neighbor-changes','send-packets','receive-packets','receive-routes'])),
		)))),
		('session' , (TYPE.dictionary, PRESENCE.mandatory, '', OrderedDict((
			('router-id' , (TYPE.string, PRESENCE.mandatory, '', check.ipv4)),
			('hold-time' , (TYPE.integer, PRESENCE.mandatory, '', check.uint16)),
			('asn' , (TYPE.dictionary, PRESENCE.mandatory, '', OrderedDict((
				('local' , (TYPE.integer, PRESENCE.mandatory, '', check.uint32)),
				('peer' , (TYPE.integer, PRESENCE.mandatory, '', check.uint32)),
			)))),
			('capability' , (TYPE.dictionary, PRESENCE.mandatory, '', OrderedDict((
				('family' , (TYPE.dictionary, PRESENCE.mandatory, '', OrderedDict((
					('inet'  , (TYPE.list, PRESENCE.optional, '', ['unicast','multicast','nlri-mpls','mpls-vpn','flow-vpnv4','flow'])),
					('inet4' , (TYPE.list, PRESENCE.optional, '', ['unicast','multicast','nlri-mpls','mpls-vpn','flow-vpnv4','flow'])),
					('inet6' , (TYPE.list, PRESENCE.optional, '', ['unicast','flow'])),
					('alias' , (TYPE.string, PRESENCE.optional, '', ['all','minimal'])),
				)))),
				('asn4' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('route-refresh' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('graceful-restart' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('multi-session' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('add-path' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
			))))
		)))),
		('announce' , (TYPE.list, PRESENCE.optional, ['updates.prefix','updates.flow'], check.string)),
	)))),
	('api' , (TYPE.dictionary, PRESENCE.optional, 'api', OrderedDict((
		('<*>' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
			('encoder' , (TYPE.string, PRESENCE.optional, '', ['json','text'])),
			('program' , (TYPE.string, PRESENCE.mandatory, '', check.nop)),
		)))),
	)))),
	('attributes' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
		('<*>' , (TYPE.dictionary, PRESENCE.optional, '', _attributes)),
	)))),
	('flow' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
		('filtering-condition' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
			('<*>' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
				('source' , (TYPE.list|TYPE.string, PRESENCE.optional, '', check.flow_ipv4_range)),
				('destination' , (TYPE.list|TYPE.string, PRESENCE.optional, '', check.flow_ipv4_range)),
				('port' , (TYPE.list, PRESENCE.optional, '', check.flow_port)),
				('source-port' , (TYPE.list, PRESENCE.optional, '', check.flow_port)),
				('destination-port' , (TYPE.list, PRESENCE.optional, '', check.flow_port)),
				('protocol' , (TYPE.list|TYPE.string, PRESENCE.optional, '', ['udp','tcp'])),  # and value of protocols ...
				('packet-length' , (TYPE.list, PRESENCE.optional, '', check.flow_length)),
				('packet-fragment' , (TYPE.list|TYPE.string, PRESENCE.optional, '', ['not-a-fragment', 'dont-fragment', 'is-fragment', 'first-fragment', 'last-fragment'])),
				('icmp-type' , (TYPE.list|TYPE.string, PRESENCE.optional, '', ['unreachable', 'echo-request', 'echo-reply'])),
				# TODO : missing type
				('icmp-code' , (TYPE.list|TYPE.string, PRESENCE.optional, '', ['host-unreachable', 'network-unreachable'])),
				# TODO : missing  code
				('tcp-flags' , (TYPE.list|TYPE.string, PRESENCE.optional, '', ['fin', 'syn', 'rst', 'push', 'ack', 'urgent'])),
				('dscp' , (TYPE.list|TYPE.integer, PRESENCE.optional, '', check.dscp)),
				# TODO: MISSING SOME MORE ?
			)))),
		)))),
		('filtering-action' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
			('<*>' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
				('rate-limit' , (TYPE.integer, PRESENCE.optional, '', check.float)),
				('discard' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('redirect' , (TYPE.list, PRESENCE.optional, '', check.redirect)),
				('community' , (TYPE.list , PRESENCE.optional, '', check.community)),
			)))),
		)))),
	)))),
	('updates' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
		('prefix' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
			('<*>' , (TYPE.dictionary, PRESENCE.optional, 'attributes', OrderedDict((  # name of route
				('<*>' , (TYPE.dictionary, PRESENCE.mandatory, '', OrderedDict((  # name of attributes referenced
					('<*>' , (TYPE.dictionary, PRESENCE.optional, '', _attributes)),  # prefix
				)))),
			)))),
		)))),
		('flow' , (TYPE.dictionary, PRESENCE.optional, '', OrderedDict((
			('<*>' , (TYPE.dictionary, PRESENCE.optional, 'flow.filtering-condition', OrderedDict((  # name of the dos
				('<*>' , (TYPE.string, PRESENCE.mandatory, 'flow.filtering-action', check.nop)),
			)))),
		)))),
	)))),
)))


def _reference (root,references,json):
	if not references:
		return True

	ref = references if check.list(references) else [references,]
	jsn = json if check.list(json) else json.keys() if check.dict(json) else [json,]

	valid = []
	for reference in ref:
		compare = root
		for path in reference.split('.'):
			compare = compare.get(path,{})
		# prevent name conflict where we can not resolve which object is referenced.
		add = compare.keys()
		for k in add:
			if k in valid:
				return False
		valid.extend(add)

	for option in jsn:
		if not option in valid:
			return False

	return True

def _validate (root,json,definition,location=[]):
	kind,presence,references,contextual = definition

	# kind, the type of data possible
	# presence, indicate if the data is mandatory or not
	# reference, if the name is a reference to another key
	# valid, a subdefinition or the check to run

	if kind == TYPE.error:
		return False

	# ignore missing optional elements
	if not json:
		#print ' / '.join(location), 'not present'
		return presence == PRESENCE.optional

	# check that the value of the right type
	if not check.kind(kind,json):
		return False

	# for dictionary check all the elements inside
	if kind & TYPE.dictionary and check.dict(json):
		subdefinition = contextual
		keys = subdefinition.keys()
		wildcard = True

		while keys:
			key = keys.pop()
			if key.startswith('_'):
				continue

			if type(json) != type({}):
				print "bad data, not a dict", json
				return False

			if key == '<*>' and wildcard:
				keys = json.keys()
				wildcard = False
				continue

			if not _reference (root,references,json):
				return False

			if DEBUG: print "  "*len(location) + key
			star = subdefinition.get('<*>',(TYPE.error,None,'','','problem validating configuration',None))
			subtest = subdefinition.get(key,star)
			if not _validate(root,json.get(key,None),subtest,location + [key]):
				return False

	# for list check all the element inside
	elif kind & TYPE.list and check.list(json):
		test = contextual
		# This is a function
		if hasattr(test, '__call__'):
			for data in json:
				if not test(data):
					return False
		# This is a list of valid option
		elif type(test) == type([]):
			for data in json:
				if not data in test:
					return False
		# no idea what the data is - so something is wrong with the program
		else:
			return False

	# for non container object check the value
	else:
		test = contextual
		# check that the value of the data
		if hasattr(test, '__call__'):
			if not test(json):
				return False
		# a list of valid option
		elif type(test) == type([]):
			if not json in test:
				return False
		else:
			return False

	if not _reference (root,references,json):
		return False

	return True


def validation (json):
	return _validate(json,json,_definition)

def main ():
	DEBUG = True
	from exabgp.configuration.loader import read
	try:
		validation(
			read('/Users/thomas/source/hg/exabgp/tip/QA/configuration/first.exa')
		)
		print "validation succesful"
	except ValidationError,e:
		print "validation failed", str(e)

if __name__ == '__main__':
	main()
