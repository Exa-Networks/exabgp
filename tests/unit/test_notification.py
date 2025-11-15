#!/usr/bin/env python3
# encoding: utf-8
"""notification_test.py

Unit tests for the Notify exception and BGP NOTIFICATION packet generation.
AI Generated
"""

import unittest

from exabgp.bgp.message.message import Message
from exabgp.bgp.message.notification import Notify, Notification


class TestNotifyException(unittest.TestCase):
    def test_notify_message_wire_format(self) -> None:
        # Build a Notify exception and generate its wire-format packet
        code, subcode, data = 2, 1, 'AB'
        notify_exc = Notify(code, subcode, data)
        packet = notify_exc.pack_message(negotiated=None)

        # Marker: 16 bytes of 0xFF
        self.assertEqual(packet[:16], Message.MARKER)

        # Length: header (19 bytes) + payload (code + subcode + data)
        length = int.from_bytes(packet[16:18], 'big')
        expected_len = Message.HEADER_LEN + 1 + 1 + len(data)
        self.assertEqual(length, expected_len)

        # Type: single byte for NOTIFICATION
        self.assertEqual(packet[18:19], Notification.TYPE)

        # Payload: code, subcode, then data (encoded as ASCII bytes)
        self.assertEqual(packet[19], code)
        self.assertEqual(packet[20], subcode)
        self.assertEqual(packet[21:], data.encode('ascii'))

    def test_message_klass_unknown_raises_notify(self) -> None:
        # Message.klass should raise Notify for unknown message codes
        from exabgp.bgp.message.message import Message

        unknown_code = 255
        with self.assertRaises(Notify) as cm:
            Message.klass(unknown_code)
        notify_exc = cm.exception
        # Default error for unhandled message
        self.assertEqual(notify_exc.code, 2)
        self.assertEqual(notify_exc.subcode, 4)
        # The payload data should include the unknown message code
        expected_data = f'can not handle message {unknown_code}'.encode('ascii')
        self.assertEqual(notify_exc.data, expected_data)


if __name__ == '__main__':
    unittest.main()
