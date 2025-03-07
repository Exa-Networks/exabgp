from struct import pack, unpack

class OpaqueMetadata(object):
    def __init__(self, opaque_type, flags, value):
        self.type = 65001
        self.opaque_type = int(opaque_type)
        self.flags = int(flags)
        self.value = str(value).encode('utf-8')
        self.length = len(pack('!HB', self.opaque_type, self.flags) + self.value + b'\x00')

    def pack(self):
        return pack('!HHHB', self.type, self.length, self.opaque_type, self.flags) + self.value + b'\x00'

    @staticmethod
    def unpack(data):
        opaque_type, flags = unpack('!HB', data[:3])
        value = data[3:].rstrip(b'\x00').decode('utf-8')
        return OpaqueMetadata(opaque_type, flags, value)

    def json(self, compact=None):
        content = ', '.join([
            '"type": %d' % self.type,
            '"length": %d' % self.length,
            '"opaque-type": %d' % self.opaque_type,
            '"flags": %d' % self.flags,
            '"value": "%s"' % self.value.decode('utf-8')
        ])
        return '{ %s }' % content
