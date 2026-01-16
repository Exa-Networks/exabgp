# TCP-AO Support Implementation Plan

**Status:** ✅ Completed
**Created:** 2025-01-15
**Issue:** https://github.com/Exa-Networks/exabgp/issues/1254
**RFC:** RFC 5925 (TCP Authentication Option)

---

## Overview

Implement TCP Authentication Option (TCP-AO) support for ExaBGP on Linux, following the same pattern as existing TCP-MD5SIG support.

## Background

- TCP-AO (RFC 5925) supersedes TCP-MD5SIG (RFC 2385)
- Linux kernel supports TCP-AO since ~v6.7 (2023)
- Socket options: `TCP_AO_ADD_KEY=38`, `TCP_AO_DEL_KEY=39`, `TCP_AO_INFO=40`
- Max key length: 80 bytes (same as MD5)
- Supports multiple algorithms (HMAC-SHA-1-96, AES-128-CMAC-96, HMAC-SHA-256)

## Linux Kernel API

### Constants
```c
TCP_AO_ADD_KEY    = 38
TCP_AO_DEL_KEY    = 39
TCP_AO_INFO       = 40
TCP_AO_GET_KEYS   = 41
TCP_AO_MAXKEYLEN  = 80
```

### Structure: tcp_ao_add
```c
struct tcp_ao_add {
    struct __kernel_sockaddr_storage addr;  // 128 bytes
    char alg_name[64];                       // e.g., "hmac(sha256)"
    __s32 ifindex;                           // VRF interface
    __u32 set_current:1, set_rnext:1, reserved:30;
    __u16 reserved2;
    __u8 prefix;      // Address prefix length (0=exact match)
    __u8 sndid;       // KeyID for outgoing packets
    __u8 rcvid;       // KeyID for incoming packets
    __u8 maclen;      // MAC length (0=default for algorithm)
    __u8 keyflags;    // TCP_AO_KEYF_* flags
    __u8 keylen;      // Key length
    __u8 key[80];     // Key material
};
// Total size: 128 + 64 + 4 + 4 + 2 + 8 + 80 = 290 bytes (aligned to 8)
```

---

## Implementation Tasks

### Phase 1: Configuration Schema

| Task | File | Status |
|------|------|--------|
| Add `tcp-ao {}` section config | `configuration/tcpao.py` | ✅ |
| Add tcp-ao Container to neighbor schema | `configuration/neighbor/__init__.py` | ✅ |
| Add config-to-session mappings | `configuration/neighbor/__init__.py` | ✅ |

**Config syntax:**
```
neighbor 10.0.0.1 {
    tcp-ao-keyid 1;
    tcp-ao-algorithm hmac-sha-256;
    tcp-ao-password secretkey;
    tcp-ao-base64 false;
}
```

### Phase 2: Session Storage & Validation

| Task | File | Status |
|------|------|--------|
| Add TCP-AO fields to Session class | `bgp/neighbor/session.py` | ✅ |
| Implement `validate_tcp_ao()` method | `bgp/neighbor/session.py` | ✅ |
| Validate mutual exclusion with MD5 | `bgp/neighbor/session.py` | ✅ |

**Validation rules:**
- `tcp-ao-keyid` must be 0-255
- `tcp-ao-algorithm` must be valid Linux kernel algorithm name
- `tcp-ao-password` max 80 bytes
- TCP-AO and MD5 are mutually exclusive

### Phase 3: Socket Option Implementation

| Task | File | Status |
|------|------|--------|
| Add `TCPAOError` exception class | `reactor/network/error.py` | ✅ |
| Implement `tcp_ao()` function | `reactor/network/tcp.py` | ✅ |
| Handle IPv4 sockaddr packing | `reactor/network/tcp.py` | ✅ |
| Handle IPv6 sockaddr packing | `reactor/network/tcp.py` | ✅ |

**Structure packing (Python):**
```python
# tcp_ao_add structure layout:
# - sockaddr_storage: 128 bytes
# - alg_name: 64 bytes (null-terminated string)
# - ifindex: 4 bytes (signed int)
# - flags: 4 bytes (bitfield)
# - reserved2: 2 bytes
# - prefix, sndid, rcvid, maclen, keyflags, keylen: 6 bytes
# - key: 80 bytes
# Total: 288 bytes, aligned to 8 = 288 bytes

TCP_AO_ADD_KEY = 38
TCP_AO_MAXKEYLEN = 80

def tcp_ao(io, ip, port, password, keyid, algorithm, base64=False):
    # Pack sockaddr_storage (same as MD5)
    # Pack algorithm name
    # Pack key material
    io.setsockopt(socket.IPPROTO_TCP, TCP_AO_ADD_KEY, struct_data)
```

