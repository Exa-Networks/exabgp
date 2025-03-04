from struct import pack, unpack

class OpaqueMetadata(object):
    def __init__(self, length, opaque_type, flags, value):
        self.type = 65001
        self.length = int(length)
        self.opaque_type = int(opaque_type)
        self.flags = int(flags)
        self.value = str(value).encode('utf-8')

    def pack(self):
        return pack('!HHHB', self.type, self.length, self.opaque_type, self.flags) + self.value

    @staticmethod
    def unpack(length, data):
        opaque_type, flags = unpack('!HB', data[:3])
        value = data[3:].decode('utf-8')
        return OpaqueMetadata(length, opaque_type, flags, value)

    def json(self, compact=None):
        content = ', '.join([
            '"type": %d' % self.type,
            '"length": %d' % self.length,
            '"opaque-type": %d' % self.opaque_type,
            '"flags": %d' % self.flags,
            '"value": "%s"' % self.value.decode('utf-8')
        ])
        return '{ %s }' % (content)
