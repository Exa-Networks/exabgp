# encoding: utf-8
from exabgp.protocol.family import AFI

from exabgp.protocol.ip import IP
from exabgp.bgp.message.update.attribute import NextHopSelf

from exabgp.bgp.message.update.nlri import VPLS
from exabgp.bgp.message.update.attribute import Attributes
from exabgp.rib.change import Change
from exabgp.bgp.message.update.nlri.bgpls.srv6sid import LocalNodeDescriptor, SRv6SIDDescriptor, MultiTopology, \
    ServiceChaining, OpaqueMetadata, LocalNodeDescriptorSub


def protocol_id(tokeniser):
    return int(tokeniser())

def identifier(tokeniser):
    return int(tokeniser())

def local_node_descriptor(tokeniser):
    value = tokeniser()
    if value == '(':
        as_number = tokeniser()
        bgp_ls_identifier = tokeniser()
        router_id = tokeniser()
        confederation_member = tokeniser()
        tokeniser()
        return LocalNodeDescriptor([
            LocalNodeDescriptorSub(512, as_number),
            LocalNodeDescriptorSub(513, bgp_ls_identifier),
            LocalNodeDescriptorSub(516, router_id),
            LocalNodeDescriptorSub(517, confederation_member)
        ])
    else:
        raise ValueError('invalid local node descriptor')

def srv6_sid_information(tokeniser):
    srv6_sid_info = []

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == ']':
                break
            srv6_sid_info.append(SRv6SIDDescriptor(value))
    else:
        srv6_sid_info.append(SRv6SIDDescriptor(value))

    return srv6_sid_info

def multi_topologies(tokeniser):
    mt_ids = []

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == '(':
                ids = []
                while True:
                    value = tokeniser()
                    if value == ')':
                        break
                    ids.append(int(value))
                mt_ids.append(MultiTopology(ids))
            elif value == ']':
                break
    else:
        mt_ids.append(MultiTopology([int(value)]))
    return mt_ids

def service_chainings(tokeniser):
    service_chainings = []

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == '(':
                service_type = tokeniser()
                flags = tokeniser()
                traffic_type = tokeniser()
                reserved = tokeniser()
                tokeniser()
                service_chainings.append(ServiceChaining(service_type, flags, traffic_type, reserved))
            elif value == ']':
                break
    return service_chainings

def opaque_metadata(tokeniser):
    opaque_metadata = []

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == '(':
                opaque_type = tokeniser()
                flags = tokeniser()
                metadata = tokeniser()
                tokeniser()
                opaque_metadata.append(OpaqueMetadata(opaque_type, flags, metadata))
            elif value == ']':
                break
    return opaque_metadata
