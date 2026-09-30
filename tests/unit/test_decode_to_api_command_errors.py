"""decode_to_api_command must distinguish no update from an internal failure."""

import pytest

from exabgp.configuration import command
from tests import negotiation

# A KEEPALIVE: a BGP message, but not an UPDATE, so there is nothing to decode
KEEPALIVE = 'FF' * 16 + '0013' + '04'


def test_decode_failure_propagates() -> None:
    # 'zz' is not hexadecimal: the failure reaches the caller, it is not read as no update
    with pytest.raises(ValueError, match='zz'):
        command.decode_to_api_command('zz', negotiation.neighbor())


def test_no_decoded_update_returns_empty_list() -> None:
    assert command.decode_to_api_command(KEEPALIVE, negotiation.neighbor()) == []
