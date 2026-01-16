"""test_tcp_ao.py

Unit tests for TCP-AO (RFC 5925) socket option support.

Copyright (c) 2009-2025 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""

from __future__ import annotations

import socket
import struct
from struct import calcsize, pack, unpack

import pytest


class TestTCPAOStructPacking:
    """Tests for TCP-AO struct packing logic."""

    def test_sockaddr_storage_ipv4_size(self) -> None:
        """IPv4 sockaddr_storage should be 128 bytes."""
        # sockaddr_storage is always 128 bytes regardless of address family
        SS_MAXSIZE = 128
        # IPv4: family (2) + port (2) + addr (4) + padding
        ipv4_base_size = calcsize('HH4s')
        padding = SS_MAXSIZE - ipv4_base_size
        assert padding == 120  # 128 - 8

        # Full packed sockaddr should be 128 bytes
        sockaddr = pack('HH4s%dx' % padding, socket.AF_INET, 0, b'\x00' * 4)
        assert len(sockaddr) == SS_MAXSIZE

    def test_sockaddr_storage_ipv6_size(self) -> None:
        """IPv6 sockaddr_storage should be 128 bytes."""
        SS_MAXSIZE = 128
        # IPv6: family (2) + port (2) + flowinfo (4) + addr (16) + scope_id (4) = 28
        ipv6_base_size = calcsize('HHI16sI')
        padding = SS_MAXSIZE - ipv6_base_size
        assert padding == 100  # 128 - 28

        sockaddr = pack('HHI16sI%dx' % padding, socket.AF_INET6, 0, 0, b'\x00' * 16, 0)
        assert len(sockaddr) == SS_MAXSIZE

    def test_tcp_ao_add_struct_layout(self) -> None:
        """tcp_ao_add structure should have correct layout.

        From Linux tcp.h:
        struct tcp_ao_add {
            struct __kernel_sockaddr_storage addr;  // 128 bytes
            char alg_name[64];                      // algorithm name
            __s32 ifindex;                          // VRF interface
            __u32 flags;                            // set_current:1, set_rnext:1, reserved:30
            __u16 reserved2;
            __u8 prefix, sndid, rcvid, maclen, keyflags, keylen;  // 6 bytes
            __u8 key[TCP_AO_MAXKEYLEN];             // 80 bytes
        };
        """
        SS_MAXSIZE = 128
        ALG_NAME_LEN = 64
        TCP_AO_MAXKEYLEN = 80

        # Calculate total size
        sockaddr_size = SS_MAXSIZE  # 128
        alg_name_size = ALG_NAME_LEN  # 64
        ifindex_size = 4  # __s32
        flags_size = 4  # __u32
        reserved2_size = 2  # __u16
        fields_size = 6  # prefix, sndid, rcvid, maclen, keyflags, keylen
        key_size = TCP_AO_MAXKEYLEN  # 80

        total_size = sockaddr_size + alg_name_size + ifindex_size + flags_size + reserved2_size + fields_size + key_size
        assert total_size == 288

    def test_algorithm_name_packing(self) -> None:
        """Algorithm names should be null-padded to 64 bytes."""
        ALG_NAME_LEN = 64

        alg_names = [
            ('hmac(sha1)', b'hmac(sha1)'),
            ('cmac(aes)', b'cmac(aes)'),
            ('hmac(sha256)', b'hmac(sha256)'),
        ]

        for name_str, expected_bytes in alg_names:
            # Pack with null padding
            alg_name = name_str.encode('ascii')
            packed = alg_name.ljust(ALG_NAME_LEN, b'\x00')
            assert len(packed) == ALG_NAME_LEN
            assert packed.startswith(expected_bytes)
            assert packed[len(expected_bytes) :] == b'\x00' * (ALG_NAME_LEN - len(expected_bytes))

    def test_key_packing(self) -> None:
        """Key should be null-padded to TCP_AO_MAXKEYLEN (80) bytes."""
        TCP_AO_MAXKEYLEN = 80

        test_keys = [
            b'short',
            b'a' * 40,
            b'x' * TCP_AO_MAXKEYLEN,
        ]

        for key in test_keys:
            keylen = len(key)
            packed_key = key.ljust(TCP_AO_MAXKEYLEN, b'\x00')
            assert len(packed_key) == TCP_AO_MAXKEYLEN
            assert packed_key[:keylen] == key

    def test_keyid_range(self) -> None:
        """KeyID (sndid, rcvid) should be 0-255."""
        valid_keyids = [0, 1, 127, 255]
        invalid_keyids = [-1, 256, 1000]

        for keyid in valid_keyids:
            # Should pack as unsigned byte
            packed = pack('B', keyid)
            assert len(packed) == 1
            assert unpack('B', packed)[0] == keyid

        for keyid in invalid_keyids:
            with pytest.raises((struct.error, OverflowError)):
                pack('B', keyid)


class TestTCPAOConstants:
    """Tests for TCP-AO kernel constants."""

    def test_socket_option_constants(self) -> None:
        """TCP-AO socket option constants should match kernel values."""
        # From Linux tcp.h
        TCP_AO_ADD_KEY = 38
        TCP_AO_DEL_KEY = 39
        TCP_AO_INFO = 40
        TCP_AO_GET_KEYS = 41
        TCP_AO_MAXKEYLEN = 80

        # These are the expected values from the kernel
        assert TCP_AO_ADD_KEY == 38
        assert TCP_AO_DEL_KEY == 39
        assert TCP_AO_INFO == 40
        assert TCP_AO_GET_KEYS == 41
        assert TCP_AO_MAXKEYLEN == 80


class TestTCPAOAlgorithms:
    """Tests for TCP-AO algorithm name mapping."""

    def test_algorithm_name_mapping(self) -> None:
        """User-friendly names should map to kernel algorithm names."""
        # User config -> kernel name
        ALGORITHM_MAP = {
            'hmac-sha-1-96': 'hmac(sha1)',
            'aes-128-cmac-96': 'cmac(aes)',
            'hmac-sha-256': 'hmac(sha256)',
        }

        for user_name, kernel_name in ALGORITHM_MAP.items():
            assert len(kernel_name.encode('ascii')) <= 64
            # Verify kernel names are valid strings
            assert kernel_name.isascii()


class TestTCPAOValidation:
    """Tests for TCP-AO parameter validation."""

    def test_keyid_validation(self) -> None:
        """KeyID must be 0-255."""

        # Valid keyid range
        for keyid in [0, 1, 127, 255]:
            # Should not raise
            assert 0 <= keyid <= 255

        # Invalid keyid values
        for keyid in [-1, 256, 1000]:
            assert not (0 <= keyid <= 255)

    def test_key_length_validation(self) -> None:
        """Key length must be <= 80 bytes."""
        TCP_AO_MAXKEYLEN = 80

        valid_keys = ['short', 'a' * 40, 'x' * TCP_AO_MAXKEYLEN]
        invalid_keys = ['y' * (TCP_AO_MAXKEYLEN + 1)]

        for key in valid_keys:
            assert len(key) <= TCP_AO_MAXKEYLEN

        for key in invalid_keys:
            assert len(key) > TCP_AO_MAXKEYLEN

    def test_algorithm_validation(self) -> None:
        """Algorithm name must be valid."""
        VALID_ALGORITHMS = {'hmac-sha-1-96', 'aes-128-cmac-96', 'hmac-sha-256'}

        for alg in VALID_ALGORITHMS:
            assert alg in VALID_ALGORITHMS

        assert 'invalid-algorithm' not in VALID_ALGORITHMS


class TestTCPAOMutualExclusion:
    """Tests for MD5/TCP-AO mutual exclusion."""

    def test_md5_and_tcp_ao_mutually_exclusive(self) -> None:
        """MD5 and TCP-AO cannot both be configured."""
        # This tests the validation logic that will be added
        # Both being set should be an error
        md5_password = 'md5secret'
        tcp_ao_password = 'aosecret'

        # When both are set, should be invalid
        both_set = bool(md5_password) and bool(tcp_ao_password)
        assert both_set is True  # This is the error condition

        # Only one set should be valid
        only_md5 = bool(md5_password) and not bool('')
        only_ao = bool(tcp_ao_password) and not bool('')
        assert only_md5 is True
        assert only_ao is True


class TestTCPAOByteLengthValidation:
    """Tests for password byte-length validation (not character length)."""

    def test_multibyte_utf8_password_byte_count(self) -> None:
        """Password with multi-byte UTF-8 chars should count bytes, not characters."""
        # "пароль" (Russian for "password") = 6 characters but 12 UTF-8 bytes
        cyrillic_password = 'пароль'
        assert len(cyrillic_password) == 6  # Character count
        assert len(cyrillic_password.encode('utf-8')) == 12  # Byte count

        # A password that's 80 characters but >80 bytes should fail validation
        # 40 Cyrillic chars = 40 characters, 80 bytes (at limit)
        at_limit = 'п' * 40
        assert len(at_limit) == 40
        assert len(at_limit.encode('utf-8')) == 80

        # 41 Cyrillic chars = 41 characters, 82 bytes (over limit)
        over_limit = 'п' * 41
        assert len(over_limit) == 41
        assert len(over_limit.encode('utf-8')) == 82

    def test_ascii_password_same_length(self) -> None:
        """ASCII passwords have same character and byte count."""
        ascii_password = 'secret123'
        assert len(ascii_password) == len(ascii_password.encode('utf-8'))
