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
	type_error = 'the data is of the wrong type'
	internal_error = 'invalid configuration definition (internal error)'
	configuration_error = 'missing configuration information'

	def __init__ (self,location,message):
		self.location = location
		self.message = message

	def __str__ (self):
		return ','.join(self.location) + ' : ' + self.message

_attributes = OrderedDict((
	('next-hop', (TYPE.string, PRESENCE.optional, '', check.ipv4)),
	('origin' , (TYPE.string, PRESENCE.optional, '', ['igp','egp','incomplete'])),
	('as-path' , (TYPE.array, PRESENCE.optional, '', check.aspath)),
	('as-sequence' , (TYPE.array, PRESENCE.optional, '', check.assequence)),
	('local-preference', (TYPE.integer, PRESENCE.optional, '', check.localpreference)),
	('med', (TYPE.integer, PRESENCE.optional, '', check.med)),
	('aggregator' , (TYPE.string , PRESENCE.optional, '', check.ipv4)),
	('aggregator-id' , (TYPE.string , PRESENCE.optional, '', check.ipv4)),
	('atomic-aggregate' , (TYPE.boolean , PRESENCE.optional, '', check.nop)),
	('community' , (TYPE.array , PRESENCE.optional, '', check.community)),
	('extended-community' , (TYPE.array , PRESENCE.optional, '', check.extendedcommunity)),
	('label' , (TYPE.array , PRESENCE.optional, '', check.label)),
	('cluster-list' , (TYPE.array , PRESENCE.optional, '', check.clusterlist)),
	('originator-id' , (TYPE.string , PRESENCE.optional, '', check.originator)),
	('path-information' , (TYPE.string|TYPE.integer , PRESENCE.optional, '', check.pathinformation)),
	('route-distinguisher' , (TYPE.string , PRESENCE.optional, '', check.distinguisher)),
	('split' , (TYPE.integer , PRESENCE.optional, '', check.split)),
	('watchdog' , (TYPE.string , PRESENCE.optional, '', check.watchdog)),
	('withdrawn' , (TYPE.boolean , PRESENCE.optional, '', check.nop)),
))

_definition = (TYPE.object, PRESENCE.mandatory, '', OrderedDict((
	('exabgp' , (TYPE.integer, PRESENCE.mandatory, '', [3,4,])),
	('neighbor' , (TYPE.object, PRESENCE.mandatory, '', OrderedDict((
		('tcp' , (TYPE.object, PRESENCE.mandatory, '', OrderedDict((
			('local' , (TYPE.string, PRESENCE.mandatory, '', check.ip)),
			('peer' , (TYPE.string, PRESENCE.mandatory, '', check.ip)),
			('ttl-security' , (TYPE.integer, PRESENCE.optional, '', check.uint8)),
			('md5' , (TYPE.string, PRESENCE.optional, '', check.md5))
		)))),
		('api' , (TYPE.object, PRESENCE.optional, 'api', OrderedDict((
			('<*>' , (TYPE.array, PRESENCE.mandatory, '', ['neighbor-changes','send-packets','receive-packets','receive-routes'])),
		)))),
		('session' , (TYPE.object, PRESENCE.mandatory, '', OrderedDict((
			('router-id' , (TYPE.string, PRESENCE.mandatory, '', check.ipv4)),
			('hold-time' , (TYPE.integer, PRESENCE.mandatory, '', check.uint16)),
			('asn' , (TYPE.object, PRESENCE.mandatory, '', OrderedDict((
				('local' , (TYPE.integer, PRESENCE.mandatory, '', check.uint32)),
				('peer' , (TYPE.integer, PRESENCE.mandatory, '', check.uint32)),
			)))),
			('capability' , (TYPE.object, PRESENCE.mandatory, '', OrderedDict((
				('family' , (TYPE.object, PRESENCE.mandatory, '', OrderedDict((
					('inet'  , (TYPE.array, PRESENCE.optional, '', ['unicast','multicast','nlri-mpls','mpls-vpn','flow-vpnv4','flow'])),
					('inet4' , (TYPE.array, PRESENCE.optional, '', ['unicast','multicast','nlri-mpls','mpls-vpn','flow-vpnv4','flow'])),
					('inet6' , (TYPE.array, PRESENCE.optional, '', ['unicast','flow'])),
					('alias' , (TYPE.string, PRESENCE.optional, '', ['all','minimal'])),
				)))),
				('asn4' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('route-refresh' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('graceful-restart' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('multi-session' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('add-path' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
			))))
		)))),
		('announce' , (TYPE.array, PRESENCE.optional, ['updates,prefix','updates,flow'], check.string)),
	)))),
	('api' , (TYPE.object, PRESENCE.optional, 'api', OrderedDict((
		('<*>' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
			('encoder' , (TYPE.string, PRESENCE.optional, '', ['json','text'])),
			('program' , (TYPE.string, PRESENCE.mandatory, '', check.nop)),
		)))),
	)))),
	('attributes' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
		('<*>' , (TYPE.object, PRESENCE.optional, '', _attributes)),
	)))),
	('flow' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
		('filtering-condition' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
			('<*>' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
				('source' , (TYPE.array|TYPE.string, PRESENCE.optional, '', check.flow_ipv4_range)),
				('destination' , (TYPE.array|TYPE.string, PRESENCE.optional, '', check.flow_ipv4_range)),
				('port' , (TYPE.array, PRESENCE.optional, '', check.flow_port)),
				('source-port' , (TYPE.array, PRESENCE.optional, '', check.flow_port)),
				('destination-port' , (TYPE.array, PRESENCE.optional, '', check.flow_port)),
				('protocol' , (TYPE.array|TYPE.string, PRESENCE.optional, '', ['udp','tcp'])),  # and value of protocols ...
				('packet-length' , (TYPE.array, PRESENCE.optional, '', check.flow_length)),
				('packet-fragment' , (TYPE.array|TYPE.string, PRESENCE.optional, '', ['not-a-fragment', 'dont-fragment', 'is-fragment', 'first-fragment', 'last-fragment'])),
				('icmp-type' , (TYPE.array|TYPE.string, PRESENCE.optional, '', ['unreachable', 'echo-request', 'echo-reply'])),
				# TODO : missing type
				('icmp-code' , (TYPE.array|TYPE.string, PRESENCE.optional, '', ['host-unreachable', 'network-unreachable'])),
				# TODO : missing  code
				('tcp-flags' , (TYPE.array|TYPE.string, PRESENCE.optional, '', ['fin', 'syn', 'rst', 'push', 'ack', 'urgent'])),
				('dscp' , (TYPE.array|TYPE.integer, PRESENCE.optional, '', check.dscp)),
				# TODO: MISSING SOME MORE ?
			)))),
		)))),
		('filtering-action' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
			('<*>' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
				('rate-limit' , (TYPE.integer, PRESENCE.optional, '', check.float)),
				('discard' , (TYPE.boolean, PRESENCE.optional, '', check.nop)),
				('redirect' , (TYPE.array, PRESENCE.optional, '', check.redirect)),
				('community' , (TYPE.array , PRESENCE.optional, '', check.community)),
			)))),
		)))),
	)))),
	('updates' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
		('prefix' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
			('<*>' , (TYPE.object, PRESENCE.optional, 'attributes', OrderedDict((  # name of route
				('<*>' , (TYPE.object, PRESENCE.mandatory, '', OrderedDict((  # name of attributes referenced
					('<*>' , (TYPE.object, PRESENCE.optional, '', _attributes)),  # prefix
				)))),
			)))),
		)))),
		('flow' , (TYPE.object, PRESENCE.optional, '', OrderedDict((
			('<*>' , (TYPE.object, PRESENCE.optional, 'flow,filtering-condition', OrderedDict((  # name of the dos
				('<*>' , (TYPE.string, PRESENCE.mandatory, 'flow,filtering-action', check.nop)),
			)))),
		)))),
	)))),
)))