### Phase 4: Network Layer Integration

| Task | File | Status |
|------|------|--------|
| Add TCP-AO params to Outgoing.__init__ | `reactor/network/outgoing.py` | ✅ |
| Call tcp_ao() in Outgoing._setup | `reactor/network/outgoing.py` | ✅ |
| Add TCP-AO params to Listener._listen | `reactor/listener.py` | ✅ |
| Add TCP-AO params to Listener.listen_on | `reactor/listener.py` | ✅ |

### Phase 5: Reactor Coordination

| Task | File | Status |
|------|------|--------|
| Wire TCP-AO in passive connection setup | `reactor/loop.py` | ✅ |
| Wire TCP-AO in active connection setup | `reactor/loop.py` | ✅ |
| Extract params in Protocol.connect | `reactor/protocol.py` | ✅ |

### Phase 6: Testing

| Task | Status |
|------|--------|
| Write unit tests for validation | ✅ |
| Write unit tests for struct packing | ✅ |
| Manual testing on Linux (kernel 6.7+) | ⬜ (requires Linux 6.7+) |
| Add functional test if possible | ⬜ (requires two Linux 6.7+ hosts) |

---

## Algorithm Names

Linux kernel crypto algorithm names for TCP-AO:
- `hmac(sha1)` - HMAC-SHA-1-96 (RFC 5926 default)
- `cmac(aes)` - AES-128-CMAC-96 (RFC 5926)
- `hmac(sha256)` - HMAC-SHA-256 (common extension)

User-friendly config values and kernel names:
| Config Value | Kernel Name | Notes |
|--------------|-------------|-------|
| `hmac-sha-1-96` | `hmac(sha1)` | RFC 5926 mandatory |
| `aes-128-cmac-96` | `cmac(aes)` | RFC 5926 mandatory |
| `hmac-sha-256` | `hmac(sha256)` | Common, recommended |

---

## Files to Modify

1. **Configuration parsing:**
   - `src/exabgp/configuration/neighbor/__init__.py`

2. **Session storage:**
   - `src/exabgp/bgp/neighbor/settings.py`
   - `src/exabgp/bgp/neighbor/session.py`

3. **Socket operations:**
   - `src/exabgp/reactor/network/error.py`
   - `src/exabgp/reactor/network/tcp.py`

4. **Network layer:**
   - `src/exabgp/reactor/network/outgoing.py`
   - `src/exabgp/reactor/listener.py`

5. **Reactor coordination:**
   - `src/exabgp/reactor/loop.py`
   - `src/exabgp/reactor/protocol.py`

6. **Tests:**
   - `tests/unit/reactor/network/test_tcp_ao.py` (new)

---

## Risks & Considerations

1. **Kernel version requirement:** TCP-AO requires Linux 6.7+. Need graceful handling on older kernels.
2. **Platform limitation:** Initially Linux-only. FreeBSD/macOS support deferred.
3. **Testing:** Functional testing requires kernel support; may need to be manual/optional.
4. **Mutual exclusion:** TCP-AO and MD5 cannot be used simultaneously on same socket.

---

## References

- [RFC 5925 - TCP Authentication Option](https://datatracker.ietf.org/doc/html/rfc5925)
- [RFC 5926 - Cryptographic Algorithms for TCP-AO](https://datatracker.ietf.org/doc/html/rfc5926)
- [Linux TCP-AO Documentation](https://docs.kernel.org/networking/tcp_ao.html)
- [GitHub Issue #1254](https://github.com/Exa-Networks/exabgp/issues/1254)

---

## Progress Log

### 2025-01-15
- Created implementation plan
- Researched Linux kernel API
- Mapped existing MD5 implementation pattern
- ✅ Implemented all phases:
  - Created `ParseTCPAO` config section with nested syntax
  - Added `tcp_ao()` socket option function with struct packing
  - Added `TCPAOError` exception class
  - Added Session fields and `validate_tcp_ao()` method
  - Wired through Outgoing, Listener, loop.py, protocol.py
  - Added unit tests (12 tests, all passing)
  - All existing tests pass (352/353 - one unrelated failure)
