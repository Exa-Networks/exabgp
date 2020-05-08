# encoding: utf-8
"""
aspath.py

Created by Thomas Mangin on 2009-11-05.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from struct import unpack
from struct import error

from exabgp.util import character
from exabgp.util import ordinal
from exabgp.util import concat_bytes
from exabgp.util import concat_bytes_i
from exabgp.bgp.message.open.asn import ASN
from exabgp.bgp.message.open.asn import AS_TRANS
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message.notification import Notify


# =================================================================== ASPath (2)
# only 2-4% of duplicated data therefore it is not worth to cache


@Attribute.register()
class ASPath(Attribute):
    AS_SET = 0x01
    AS_SEQUENCE = 0x02
    AS_CONFED_SEQUENCE = 0x03
    AS_CONFED_SET = 0x04
    ASN4 = False

    ID = Attribute.CODE.AS_PATH
    FLAG = Attribute.Flag.TRANSITIVE

    __slots__ = ['as_seq', 'as_set', 'as_cseq', 'as_cset', 'segments', '_packed', 'index', '_str', '_json']

    def __init__(self, as_sequence, as_set, as_conf_sequence=None, as_conf_set=None, index=None):
        self.as_seq = as_sequence
        self.as_set = as_set
        self.as_cseq = as_conf_sequence if as_conf_sequence is not None else []
        self.as_cset = as_conf_set if as_conf_set is not None else []
        self.segments = b''
        self._packed = {True: b'', False: b''}
        self.index = index  # the original packed data, use for indexing
        self._str = ''
        self._json = {}

    def __eq__(self, other):
        return (
            self.ID == other.ID
            and self.FLAG == other.FLAG
            and self.ASN4 == other.ASN4
            and self.as_seq == other.as_seq
            and self.as_set == other.as_set
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def _segment(self, seg_type, values, asn4):
        length = len(values)
        if length:
            if length > 255:
                return self._segment(seg_type, values[:255], asn4) + self._segment(seg_type, values[255:], asn4)
            return concat_bytes(
                character(seg_type), character(len(values)), concat_bytes_i(v.pack(asn4) for v in values)
            )
        return b""

    def _segments(self, asn4):
        segments = b''
        if self.as_cseq:
            segments += self._segment(self.AS_CONFED_SEQUENCE, self.as_cseq, asn4)
        if self.as_cset:
            segments += self._segment(self.AS_CONFED_SET, self.as_cset, asn4)
        if self.as_seq:
            segments += self._segment(self.AS_SEQUENCE, self.as_seq, asn4)
        if self.as_set:
            segments += self._segment(self.AS_SET, self.as_set, asn4)
        return segments

    def asn_pack(self, negotiated, force_asn4=False):
        asn4 = True if force_asn4 else negotiated.asn4
        if not self._packed[asn4]:
            self._packed[asn4] = self._attribute(self._segments(asn4))
        return self._packed[asn4]

    def pack(self, negotiated):
        # if the peer does not understand ASN4, we need to build a transitive AS4_PATH
        if negotiated.asn4:
            return self.asn_pack(negotiated)

        as2_seq = [_ if not _.asn4() else AS_TRANS for _ in self.as_seq]
        as2_set = [_ if not _.asn4() else AS_TRANS for _ in self.as_set]

        message = ASPath(as2_seq, as2_set, self.as_cseq, self.as_cset).asn_pack(negotiated, False)
        if AS_TRANS in as2_seq or AS_TRANS in as2_set:
            message += AS4Path(self.as_seq, self.as_set, self.as_cseq, self.as_cset).asn_pack(negotiated, True)
        return message

    def __len__(self):
        raise RuntimeError('it makes no sense to ask for the size of this object')

    def __repr__(self, confed=False):
        if self._str:
            return self._str

        if self.as_cseq or self.as_cset:
            string = self.string(self.as_seq, self.as_set) + self.string(self.as_cseq, self.as_cset)
        else:
            string = self.string(self.as_seq, self.as_set)

        self._str = string
        return string

    def string(self, aseq, aset):
        lseq = len(aseq)
        lset = len(aset)
        if lseq == 1:
            if not lset:
                string = '[ %d ]' % aseq[0]
            else:
                string = '[ %s %s]' % (aseq[0], '( %s ) ' % (' '.join([str(_) for _ in aset])))
        elif lseq > 1:
            if lset:
                string = '[ %s %s]' % (
                    (' '.join([str(_) for _ in aseq])),
                    '( %s ) ' % (' '.join([str(_) for _ in aset])),
                )
            else:
                string = '[ %s ]' % ' '.join([str(_) for _ in aseq])
        else:  # lseq == 0
            if lset:
                string = '[ ( %s )]' % (' '.join([str(_) for _ in aset]))
            else:
                string = '[ ]'
        return string

    def json(self, name):
        match = {
            # data , default representation
            'as-path': (self.as_seq, '[]'),
            'as-set': (self.as_set, ''),
            'confederation-path': (self.as_cseq, '[]'),
            'confederation-set': (self.as_cset, ''),
        }

        data, default = match[name]
        self._json[name] = '[ %s ]' % ', '.join([str(_) for _ in data]) if data else default
        return self._json[name]

    @classmethod
    def _new_aspaths(cls, data, asn4, klass=None):
        as_set = []
        as_seq = []
        as_cset = []
        as_cseq = []

        backup = data

        unpacker = {
            False: '!H',
            True: '!L',
        }
        size = {
            False: 2,
            True: 4,
        }
        as_choice = {
            ASPath.AS_SEQUENCE: as_seq,
            ASPath.AS_SET: as_set,
            ASPath.AS_CONFED_SEQUENCE: as_cseq,
            ASPath.AS_CONFED_SET: as_cset,
        }

        upr = unpacker[asn4]
        length = size[asn4]

        try:

            while data:
                stype = ordinal(data[0])
                slen = ordinal(data[1])

                if stype not in (ASPath.AS_SET, ASPath.AS_SEQUENCE, ASPath.AS_CONFED_SEQUENCE, ASPath.AS_CONFED_SET):
                    raise Notify(3, 11, 'invalid AS Path type sent %d' % stype)

                end = 2 + (slen * length)
                sdata = data[2:end]
                data = data[end:]
                # Eat the data and ignore it if the ASPath attribute is know known
                asns = as_choice.get(stype, [])

                for _ in range(slen):
                    asn = unpack(upr, sdata[:length])[0]
                    asns.append(ASN(asn))
                    sdata = sdata[length:]

        except IndexError:
            raise Notify(3, 11, 'not enough data to decode AS_PATH or AS4_PATH')
        except error:  # struct
            raise Notify(3, 11, 'not enough data to decode AS_PATH or AS4_PATH')

        if klass:
            return klass(as_seq, as_set, as_cseq, as_cset, backup)
        return cls(as_seq, as_set, as_cseq, as_cset, backup)

    @classmethod
    def unpack(cls, data, negotiated):
        if not data:
            return None  # ASPath.Empty
        return cls._new_aspaths(data, negotiated.asn4, ASPath)


ASPath.Empty = ASPath([], [])


# ================================================================= AS4Path (17)
#


@Attribute.register()
class AS4Path(ASPath):
    ID = Attribute.CODE.AS4_PATH
    FLAG = Attribute.Flag.TRANSITIVE | Attribute.Flag.OPTIONAL
    ASN4 = True

    def pack(self, negotiated=None):
        ASPath.pack(self, True)

    @classmethod
    def unpack(cls, data, negotiated):
        if not data:
            return None  # AS4Path.Empty
        return cls._new_aspaths(data, True, AS4Path)


AS4Path.Empty = AS4Path([], [])
