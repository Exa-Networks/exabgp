"""RFC 7606 section 6: an UPDATE with a malformed attribute is logged, with its NLRI and its bytes.

Treat-as-withdraw and attribute discard change the routes without a NOTIFICATION, so the
log is the only record the operator gets of why. The section asks for one error naming the
NLRI involved and carrying the entire malformed UPDATE. Each path below used to say less:
some logged at debug, some nothing, and the one which logged an error named the attribute
but neither the routes nor the message.
"""

from __future__ import annotations

import logging
from typing import Any

import pytest

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.update.attribute import Attribute
from exabgp.logger import log
from exabgp.logger.option import echo, option

from rfc.rfc7606_wire import (
    EMPTY_AS_PATH,
    IPV4_PREFIX,
    MANDATORY,
    NEXT_HOP,
    OPTIONAL,
    OPTIONAL_TRANSITIVE,
    ORIGIN_IGP,
    WELL_KNOWN_TRANSITIVE,
    attribute,
    parse,
    session,
    update,
)

CODE = Attribute.CODE

# The real dispatcher, kept before any test can swap it for the no-op one.
ENABLED_LOG_DISPATCH = log.logger
LOG_LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')


def enable_every_log(monkeypatch: pytest.MonkeyPatch, caplog: Any, lowest: str = 'DEBUG') -> None:
    """Every level from `lowest` and every source switched on, so silence is the parser's own."""
    enabled = LOG_LEVELS[LOG_LEVELS.index(lowest) :]
    monkeypatch.setattr(log, 'logger', staticmethod(ENABLED_LOG_DISPATCH))
    monkeypatch.setattr(option, 'logger', logging.getLogger('test.rfc7606.logging'))
    monkeypatch.setattr(option, 'formater', echo)
    monkeypatch.setattr(option, 'option', {})
    monkeypatch.setattr(option, 'logit', {level: level in enabled for level in LOG_LEVELS})
    caplog.set_level(getattr(logging, lowest), logger='test.rfc7606.logging')


def errors(caplog: Any) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]


def as_set_path() -> bytes:
    """An AS_PATH holding an AS_SET, which RFC 9774 withdraws by default."""
    return attribute(WELL_KNOWN_TRANSITIVE, CODE.AS_PATH, bytes([1, 1, 0, 0, 0xFD, 0xEA]))


MALFORMED_UPDATES = [
    ('a malformed MULTI_EXIT_DISC', MANDATORY + attribute(OPTIONAL, CODE.MED, bytes(3))),
    ('a length past the end of the attributes', MANDATORY + bytes([OPTIONAL, CODE.MED, 40]) + bytes(4)),
    ('a truncated attribute header', MANDATORY + bytes([WELL_KNOWN_TRANSITIVE, CODE.ORIGIN])),
    ('a flag conflict', attribute(OPTIONAL, CODE.ORIGIN, bytes([0])) + EMPTY_AS_PATH + NEXT_HOP),
    ('a missing NEXT_HOP', ORIGIN_IGP + EMPTY_AS_PATH),
    ('a malformed NEXT_HOP', ORIGIN_IGP + EMPTY_AS_PATH + attribute(WELL_KNOWN_TRANSITIVE, CODE.NEXT_HOP, bytes(3))),
    ('an AS_SET', ORIGIN_IGP + as_set_path() + NEXT_HOP),
    ('a discarded AGGREGATOR', MANDATORY + attribute(OPTIONAL_TRANSITIVE, CODE.AGGREGATOR, bytes(7))),
]


@pytest.mark.rfc('rfc7606#6-log-malformed-update')
@pytest.mark.parametrize('name,attributes', MALFORMED_UPDATES, ids=[_[0] for _ in MALFORMED_UPDATES])
def test_a_malformed_update_is_logged_once_with_its_nlri_and_its_bytes(
    monkeypatch: pytest.MonkeyPatch, caplog: Any, name: str, attributes: bytes
) -> None:
    payload = update(attributes, nlri=IPV4_PREFIX)
    whole = Message.frame(Message.CODE.UPDATE, payload).hex()
    enable_every_log(monkeypatch, caplog)

    parse(payload, session())

    logged = errors(caplog)
    assert len(logged) == 1, f'{name}: {len(logged)} errors for one UPDATE: {logged}'
    assert '10.0.0.0/24' in logged[0], f'{name}: the NLRI is not named: {logged[0]}'
    assert whole in logged[0].lower(), f'{name}: the UPDATE is not in the log: {logged[0]}'


@pytest.mark.rfc('rfc7606#6-log-malformed-update', polarity='negative')
def test_a_well_formed_update_logs_no_error(monkeypatch: pytest.MonkeyPatch, caplog: Any) -> None:
    """An error for every UPDATE would pass the test above and bury the real ones."""
    enable_every_log(monkeypatch, caplog)

    parse(update(MANDATORY), session())

    assert caplog.records, 'the parser logged nothing at all, so the capture itself is broken'
    assert errors(caplog) == []


def test_the_log_of_a_large_malformed_update_is_bounded(monkeypatch: pytest.MonkeyPatch, caplog: Any) -> None:
    """A peer controls the size of the UPDATE, and so of the line, unless it is capped.

    An extended message (RFC 8654) of about twenty thousand octets: the line keeps the first
    4096 octets of it, the size of any message without the extension, and the first NLRI.
    """
    prefixes = b''.join(bytes([32, 10, 0, high, low]) for high in range(16) for low in range(250))
    payload = update(MANDATORY + attribute(OPTIONAL, CODE.MED, bytes(3)), nlri=prefixes)
    negotiated = session()
    negotiated.msg_size = Message.EXTENDED_MAX
    # errors only: a debug line for each of 4000 NLRI is slow and beside the point
    enable_every_log(monkeypatch, caplog, lowest='ERROR')

    parse(payload, negotiated)

    logged = errors(caplog)
    assert len(logged) == 1, logged
    assert '10.0.0.0/32' in logged[0]
    assert '10.0.15.249/32' not in logged[0], 'every one of 4000 NLRI was listed'
    assert len(logged[0]) < 3 * Message.STANDARD_MAX, f'a line of {len(logged[0])} characters'
