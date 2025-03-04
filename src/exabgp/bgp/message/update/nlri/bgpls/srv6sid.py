from struct import pack, unpack
from exabgp.bgp.message.update.nlri.bgpls import BGPLS
from exabgp.bgp.message import Action
from exabgp.protocol.ip import IP, IPv6
from exabgp.bgp.message.update.nlri.bgpls.tlvs.multitopology import MultiTopology
from exabgp.bgp.message.update.nlri.bgpls.tlvs.servicechaining import ServiceChaining
from exabgp.bgp.message.update.nlri.bgpls.tlvs.opaquemetadata import OpaqueMetadata
from exabgp.protocol.ip import NoNextHop

# https://www.rfc-editor.org/rfc/rfc9514.html#name-srv6-sid-nlri
@BGPLS.register
class SRv6SID(BGPLS):
    CODE = 6
    NAME = 'bgpls-srv6-sid'
    SHORT_NAME = 'SRV6_SID'

    def __init__(
            self,
            protocol_id,
            identifier,
            local_node_descriptor,
            srv6_sid_information=[],
            multi_topologies=[],
            service_chainings=[],
            opaque_metadata=[],
            packed=None
        ):
        BGPLS.__init__(self, action=Action.ANNOUNCE, addpath=None)
        self.protocol_id = protocol_id
        self.identifier = identifier
        self.local_node_descriptor = local_node_descriptor
        self.srv6_sid_information = srv6_sid_information
        self.multi_topologies = multi_topologies
        self.service_chainings = service_chainings
        self.opaque_metadata = opaque_metadata
        # self.nexthop = NoNextHop
        self.nexthop = IPv6('::1')
        self._packed = packed

    def _pack(self, packed=None):
        if self._packed:
            return self._packed

        if packed:
            self._packed = packed
            return packed

        self._packed = (
            pack('!B', self.protocol_id) +
            pack('!Q', self.identifier) +
            self.local_node_descriptor.pack() +
            b''.join(map(lambda x: x.pack(), self.srv6_sid_information)) +
            b''.join(map(lambda x: x.pack(), self.multi_topologies)) +
            b''.join(map(lambda x: x.pack(), self.service_chainings)) +
            b''.join(map(lambda x: x.pack(), self.opaque_metadata))
        )
        return self._packed

    @classmethod
    def unpack_nlri(cls, data, rd):
        protocol_id = unpack('!B', data[:1])[0]
        identifier = unpack('!Q', data[1:9])[0]
        local_node_descriptor = LocalNodeDescriptor.unpack(data[9:])
        multi_topologies = []
        srv6_sid_information = []
        service_chainings = []
        opaque_metadata = []
        tlvs = data[9+16:]

        while tlvs:
            tlv_type, tlv_length = unpack('!HH', tlvs[:4])
            value = tlvs[4 : 4 + tlv_length]
            tlvs = tlvs[4 + tlv_length :]

            if tlv_type == 263:
                multi_topologies.append(MultiTopology.unpack(value))
                continue

            if tlv_type == 518:
                srv6_sid_information.append(SRv6SIDDescriptor.unpack(value))
                continue

            if tlv_type == 65000:
                service_chainings.append(ServiceChaining.unpack(value))
                continue

            if tlv_type == 65001:
                opaque_metadata.append(OpaqueMetadata.unpack(tlv_length, value))
                continue

        return cls(
            protocol_id=protocol_id,
            identifier=identifier,
            local_node_descriptor=local_node_descriptor,
            srv6_sid_information=srv6_sid_information,
            multi_topologies=multi_topologies,
            service_chainings=service_chainings,
            opaque_metadata=opaque_metadata
        )

    def __eq__(self, other):
        return (
            isinstance(other, SRv6SID)
            and self.protocol_id == other.protocol_id
            and self.identifier == other.identifier
            and self.local_node_descriptor == other.local_node_descriptor
            and self.srv6_sid_information == other.srv6_sid_information
            and self.multi_topologies == other.multi_topologies
            and self.service_chainings == other.service_chainings
            and self.opaque_metadata == other.opaque_metadata
        )

    def __str__(self):
        return (
            f"SRv6SID(protocol_id={self.protocol_id}, identifier={self.identifier}, "
            f"local_node_descriptor={self.local_node_descriptor}, srv6_sid_information={self.srv6_sid_information}, "
            f"multi_topologies={self.multi_topologies}, service_chainings={self.service_chainings}, "
            f"opaque_metadata={self.opaque_metadata})"
        )
    
    def json(self, compact=None):
        srv6_sid_information = ', '.join(d.json() for d in self.srv6_sid_information)
        content = ', '.join(
            [
                '"protocol-id": %d' % int(self.protocol_id),
                '"identifier": %d' % int(self.identifier),
                '"local-node-descriptor": { %s }' % self.local_node_descriptor.json(),
                '"srv6-sid-information": [ %s ]' % srv6_sid_information,
            ]
        )
        if self.multi_topologies:
            content += ', "multi-topologies": [ %s ]' % ', '.join(mt.json() for mt in self.multi_topologies)
        if self.service_chainings:
            content += ', "service-chainings": [ %s ]' % ', '.join(sc.json() for sc in self.service_chainings)
        if self.opaque_metadata:
            content += ', "opaque-metadata": [ %s ]' % ', '.join(om.json() for om in self.opaque_metadata)

        return '{ %s }' % (content)

# TODO: NodeDescriptorを使えるか確認
class LocalNodeDescriptor:
    def __init__(self, as_number, bgp_ls_identifier, ospf_area_id, router_id):
        self.as_number = int(as_number)
        self.bgp_ls_identifier = int(bgp_ls_identifier)
        self.ospf_area_id = int(ospf_area_id)
        self.router_id = router_id

    def pack(self):
        return (
            pack('!I', self.as_number) +
            pack('!I', self.bgp_ls_identifier) +
            pack('!I', self.ospf_area_id) +
            IP.pton(self.router_id)
        )

    @staticmethod
    def unpack(data):
        as_number = unpack('!I', data[:4])[0]
        bgp_ls_identifier = unpack('!I', data[4:8])[0]
        ospf_area_id = unpack('!I', data[8:12])[0]
        router_id = IP.ntop(data[12:16])
        return LocalNodeDescriptor(as_number, bgp_ls_identifier, ospf_area_id, router_id)
    
    def json(self, compact=None):
        return ', '.join([
            '"as-number": %d' % self.as_number,
            '"bgp-ls-identifier": %d' % self.bgp_ls_identifier,
            '"ospf-area-id": %d' % self.ospf_area_id,
            '"router-id": "%s"' % self.router_id
        ])


class SRv6SIDDescriptor:
    def __init__(self, sid):
        self.type = 518
        self.length = 16
        self.sid = sid

    def pack(self):
        return pack('!HH', self.type, self.length) + IPv6.pton(self.sid)

    @staticmethod
    def unpack(data):
        return SRv6SIDDescriptor(IPv6.ntop(data))
    
    def json(self, compact=None):
        content = ', '.join([
            '"type": %d' % self.type,
            '"length": %d' % self.length,
            '"sid": "%s"' % self.sid
        ])
        return '{ %s }' % (content)
