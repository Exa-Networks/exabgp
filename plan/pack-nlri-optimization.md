# Pack NLRI Optimization Plan

**Status:** ✅ Complete
**Created:** 2025-12-08

## Goal

The "packed-bytes-first" pattern requires that wire-format bytes are stored at construction time, and `pack_*` methods simply return those stored bytes without calculation or concatenation.

Currently, several `pack_nlri()` methods violate this by:
- Calling `struct.pack()` to build headers at pack time
- Concatenating multiple byte sequences at pack time
- Calculating lengths at pack time

This plan eliminates these violations so `pack_nlri()` becomes a simple `return self._packed`.

---

## File 1: inet.py (lines 281-290)

### Current Code
```python
def pack_nlri(self, negotiated: 'Negotiated') -> bytes:
    if negotiated.addpath.send(self.afi, self.safi):
        if self.path_info is PathInfo.DISABLED:
            addpath = PathInfo.NOPATH.pack_path()
        else:
            addpath = self.path_info.pack_path()
    else:
        addpath = b''
    return bytes(addpath) + self._packed
```

### Problem
Even when `addpath` is empty (`b''`), we still do `bytes(b'') + self._packed` which creates a new bytes object unnecessarily. This is the most common case (most BGP sessions don't use ADD-PATH).

### Solution
Add an early return for the happy path (no ADD-PATH):

```python
def pack_nlri(self, negotiated: 'Negotiated') -> bytes:
    if not negotiated.addpath.send(self.afi, self.safi):
        return self._packed  # Happy path - zero copy

    # ADD-PATH case - must prepend path ID
    if self.path_info is PathInfo.DISABLED:
        addpath = PathInfo.NOPATH.pack_path()
    else:
        addpath = self.path_info.pack_path()
    return bytes(addpath) + self._packed
```

### Why Not Store ADD-PATH in _packed?
ADD-PATH is negotiated per-session. The same NLRI object may be sent to multiple peers, some with ADD-PATH and some without. We cannot know at construction time which format to use.

### Files to Change
- `src/exabgp/bgp/message/update/nlri/inet.py`

### Also Apply To
- `src/exabgp/bgp/message/update/nlri/label.py` - same pattern
- `src/exabgp/bgp/message/update/nlri/ipvpn.py` - same pattern

---

## File 2: rtc.py (lines 140-146)

### Current Code
```python
def pack_nlri(self, negotiated: Negotiated) -> Buffer:
    if self.rt and self._packed_origin:
        packedRT = self.rt.pack_attribute(negotiated)
        return pack('!B', len(self)) + self._packed_origin + bytes([RTC.resetFlags(packedRT[0])]) + packedRT[1:]
    return pack('!B', 0)
```

### Problem
1. Calls `self.rt.pack_attribute(negotiated)` at pack time
2. Calls `struct.pack('!B', len(self))` at pack time
3. Calls `RTC.resetFlags()` at pack time
4. Multiple concatenations

### Why This Is Fixable
Investigation showed that `ExtendedCommunityBase.pack_attribute()` ignores the `negotiated` parameter - it just returns `self._packed`. So the RT bytes are already known at construction time.

### Solution
Store the complete wire format in `_packed` at construction time:

In the factory method (e.g., `make_rtc()` or `__init__`):
```python
# At construction time:
if rt and packed_origin:
    rt_packed = rt._packed  # RT bytes are already available
    rt_with_flags_reset = bytes([RTC.resetFlags(rt_packed[0])]) + rt_packed[1:]
    length = len(packed_origin) + len(rt_with_flags_reset)
    self._packed = pack('!B', length) + packed_origin + rt_with_flags_reset
else:
    self._packed = pack('!B', 0)
```

Then `pack_nlri()` becomes:
```python
def pack_nlri(self, negotiated: Negotiated) -> Buffer:
    return self._packed
```

### Files to Change
- `src/exabgp/bgp/message/update/nlri/rtc.py`

---

## File 3: bgpls/nlri.py (line 109)

### Current Code
```python
def pack_nlri(self, negotiated: Negotiated) -> Buffer:
    return pack('!BB', self.CODE, len(self._packed)) + self._packed
```

### Problem
Every call to `pack_nlri()`:
1. Calls `struct.pack('!BB', ...)` to create 2-byte header
2. Concatenates header + payload

### Why This Is Fixable
- `self.CODE` is a class variable, known at class definition time
- `len(self._packed)` is known as soon as `_packed` is set
- Therefore, the complete wire format can be computed at construction time

### Solution
In each BGP-LS NLRI subclass factory method, prepend the TLV header when setting `_packed`:

```python
# At construction time (in make_* or unpack methods):
payload = ...  # the current _packed content
self._packed = pack('!BB', self.CODE, len(payload)) + payload
```

Then base class `pack_nlri()` becomes:
```python
def pack_nlri(self, negotiated: Negotiated) -> Buffer:
    return self._packed
```

### Subclasses to Update
All BGP-LS NLRI types that inherit from the base class:
- `src/exabgp/bgp/message/update/nlri/bgpls/node.py`
- `src/exabgp/bgp/message/update/nlri/bgpls/link.py`
- `src/exabgp/bgp/message/update/nlri/bgpls/prefixv4.py`
- `src/exabgp/bgp/message/update/nlri/bgpls/prefixv6.py`
- `src/exabgp/bgp/message/update/nlri/bgpls/srv6sid.py`

### Note
The `index()` method also builds the same header. After this change, `index()` can return `Family.index(self) + self._packed` without re-packing.

---

## File 4: mup/nlri.py (line 87)

### Current Code
```python
def pack_nlri(self, negotiated: Negotiated) -> Buffer:
    return pack('!BHB', self.ARCHTYPE, self.CODE, len(self._packed)) + self._packed
```

### Problem
Same as BGP-LS but with a 4-byte header instead of 2-byte:
- `ARCHTYPE` (1 byte)
- `CODE` (2 bytes)
- `length` (1 byte)

### Solution
Same pattern as BGP-LS. In each MUP NLRI subclass factory method:

```python
# At construction time:
payload = ...  # the current _packed content
self._packed = pack('!BHB', self.ARCHTYPE, self.CODE, len(payload)) + payload
```

Then base class `pack_nlri()` becomes:
```python
def pack_nlri(self, negotiated: Negotiated) -> Buffer:
    return self._packed
```

### Subclasses to Update
- `src/exabgp/bgp/message/update/nlri/mup/isd.py`
- `src/exabgp/bgp/message/update/nlri/mup/dsd.py`
- `src/exabgp/bgp/message/update/nlri/mup/t1st.py`
- `src/exabgp/bgp/message/update/nlri/mup/t2st.py`

---

## File 5: cidr.py (lines 218-219)

### Current Code
```python
def pack_nlri(self) -> bytes:
    return bytes([self.mask]) + bytes(self._packed[: CIDR.size(self.mask)])
```

### Problem
1. Creates new bytes object for mask
2. Slices `_packed` based on mask (CIDR stores full padded IP address)
3. Concatenates mask + truncated IP

### Current Storage
CIDR stores the full IP address in `_packed`, padded to AFI length (4 bytes for IPv4, 16 for IPv6). At pack time, it truncates to the number of bytes needed for the prefix length.

### Solution
Change CIDR to store the already-truncated wire format:

```python
# At construction time:
# Instead of: self._packed = full_ip_bytes (padded)
# Store: self._packed = bytes([mask]) + truncated_ip_bytes
```

Then `pack_nlri()` becomes:
```python
def pack_nlri(self) -> bytes:
    return self._packed
```

### Impact Analysis
This change affects other methods that use `_packed`:
- `ton()` - returns full IP for protocol use, needs adjustment
- `top()` - returns IP string, needs adjustment
- `index()` - currently builds same format, would simplify
- `pack_ip()` - returns truncated IP without mask, needs adjustment

### Recommended Approach
Store two representations:
- `_packed` = wire format `[mask][truncated_ip]` for `pack_nlri()`
- `_ip` = full padded IP bytes for `ton()`, `top()`, etc.

Or derive full IP from truncated + mask when needed (rare path).

### Files to Change
- `src/exabgp/bgp/message/update/nlri/cidr.py`
- Verify all CIDR subclasses and usages

---

## Implementation Order

1. ✅ **inet.py** - Early return for non-ADD-PATH (label.py, ipvpn.py already had this)
2. ✅ **rtc.py** - Full packed-bytes-first conversion
3. ✅ **bgpls/nlri.py** - Already converted (header in `_packed`)
4. ✅ **mup/nlri.py** - Full packed-bytes-first conversion (+ all subclasses: isd, dsd, t1st, t2st)
5. ⏭️ **cidr.py** - **SKIPPED** (see analysis below)

### cidr.py Analysis

`cidr.pack_nlri()` is only called at NLRI construction time (3 call sites):
- `inet.py:155` in `INET.from_cidr()`
- `label.py:167` in `Label.from_cidr()`
- `ipvpn.py:196` in `IPVPN.from_cidr()`

The result is stored in the NLRI's `_packed` field, and the NLRI's `pack_nlri()` returns it directly.

**Conclusion:** Converting CIDR is not worthwhile because:
1. The hot path (NLRI.pack_nlri) already returns stored bytes directly
2. CIDR.pack_nlri() is only called once per NLRI construction
3. Converting CIDR would require dual storage (`_packed` for wire, `_ip` for full IP) with high complexity

---

## Testing Strategy

After each file change:
```bash
./qa/bin/test_everything
```

Pay special attention to:
- Encoding functional tests (`./qa/bin/functional encoding`)
- Decoding functional tests (`./qa/bin/functional decoding`)
- Round-trip tests in `tests/unit/bgp/message/update/`

---

## Success Criteria

- [x] All `pack_nlri()` methods return `self._packed` directly (or with simple addpath prefix)
- [x] No `struct.pack()` calls in `pack_nlri()` methods (except CIDR - construction only)
- [x] No concatenation in hot path (non-addpath case)
- [x] All tests pass (11/11)
- [x] No change in wire format (byte-for-byte identical output)
