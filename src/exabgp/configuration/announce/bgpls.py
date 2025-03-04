# encoding: utf-8
"""
announce/vpn.py

Created by Thomas Mangin on 2017-07-09.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from exabgp.rib.change import Change

from exabgp.protocol.family import AFI
from exabgp.protocol.family import SAFI

from exabgp.bgp.message.update.attribute import Attributes

from exabgp.configuration.announce import ParseAnnounce

from exabgp.configuration.bgpls.parser import protocol_id
from exabgp.configuration.bgpls.parser import identifier
from exabgp.configuration.bgpls.parser import local_node_descriptor
from exabgp.configuration.bgpls.parser import srv6_sid_information
from exabgp.configuration.bgpls.parser import multi_topologies
from exabgp.configuration.bgpls.parser import service_chainings
from exabgp.configuration.bgpls.parser import opaque_metadata
from exabgp.bgp.message.update.nlri.bgpls.srv6sid import SRv6SID


class AnnounceBGPLSSAFI(ParseAnnounce):
    definition = [
        'protocol-id <protocol id; 8 bits number>',
        'identifier <identifier; 64 bits number>',
        'local-node-descriptor ( <asn> <bgp ls identifier; 32 bits number> <ospf area id; 32 bits number> <ip> )',
        'srv6-sid-information [ <ipv6>.. ]',
        'multi-topologies [ ( <mt id; 16 bits number>.. ).. ]',
        'service-chainings [ ( <service type; 16 bits number> <flags; 8 bits number> <traffic type; 8 bits number> <reserved; 16 bits number> ).. ]',
        'opaque-metadata [ ( <length; 16 bits number> <opaque type; 16 bits number> <flags; 8 bits number> <value; string> ).. ]',
    ]

    syntax = 'bgp-ls %s\n' % '  '.join(definition)

    known = {
        'protocol-id': protocol_id,
        'identifier': identifier,
        'local-node-descriptor': local_node_descriptor,
        'srv6-sid-information': srv6_sid_information,
        'multi-topologies': multi_topologies,
        'service-chainings': service_chainings,
        'opaque-metadata': opaque_metadata,
    }

    action = {
        'protocol-id': 'nlri-set',
        'identifier': 'nlri-set',
        'local-node-descriptor': 'nlri-set',
        'srv6-sid-information': 'nlri-set',
        'multi-topologies': 'nlri-set',
        'service-chainings': 'nlri-set',
        'opaque-metadata': 'nlri-set',
    }

    assign = {
        'protocol-id': 'protocol_id',
        'identifier': 'identifier',
        'local-node-descriptor': 'local_node_descriptor',
        'srv6-sid-information': 'srv6_sid_information',
        'multi-topologies': 'multi_topologies',
        'service-chainings': 'service_chainings',
        'opaque-metadata': 'opaque_metadata',
    }

    name = 'bgp-ls'
    afi = None

    def __init__(self, tokeniser, scope, error):
        ParseAnnounce.__init__(self, tokeniser, scope, error)

    def clear(self):
        return True

    def post(self):
        return self._check()

    @staticmethod
    def check(change, afi):
        return True


def bgpls(tokeniser, afi, safi):
    change = Change(SRv6SID(None, None, None), Attributes())

    while True:
        command = tokeniser()
        if not command:
            break

        action = AnnounceBGPLSSAFI.action[command]
        if 'nlri-set' in action:
            change.nlri.assign(AnnounceBGPLSSAFI.assign[command], AnnounceBGPLSSAFI.known[command](tokeniser))
        elif 'attribute-add' in action:
            change.attributes.add(AnnounceBGPLSSAFI.known[command](tokeniser))
        else:
            raise ValueError('bgp-ls: unknown command "%s"' % command)

    change.nlri._pack()
    change.nlri.pack()
    return [
        change,
    ]


@ParseAnnounce.register('bgp-ls', 'extend-name', 'bgp-ls')
def bgpls_bgpls(tokeniser):
    return bgpls(tokeniser, AFI.bgpls, SAFI.bgp_ls)
