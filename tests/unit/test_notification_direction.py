#!/usr/bin/env python3
# encoding: utf-8

"""Notify goes out, Notification comes in, and the difference is silent to get wrong

    Notify        we tell the PEER its data is malformed. The reactor sends a
                  NOTIFICATION on the wire, then resets.
    Notification  the PEER told US it is tearing down. The reactor resets and
                  sends NOTHING, because the far end is already closing.

Raising Notification from a decoder therefore closes the session WITHOUT telling
the peer why: the message never reaches the wire, and the operator on the other
side sees an unexplained reset. It is one word away from correct and nothing
about it looks wrong at the call site.

Notify subclasses Notification, so the handler order in the reactor matters too:
`except Notification` placed first would swallow every outbound notification and
none would ever be sent.

Neither property was held by anything.
"""

import ast
import pathlib

import pytest

SRC = pathlib.Path(__file__).parent.parent.parent / 'src' / 'exabgp'
REACTOR_PEER = SRC / 'reactor' / 'peer.py'


def raised_names(tree):
    """The name of every exception class raised in this module"""
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


def python_files():
    return sorted(p for p in SRC.rglob('*.py') if 'vendoring' not in p.parts)


class TestNothingRaisesTheInboundClass:
    def test_no_source_file_raises_notification(self) -> None:
        offenders = []
        for path in python_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            for line, name in raised_names(tree):
                if name == 'Notification':
                    offenders.append(f'{path.relative_to(SRC)}:{line}')
        assert not offenders, (
            'these raise Notification, which closes the session WITHOUT sending '
            f'the peer a NOTIFICATION. They almost certainly want Notify: {offenders}'
        )

    def test_notify_is_raised_and_is_the_one_we_send(self) -> None:
        # if nothing raises Notify the test above is vacuous
        total = 0
        for path in python_files():
            tree = ast.parse(path.read_text(), filename=str(path))
            total += sum(1 for _, name in raised_names(tree) if name == 'Notify')
        assert total > 50, f'only {total} Notify raises found, the check above proves little'


class TestTheHandlerOrderInTheReactor:
    """Notify subclasses Notification, so a first `except Notification` eats it"""

    def test_notify_is_caught_before_notification(self) -> None:
        source = REACTOR_PEER.read_text()
        notify = source.index('except Notify')
        notification = source.index('except Notification')
        assert notify < notification, (
            'except Notification comes first, so it catches Notify too and no '
            'outbound notification is ever put on the wire'
        )


class TestTheClassesMeanWhatTheyClaim:
    def test_notify_can_be_serialised_and_notification_cannot(self) -> None:
        from exabgp.bgp.message.notification import Notification, Notify

        assert hasattr(Notify, 'message'), 'Notify must serialise: it goes on the wire'
        assert (
            'message' not in Notification.__dict__
        ), 'Notification is what a peer sent us, there is nothing to send back'

    def test_notify_is_a_notification(self) -> None:
        from exabgp.bgp.message.notification import Notification, Notify

        assert issubclass(Notify, Notification)

    @pytest.mark.parametrize('code,subcode', [(3, 10), (2, 0), (6, 2)])
    def test_a_notify_carries_its_code_to_the_wire(self, code, subcode) -> None:
        from exabgp.bgp.message.notification import Notify

        packed = Notify(code, subcode).message()
        assert packed[19:21] == bytes([code, subcode])