def _reference (root,references,json,location):
	if not references:
		return

	ref = references if check.array(references) else [references,]
	jsn = json if check.array(json) else json.keys() if check.object(json) else [json,]

	valid = []
	for reference in ref:
		compare = root
		for path in reference.split(','):
			compare = compare.get(path,{})
		# prevent name conflict where we can not resolve which object is referenced.
		add = compare.keys()
		for k in add:
			if k in valid:
				raise ValidationError(location, "duplicate reference in " % ', '.join(references))

				return False
		valid.extend(add)

	for option in jsn:
		if not option in valid:
			destination = ' or '.join(references) if type(references) == type ([]) else references
			raise ValidationError(location, "the referenced data in %s is not present" % destination)

	return True

def _validate (root,json,definition,location=[]):
	kind,presence,references,contextual = definition

	# ignore missing optional elements
	if not json:
		if presence == PRESENCE.mandatory:
			raise ValidationError(location, ValidationError.configuration_error)
		return

	# check that the value of the right type
	if not check.kind(kind,json):
		raise ValidationError(location, ValidationError.type_error)

	# for object check all the elements inside
	if kind & TYPE.object and check.object(json):
		subdefinition = contextual
		keys = subdefinition.keys()
		wildcard = True

		while keys:
			key = keys.pop()
			if key.startswith('_'):
				continue

			if type(json) != type({}):
				raise ValidationError(location, ValidationError.configuration_error)

			if key == '<*>' and wildcard:
				keys = json.keys()
				wildcard = False
				continue

			if DEBUG: print "  "*len(location) + key
			_reference (root,references,json,location)

			star = subdefinition.get('<*>',None)
			subtest = subdefinition.get(key,star)
			if subtest is None:
				raise ValidationError(location, ValidationError.configuration_error)
			_validate(root,json.get(key,None),subtest,location + [key])

	# for list check all the element inside
	elif kind & TYPE.array and check.array(json):
		test = contextual
		# This is a function
		if hasattr(test, '__call__'):
			for data in json:
				if not test(data):
					raise ValidationError(location, ValidationError.type_error)
		# This is a list of valid option
		elif type(test) == type([]):
			for data in json:
				if not data in test:
					raise ValidationError(location, ValidationError.type_error)
		# no idea what the data is - so something is wrong with the program
		else:
			raise ValidationError(location,ValidationError.internal_error)

	# for non container object check the value
	else:
		test = contextual
		# check that the value of the data
		if hasattr(test, '__call__'):
			if not test(json):
				raise ValidationError(location, ValidationError.type_error)
		# a list of valid option
		elif type(test) == type([]):
			if not json in test:
				raise ValidationError(location, ValidationError.type_error)
		else:
			raise ValidationError(location,ValidationError.internal_error)

	_reference (root,references,json,location)



def validation (json):
	_validate(json,json,_definition)

def main ():
	global DEBUG
	DEBUG = True
	from exabgp.configuration.loader import read
	try:
		validation(
			read('/Users/thomas/source/hg/exabgp/tip/QA/configuration/first.exa')
		)
		print "validation succesful"
	except ValidationError,e:
		print "validation failed", str(e)
		raise

if __name__ == '__main__':
	main()
