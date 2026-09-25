"""`Notify` goes out, `Notification` comes in, and the difference is silent to get wrong.

    Notify        we tell the PEER its data is malformed. The reactor sends a NOTIFICATION
                  on the wire, then resets.
    Notification  the PEER told US it is tearing down. The reactor resets and sends
                  NOTHING, because the far end is already closing.

Raising `Notification` from a decoder therefore closes the session WITHOUT telling the
peer why: the message never reaches the wire and the operator on the other side sees an
unexplained reset. It is one word away from correct and nothing about it looks wrong at
the call site, so the check has to be a sweep over the source rather than a review habit.

`Notify` subclasses `Notification`, so the handler order in `Peer._main` matters for the
same reason: `except Notification` placed first would bind every outbound notification
too, and none would ever be put on the wire.

Neither property is held by anything else in this tree. Ported from the 5.0 branch.
"""

from __future__ import annotations

import ast
import pathlib
from collections.abc import Iterator

import pytest

from exabgp.bgp.message.notification import Notification, Notify
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


# ============================================== the handler order in the reactor


def test_notify_is_caught_before_notification() -> None:
    source = REACTOR_PEER.read_text(encoding='utf-8')

    notify = source.index('except Notify')
    notification = source.index('except Notification')

    assert notify < notification, (
        'except Notification comes first, so it binds Notify too and no outbound notification is ever put on the wire'
    )


def test_the_reactor_really_handles_both() -> None:
    """A file holding neither handler would satisfy the ordering test by raising instead."""
    source = REACTOR_PEER.read_text(encoding='utf-8')

    assert 'except Notify' in source
    assert 'except Notification' in source


# ============================================== the classes mean what they claim


def test_notify_serialises_and_notification_does_not() -> None:
    assert 'pack_message' in Notify.__dict__, 'Notify must serialise: it goes on the wire'
    assert 'pack_message' not in Notification.__dict__, (
        'Notification is what a peer sent us, there is nothing to send back'
    )


def test_notify_is_a_notification() -> None:
    """Which is why the handler order above is load bearing."""
    assert issubclass(Notify, Notification)


@pytest.mark.parametrize('code,subcode', [(3, 10), (2, 0), (6, 2)])
def test_a_notify_carries_its_code_to_the_wire(code: int, subcode: int) -> None:
    packed = Notify(code, subcode).pack_message(Negotiated.UNSET)

    assert packed[HEADER_LEN_BYTES : HEADER_LEN_BYTES + 2] == bytes([code, subcode])
