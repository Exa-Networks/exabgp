"""An attribute code with no class is not an error the peer made.

Attribute.unpack and Attribute.klass ended in Notify(2, 4), "Unsupported Optional
Parameter", an OPEN error about something else.  AttributeCollection.parse only calls them
for a registered code and keeps anything else as a generic attribute, so the Notify could
not reach a peer; the read-only wire iterator reaches unpack for every code and caught it.
A Notify is what a peer is sent.  This one is the caller asking for a class which is not
there, so it says so in the exception which means that.
"""

from __future__ import annotations

import pytest

from exabgp.bgp.message.open.capability.negotiated import Negotiated
from exabgp.bgp.message.update.attribute.attribute import Attribute

UNREGISTERED = 250
OPTIONAL_TRANSITIVE = 0xC0


def test_unpacking_an_unregistered_code_is_a_value_error() -> None:
    assert not Attribute.registered(UNREGISTERED, OPTIONAL_TRANSITIVE)
    with pytest.raises(ValueError):
        Attribute.unpack(UNREGISTERED, OPTIONAL_TRANSITIVE, b'', Negotiated.UNSET)


def test_asking_for_the_class_of_an_unregistered_code_is_our_bug() -> None:
    with pytest.raises(RuntimeError):
        Attribute.klass(UNREGISTERED, OPTIONAL_TRANSITIVE)
