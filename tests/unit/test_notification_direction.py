"""`Notify` goes out, `NotificationReceived` comes in, and `Notification` is only the message.

    Notify                we tell the PEER its data is malformed. The reactor sends the
                          NOTIFICATION it holds, then resets.
    NotificationReceived  the PEER told US it is tearing down. The reactor resets and sends
                          NOTHING, because the far end is already closing.
    Notification          the message itself, either way.  Not an exception.

This used to be one hierarchy: `Notify` subclassed `Notification`, which was an exception.
Raising `Notification` from a decoder closed the session WITHOUT telling the peer why, and
`except Notification` placed first in `Peer._main` bound every outbound notification too.
Both traps are gone with the hierarchy (plan/wip-message-interface.md); the sweep below
stays, as `raise Notification(...)` now fails only when it runs.

Ported from the 5.0 branch.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator

import pytest

from exabgp.bgp.message.notification import Notification, NotificationReceived, Notify
from exabgp.bgp.message.open.capability.negotiated import Negotiated

SOURCE = pathlib.Path(__file__).resolve().parent.parent.parent / 'src' / 'exabgp'
REACTOR_PEER = SOURCE / 'reactor' / 'peer' / 'peer.py'

HEADER_LEN_BYTES = 19  # RFC 4271 4.1

# A ratchet. The sweep below reports the files which raise the inbound class, and a sweep
# which matched nothing at all would report none of them and read as success.
MIN_NOTIFY_RAISES = 50


def python_files() -> list[pathlib.Path]:
    return sorted(path for path in SOURCE.rglob('*.py') if 'vendoring' not in path.parts)


def raised_names(tree: ast.AST) -> Iterator[tuple[int, str]]:
    """The line and the class name of every `raise` in this module."""
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        raised = node.exc
        if isinstance(raised, ast.Call):
            raised = raised.func
        if isinstance(raised, ast.Name):
            yield node.lineno, raised.id
        elif isinstance(raised, ast.Attribute):
            yield node.lineno, raised.attr


def raises_of(name: str) -> list[str]:
    found = []
    for path in python_files():
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        for line, raised in raised_names(tree):
            if raised == name:
                found.append(f'{path.relative_to(SOURCE)}:{line}')
    return found


# ============================================== nothing raises the inbound class


def test_no_source_file_raises_notification() -> None:
    offenders = raises_of('Notification')

    assert not offenders, (
        'these raise Notification, which closes the session WITHOUT sending the peer a '
        f'NOTIFICATION. They almost certainly want Notify: {offenders}'
    )


def test_notify_is_raised_often_enough_for_the_sweep_to_mean_something() -> None:
    """A walk which matched nothing would report no offender and read as clean."""
    total = len(raises_of('Notify'))

    assert total >= MIN_NOTIFY_RAISES, f'only {total} Notify raises found, so the check above proves little'


def test_the_walk_can_see_a_raise_of_the_class_it_is_looking_for() -> None:
    """The half the sweep over src cannot show, because src has no occurrence to find."""
    tree = ast.parse('def f():\n    raise Notification.make_notification(6, 0)\n')

    assert [name for _line, name in raised_names(tree)] == ['make_notification']

    tree = ast.parse('def f():\n    raise Notification(b"")\n')

    assert [name for _line, name in raised_names(tree)] == ['Notification']


# ============================================== the reactor handles both, in any order


def test_the_reactor_really_handles_both() -> None:
    source = REACTOR_PEER.read_text(encoding='utf-8')

    assert 'except Notify' in source
    assert 'except NotificationReceived' in source


# ============================================== the classes mean what they claim


def test_neither_exception_is_the_other() -> None:
    """Which is why the order of the two handlers in Peer no longer matters."""
    assert not issubclass(Notify, NotificationReceived)
    assert not issubclass(NotificationReceived, Notify)


def test_the_message_is_not_an_exception() -> None:
    """So `raise Notification(...)` is a TypeError, never a reset the peer is not told about."""
    assert not issubclass(Notification, BaseException)


def test_each_exception_holds_the_message() -> None:
    notify = Notify(6, 2, 'maintenance')
    received = NotificationReceived(Notification.make_notification(6, 2))

    assert (notify.notification.code, notify.notification.subcode) == (6, 2)
    assert (received.notification.code, received.notification.subcode) == (6, 2)


@pytest.mark.parametrize('code,subcode', [(3, 10), (2, 0), (6, 2)])
def test_a_notify_carries_its_code_to_the_wire(code: int, subcode: int) -> None:
    packed = Notify(code, subcode).notification.pack_message(Negotiated.UNSET)

    assert packed[HEADER_LEN_BYTES : HEADER_LEN_BYTES + 2] == bytes([code, subcode])
