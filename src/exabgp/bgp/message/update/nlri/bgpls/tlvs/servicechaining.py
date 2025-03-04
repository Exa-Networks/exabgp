from struct import pack, unpack

class ServiceChaining(object):
    def __init__(self, service_type, flags, traffic_type, reserved):
        self.type = 65000
        self.length = 6
        self.service_type = int(service_type)
        self.flags = int(flags)
        self.traffic_type = int(traffic_type)
        self.reserved = int(reserved)

    def pack(self):
        return pack('!HHHBBH', self.type, self.length, self.service_type, self.flags, self.traffic_type, self.reserved)

    @staticmethod
    def unpack(data):
        service_type, flags, traffic_type, reserved = unpack('!HBBH', data)
        return ServiceChaining(service_type, flags, traffic_type, reserved)

    def json(self, compact=None):
        content = ', '.join([
            '"type": %d' % self.type,
            '"length": %d' % self.length,
            '"service-type": %d' % self.service_type,
            '"flags": %d' % self.flags,
            '"traffic-type": %d' % self.traffic_type,
            '"reserved": %d' % self.reserved
        ])
        return '{ %s }' % (content)