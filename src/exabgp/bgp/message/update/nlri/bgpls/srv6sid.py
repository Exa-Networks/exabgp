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
        local_node_descriptor = []
        multi_topologies = []
        srv6_sid_information = []
        service_chainings = []
        opaque_metadata = []
        tlvs = data[9:]

        while tlvs:
            tlv_type, tlv_length = unpack('!HH', tlvs[:4])
            value = tlvs[4 : 4 + tlv_length]
            tlvs = tlvs[4 + tlv_length :]

            if tlv_type == 256:
                local_node_descriptor = LocalNodeDescriptor.unpack(value)
                continue

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
                opaque_metadata.append(OpaqueMetadata.unpack(value))
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
                '"local-node-descriptor": %s' % self.local_node_descriptor.json(),
                '"srv6-sid-information": [ %s ]' % srv6_sid_information,
            ]
        )
        if self.multi_topologies:
            content += ', "multi-topologies": [ %s ]' % ', '.join(mt.json() for mt in self.multi_topologies)
        if self.service_chainings:
            content += ', "service-chainings": [ %s ]' % ', '.join(sc.json() for sc in self.service_chainings)
        if self.opaque_metadata:
            content += ', "opaque-metadata": [ %s ]' % ', '.join(om.json() for om in self.opaque_metadata)

        return '{ %s }' % content


class LocalNodeDescriptorSub:
    def __init__(self, tlv_type, unpacked_value):
        self.tlv_type = tlv_type
        self.unpacked_value = unpacked_value
        if self.tlv_type in (512, 513, 514, 517):
            self.packed_value = pack('!I', int(unpacked_value))
        elif self.tlv_type in (515, 516):
            self.packed_value = IP.pton(unpacked_value)
        else:
            raise NotImplemented
        self.length = len(self.packed_value)

    def pack(self):
        return pack('!HH', self.tlv_type, self.length) + self.packed_value

    @staticmethod
    def unpack(data):
        tlv_type, length = unpack('!HH', data[:4])
        packed_value = data[4:4+length]
        if tlv_type in (512, 513, 514):
            unpacked_value = unpack('!I', packed_value)[0]
        elif tlv_type in (515, 516):
            unpacked_value = IP.ntop(packed_value)
        else:
            return None
        return LocalNodeDescriptorSub(tlv_type, unpacked_value)

    def json(self):
        content = ', '.join([
            '"type": %d' % self.tlv_type,
            '"length": %d' % self.length,
            '"value": "%s"' % self.unpacked_value
        ])
        return '{ %s }' % content


class LocalNodeDescriptor:
    def __init__(self, sub_tlvs):
        self.tlv_type = 256
        self.sub_tlvs = sub_tlvs
        self.length = sum(4 + sub_tlv.length for sub_tlv in self.sub_tlvs)

    def pack(self):
        return pack('!HH', self.tlv_type, self.length) + b''.join(sub_tlv.pack() for sub_tlv in self.sub_tlvs)

    @staticmethod
    def unpack(data):
        sub_tlvs = []
        while data:
            sub_tlv = LocalNodeDescriptorSub.unpack(data)
            if sub_tlv is None: # TODO: 要確認
                break
            sub_tlvs.append(sub_tlv)
            data = data[4 + sub_tlv.length:]
        return LocalNodeDescriptor(sub_tlvs)

    def json(self, compact=None):
        sub_tlvs = ', '.join(sub_tlv.json() for sub_tlv in self.sub_tlvs)
        content = ', '.join([
            '"type": %d' % self.tlv_type,
            '"length": %d' % self.length,
            '"sub-tlvs": [ %s ]' % sub_tlvs
        ])
        return '{ %s }' % content


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
        return '{ %s }' % content
