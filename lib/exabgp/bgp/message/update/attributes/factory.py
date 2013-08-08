# encoding: utf-8
"""
factory.py

Created by Thomas Mangin on 2010-01-16.
Copyright (c) 2009-2013  Exa Networks. All rights reserved.
"""

from exabgp.bgp.message.update.attributes import Attributes
from exabgp.bgp.message.update.attribute.id import AttributeID as AID
from exabgp.bgp.message.notification import Notify

def AttributesFactory (nlriFactory,negotiated,data):
	try:
		# caching and checking the last attribute parsed as nice implementation group them :-)
		if Attributes.cached and Attributes.cached.cacheable and data.startswith(Attributes.cached.prefix):
			attributes = Attributes.cached
			data = data[len(attributes.prefix):]
		else:
			attributes = Attributes()
			Attributes.cached = attributes

		# XXX: hackish for now
		attributes.mp_announce = []
		attributes.mp_withdraw = []

		attributes.negotiated = negotiated
		attributes.nlriFactory = nlriFactory
		attributes.factory(data)
		if AID.AS_PATH in attributes and AID.AS4_PATH in attributes:
			attributes.merge_attributes()
		return attributes
	except IndexError:
		raise Notify(3,2,data)
