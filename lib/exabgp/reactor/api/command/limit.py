# encoding: utf-8
"""
command/limit.py

Created by Thomas Mangin on 2017-07-01.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

import re


def extract_neighbors (command):
	"""Return a list of neighbor definition : the neighbor definition is a list of string which are in the neighbor indexing string"""
	# This function returns a list and a string
	# The first list contains parsed neighbor to match against our defined peers
	# The string is the command to be run for those peers
	# The parsed neighbor is a list of the element making the neighbor string so each part can be checked against the neighbor name

	returned = []
	neighbor,remaining = command.split(' ',1)
	if neighbor != 'neighbor':
		return [],command

	ip,command = remaining.split(' ',1)
	definition = ['neighbor %s' % (ip)]

	while True:
		try:
			key,value,remaining = command.split(' ',2)
		except ValueError:
			key,value = command.split(' ',1)
		if key == ',':
			returned.append(definition)
			_,command = command.split(' ',1)
			definition = []
			continue
		if key not in ['neighbor','local-ip','local-as','peer-as','router-id','family-allowed']:
			if definition:
				returned.append(definition)
			break
		definition.append('%s %s' % (key,value))
		command = remaining

	return returned,command


def match_neighbor (description, name):
	for string in description:
		if re.search(r'(^|\s)%s($|\s|,)' % re.escape(string), name) is None:
			return False
	return True


def match_neighbors (peers,descriptions):
	"""Return the sublist of peers matching the description passed, or None if no description is given"""
	if not descriptions:
		return peers.keys()

	returned = []
	for key in peers:
		for description in descriptions:
			if match_neighbor(description,key):
				if key not in returned:
					returned.append(key)
	return returned
