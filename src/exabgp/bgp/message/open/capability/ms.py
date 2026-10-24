"""ms.py

Created by Thomas Mangin on 2012-07-17.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

from exabgp.bgp.message.open.capability.capability import Capability

# ================================================================= MultiSession
#


@Capability.register()
@Capability.register(Capability.CODE.MULTISESSION_CISCO)
class MultiSession(Capability, list):
    ID = Capability.CODE.MULTISESSION

    # draft-ietf-idr-bgp-multisession-07 section 4: the capability value is one octet of
    # flags followed by the Session Id, "list of zero or more capability codes (1 octet
    # each) defined in BGP, whose values will be used to distinguish one group from
    # another".  This is the size of the flags octet which precedes that list.
    FLAGS_SIZE = 1

    _seen = False

    def set(self, data):
        self.extend(data)
        return self

    # XXX: FIXME: Looks like we could do with something in this Caoability
    def __str__(self):
        info = ' (RFC)' if self.ID == Capability.CODE.MULTISESSION else ''
        return 'Multisession{} {}'.format(info, ' '.join([str(capa) for capa in self]))

    def json(self):
        variant = 'RFC' if self.ID == Capability.CODE.MULTISESSION else 'Cisco'
        return '{{ "name": "multisession", "variant": "{}", "capabilities": [{} ] }}'.format(
            variant,
            ','.join(' "{}"'.format(str(capa)) for capa in self),
        )

    def extract(self):
        # This does not match draft-ietf-idr-bgp-multisession-07 section 4, which defines a
        # single capability value of a flags octet followed by the whole Session Id: pack()
        # turns every element returned here into its own capability TLV, so the flags octet
        # and each Session Id code go out as separate one octet MULTISESSION capabilities.
        # It is left alone deliberately.  MULTIPROTOCOL is the only Session Id ExaBGP
        # generates, and a receiver which keeps the first instance reads our first TLV as an
        # empty Session Id, which section 4 makes equal to {MULTIPROTOCOL}: the bytes are
        # wrong and the meaning is right.  Changing what a production release puts in its
        # OPEN, with no multi-session peer to test against, buys nothing.  main/6.0 has the
        # conformant encoder (commit 7a7bdeea3), so fixing this is a parity item, not a bug
        # blocking the Session Id being read below.
        rs = [
            bytes([0]),
        ]
        for v in self:
            rs.append(bytes([v]))
        return rs

    @staticmethod
    def unpack_capability(instance, data, capability=None):  # pylint: disable=W0613
        # draft-ietf-idr-bgp-multisession-07 section 4 gives the value as a flags octet
        # followed by the Session Id.  This read used to discard `data` outright, so every
        # peer's Session Id decoded to the empty list, negotiated.py replaced that empty
        # set with its own {MULTIPROTOCOL} default, and the two sides therefore always
        # compared equal: the Grouping Conflict refusal section 7 requires was unreachable.
        if instance._seen:
            # RFC 5492 section 5 lets a receiver keep one instance of a capability sent
            # more than once.  Appending the second Session Id onto the first would
            # produce a list which is neither of the two the peer sent.  Keeping the first
            # is also what every ExaBGP needs: extract() above emits the flags octet and
            # each Session Id code as separate one octet capabilities, so our own OPEN
            # arrives here as several MULTISESSION TLVs whose bytes past the first one are
            # flags, not Session Id codes.
            return instance
        instance._seen = True

        # A zero length value has no flags octet, which section 4 makes mandatory, so it
        # is malformed.  It is read as an empty Session Id rather than refused: section 4
        # says "Empty Session Id list and Session Id containing 1 (one, Multiprotocol
        # Extensions) as the only value are considered equal", so the intent of a value
        # with nothing in it is unambiguous and is what we would have negotiated anyway.
        # Answering a NOTIFICATION here would drop a session which comes up today over a
        # missing octet we do not need, on the OPEN path of a production release.
        if len(data) < MultiSession.FLAGS_SIZE:
            return instance

        # The flags octet is skipped: the G bit is deprecated ("implementations conforming
        # to final version of Multisession specification SHOULD NOT rely on value of the G
        # bit") and the rest is "Reserved - MUST be set to zero by sender, MUST be ignored
        # by receiver".  Each remaining octet is one whole Session Id code, so there is no
        # partial record to guard against and the loop is bounded by the value we received.
        for code in data[MultiSession.FLAGS_SIZE :]:
            if code in (Capability.CODE.MULTISESSION, Capability.CODE.MULTISESSION_CISCO):
                # section 4: "The Multisession capability code itself MUST NOT be listed;
                # if listed it MUST be ignored upon receipt."
                continue
            instance.append(Capability.CODE(code))
        return instance
