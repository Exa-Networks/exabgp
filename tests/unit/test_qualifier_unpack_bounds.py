"""Wire qualifier helpers reject truncated and overlong fixed-size values."""

from collections.abc import Callable
from typing import cast

import pytest

from exabgp.bgp.message.notification import Notify
from exabgp.bgp.message.update.nlri.qualifier.esi import ESI
from exabgp.bgp.message.update.nlri.qualifier.etag import EthernetTag
from exabgp.bgp.message.update.nlri.qualifier.mac import MAC
from exabgp.bgp.message.update.nlri.qualifier.rd import RouteDistinguisher

NOTIFY_EXCEPTION = cast(type[BaseException], Notify)


@pytest.mark.parametrize(
    'unpack,length',
    [
        (ESI.unpack_esi, ESI.LENGTH),
        (EthernetTag.unpack_etag, EthernetTag.LENGTH),
        (MAC.unpack_mac, MAC.LENGTH),
        (RouteDistinguisher.unpack_routedistinguisher, RouteDistinguisher.LENGTH),
    ],
)
def test_fixed_size_qualifier_requires_exact_length(unpack: Callable[[bytes], object], length: int) -> None:
    with pytest.raises(NOTIFY_EXCEPTION):
        unpack(bytes(length - 1))
    with pytest.raises(NOTIFY_EXCEPTION):
        unpack(bytes(length + 1))

    assert unpack(bytes(length)) is not None
