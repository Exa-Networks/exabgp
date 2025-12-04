# Wave 6 NLRI Refactoring - Work in Progress

## Overview

Wave 6 of the packed-bytes-first refactoring covers NLRI types:
- `nlri/cidr.py`
- `nlri/inet.py`
- `nlri/label.py`
- `nlri/ipvpn.py`
- (remaining: `nlri/vpls.py`, `nlri/rtc.py`, `nlri/flow.py`)

## Problem Summary

The packed-bytes-first pattern stores wire-format bytes in `_packed` and extracts values via properties. For NLRI classes, this creates a **chicken-and-egg problem**:

1. **SAFI determines format**: Properties like `rd`, `labels`, `cidr` need to know what's in `_packed` to extract correctly
2. **Format determines SAFI**: SAFI should be set based on what's actually in `_packed` (labels → nlri_mpls, rd → mpls_vpn)

### Specific Issues Encountered

#### Issue 1: Setters using constant RD_SIZE_BITS

**Problem**: IPVPN setters used `RD_SIZE_BITS = 64` constant even when RD was NORD (empty).

```python
# Before (broken)
mask = len(value) * 8 + RD_SIZE_BITS + current_cidr.mask

# After (fixed)
mask = len(value) * 8 + len(current_rd) * 8 + current_cidr.mask
```

**Files changed**: `ipvpn.py` lines 86, 101, 260

#### Issue 2: Properties depending on SAFI

**Problem**: When NLRI is created with unicast SAFI (from config parsing), properties check `safi.has_label()` or `safi.has_rd()` which return False, causing incorrect extraction.

**Example flow**:
1. `IPVPN.from_cidr()` creates with `safi=unicast`, `_packed=[mask][prefix]`
2. `nlri.labels = Labels([20012])` sets labels, `_packed` becomes `[mask+24][labels][prefix]`
3. `nlri.rd = RD(...)` is called
4. rd setter calls `self.labels` → `_parse_labels()` checks `safi.has_label()` → False → returns `[]`
5. rd setter calls `self.cidr` with wrong offset → **CRASH**

**Solution attempted**: Make `_parse_labels()` detect labels from mask value instead of SAFI:

```python
# Detect labels by checking if mask exceeds max prefix for AFI
max_prefix = 32 if self.afi == AFI.ipv4 else 128
has_labels = self.safi.has_label() or mask > max_prefix
```

#### Issue 3: Configuration parser sets SAFI prematurely

**Problem**: `static/__init__.py` creates NLRI with final SAFI before attributes are set:

```python
# This sets safi=mpls_vpn before rd is actually in _packed
nlri = IPVPN.from_cidr(cidr, afi, SAFI.mpls_vpn, action)
```

**Solution attempted**: Create with unicast SAFI initially, let setters/post() upgrade:

```python
# Create with unicast, setters will detect format from _packed
nlri = IPVPN.from_cidr(cidr, afi, IP.tosafi(ip), action)
```

## Changes Made

### `label.py`

1. Updated `_parse_labels()` to detect labels from mask value (not just SAFI):
   - For IPv4: `mask > 32` implies labels present
   - For IPv6: `mask > 128` implies labels present

### `ipvpn.py`

1. Added `_detect_rd_presence(labels_bytes)` helper method
2. Updated `rd` property to always try `_parse_labels()` (uses mask detection)
3. Updated `cidr` property to always try `_parse_labels()` (uses mask detection)
4. Fixed `rd.setter` to use `len(value) * 8` instead of `RD_SIZE_BITS`
5. Fixed `labels.setter` to use `len(current_rd) * 8` instead of `RD_SIZE_BITS`
6. Fixed `index()` to use `len(self.rd) * 8` instead of `RD_SIZE_BITS`

### `static/__init__.py`

1. Changed `route()` and `attributes()` functions to create NLRI with unicast SAFI initially

## Current Status

### Working
- `conf-addpath.conf` - validates and encodes correctly

### Failing
- `conf-parity.conf` - parses but fails encoding verification for IPv6 mpls-vpn routes
  - Error: `could not decode IPVPN NLRI with family ipv6 (AFI 2) mpls-vpn (SAFI 128)`
  - This appears to be an encode/decode round-trip issue, not a parsing issue

## Remaining Work

1. **Fix conf-parity.conf encoding issue**: The IPv6 mpls-vpn routes encode incorrectly
   - Need to trace through `pack_nlri()` and `unpack_nlri()` for IPv6

2. **Update unit tests**: Add tests for the new mask-based detection logic

3. **Consider alternative approach**: Instead of mask-based detection, store flags indicating what's in `_packed`:
   ```python
   self._has_labels_in_packed = False
   self._has_rd_in_packed = False
   ```

4. **Continue Wave 6**: Apply pattern to remaining files:
   - `nlri/vpls.py`
   - `nlri/rtc.py`
   - `nlri/flow.py`

## Key Insights

1. The packed-bytes-first pattern works well when `_packed` format is **fixed** for a class
2. For NLRI classes where format **varies** (labels optional, RD optional), need additional detection logic
3. SAFI metadata and `_packed` contents must stay synchronized
4. Mask-based detection works for labels (mask > max_prefix), but RD detection needs length heuristics

## Test Commands

```bash
# Validate specific config
./sbin/exabgp configuration validate -nrv ./etc/exabgp/conf-addpath.conf

# Run unit tests
env exabgp_log_enable=false uv run pytest ./tests/unit/ -x -q

# Debug with traceback
env exabgp_debug_configuration=true ./sbin/exabgp configuration validate -nrv ./etc/exabgp/conf-parity.conf
```
