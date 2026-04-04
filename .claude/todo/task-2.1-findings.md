# Task 2.1 Findings: BGP UPDATE Message Parser Analysis

**Date**: 2025-11-08
**File Analyzed**: `/home/user/exabgp/src/exabgp/bgp/message/update/__init__.py`
**Methods**: `split()` (lines 81-102), `unpack_message()` (lines 253-330)

---

## UPDATE Message Structure (RFC 4271)

```
+-----------------------------------------------------+
|   Withdrawn Routes Length (2 octets)                |  Bytes 0-1
+-----------------------------------------------------+
|   Withdrawn Routes (variable)                       |  Bytes 2 to 2+withdrawn_len
+-----------------------------------------------------+
|   Total Path Attribute Length (2 octets)            |  Bytes 2+withdrawn_len to 4+withdrawn_len
+-----------------------------------------------------+
|   Path Attributes (variable)                        |  Bytes 4+withdrawn_len to 4+withdrawn_len+attr_len
+-----------------------------------------------------+
|   Network Layer Reachability Information (variable) |  Remaining bytes
+-----------------------------------------------------+
```

### Prefix Format (Withdrawn and NLRI)
```
+---------------------------+
|   Length (1 octet)        |  Prefix length in bits
+---------------------------+
|   Prefix (variable)       |  ceil(length/8) bytes
+---------------------------+
```

---

## Questions Answered

### 1. What does unpack_message() return?
**Returns**: `Update` object or `EOR` (End-of-RIB) object

**Return types**:
- `Update(nlris, attributes)` - Normal UPDATE message (line 319)
- `EOR(AFI.ipv4, SAFI.unicast)` - IPv4 unicast EOR (line 260, 312)
- `EOR(afi, safi)` - Multi-protocol EOR (line 262, 314, 316)

### 2. What parameters does it take?
**Parameters** (line 253):
- `data` (bytes): The UPDATE message body (without 19-byte BGP header)
- `direction` (Direction): IN or OUT
- `negotiated` (Negotiated): Negotiated capabilities (AddPath, families, etc.)

### 3. How are lengths validated?

#### Withdrawn Routes Length (lines 84-88)
```python
len_withdrawn = unpack('!H', data[0:2])[0]
withdrawn = data[2 : len_withdrawn + 2]

if len(withdrawn) != len_withdrawn:
    raise Notify(3, 1, 'invalid withdrawn routes length, not enough data available')
```
- **Error Code**: Notify(3, 1) = UPDATE Message Error / Malformed Attribute List

#### Path Attributes Length (lines 90-97)
```python
len_attributes = unpack('!H', data[len_withdrawn + 2 : start_attributes])[0]
start_announced = len_withdrawn + len_attributes + 4
attributes = data[start_attributes:start_announced]

if len(attributes) != len_attributes:
    raise Notify(3, 1, 'invalid total path attribute length, not enough data available')
```
- **Error Code**: Notify(3, 1) = UPDATE Message Error / Malformed Attribute List

#### Total Message Length (lines 99-100)
```python
if 2 + len_withdrawn + 2 + len_attributes + len(announced) != length:
    raise Notify(3, 1, 'error in BGP message length, not enough data for the size announced')
```
- **Formula**: `2 (withdrawn_len) + withdrawn_routes + 2 (attr_len) + attributes + nlri = total`

### 4. What happens if lengths don't match data?
**All mismatches raise `Notify(3, 1)`** with descriptive messages:
1. Withdrawn routes length mismatch → `'invalid withdrawn routes length...'`
2. Path attributes length mismatch → `'invalid total path attribute length...'`
3. Total message length mismatch → `'error in BGP message length...'`

### 5. What are the minimum/maximum sizes?

#### Minimum UPDATE Message
- **4 bytes**: EOR marker `\x00\x00\x00\x00` (line 259)
- **11 bytes**: Multi-protocol EOR (line 261)
- **4 bytes**: Empty UPDATE `\x00\x00` (no withdrawals) + `\x00\x00` (no attributes)

#### Maximum UPDATE Message
- **Standard**: 4096 bytes (from Message.HEADER_LEN + body)
- **Extended**: 65535 bytes (if Extended Message capability negotiated)

#### Field Limits
- **Withdrawn Routes Length**: 0-65535 (2 bytes, big-endian)
- **Path Attributes Length**: 0-65535 (2 bytes, big-endian)
- **NLRI**: Remaining space after withdrawn + attributes

---

## Parsing Flow

### Step 1: Special Case Detection (lines 259-262)
```python
if length == 4 and data == b'\x00\x00\x00\x00':
    return EOR(AFI.ipv4, SAFI.unicast)  # IPv4 unicast EOR

if length == 11 and data.startswith(EOR.NLRI.PREFIX):
    return EOR.unpack_message(data, direction, negotiated)  # MP-EOR
```

### Step 2: Split Message (line 264)
```python
withdrawn, _attributes, announced = cls.split(data)
```
Calls `split()` method which:
1. Extracts withdrawn routes length (2 bytes)
2. Validates and extracts withdrawn routes
3. Extracts path attributes length (2 bytes)
4. Validates and extracts path attributes
5. Extracts announced NLRI (remaining data)
6. Validates total lengths match

### Step 3: Parse Attributes (line 269)
```python
attributes = Attributes.unpack(_attributes, direction, negotiated)
```
Parses path attributes (delegated to `Attributes.unpack()`)

### Step 4: Extract Next-Hop (line 281)
```python
nexthop = attributes.get(Attribute.CODE.NEXT_HOP, NoNextHop)
```

### Step 5: Parse Withdrawn Routes (lines 287-291)
```python
while withdrawn:
    nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, withdrawn, Action.WITHDRAW, addpath)
    withdrawn = left
    nlris.append(nlri)
```

### Step 6: Parse Announced Routes (lines 293-298)
```python
while announced:
    nlri, left = NLRI.unpack_nlri(AFI.ipv4, SAFI.unicast, announced, Action.ANNOUNCE, addpath)
    nlri.nexthop = nexthop
    announced = left
    nlris.append(nlri)
```

### Step 7: Handle MP-BGP (lines 300-307)
```python
unreach = attributes.pop(MPURNLRI.ID, None)
reach = attributes.pop(MPRNLRI.ID, None)

if unreach is not None:
    nlris.extend(unreach.nlris)

if reach is not None:
    nlris.extend(reach.nlris)
```

### Step 8: Detect EOR (lines 309-317)
If no attributes and no NLRIs, check if it's an EOR marker

### Step 9: Return UPDATE (line 319)
```python
return Update(nlris, attributes)
```

---

## Exception Types

### From split() method
- **`Notify(3, 1, ...)`** - UPDATE Message Error / Malformed Attribute List
  - Invalid withdrawn routes length
  - Invalid path attributes length
  - Invalid total message length

### From unpack_message() method
- **`ValueError`** - (mentioned in comment line 251, raised by called functions)
- **`IndexError`** - (mentioned in comment line 251, from array access)
- **`TypeError`** - (mentioned in comment line 251, from type mismatches)
- **`struct.error`** - (mentioned in comment line 251, from unpack failures)

### From called functions
- `Attributes.unpack()` - Various attribute parsing errors
- `NLRI.unpack_nlri()` - NLRI parsing errors

---

## Edge Cases

### 1. Empty UPDATE (EOR - End-of-RIB)
- **IPv4 Unicast EOR**: `\x00\x00\x00\x00` (4 bytes)
- **Multi-protocol EOR**: 11 bytes starting with EOR.NLRI.PREFIX
- **Implicit EOR**: No attributes + no NLRIs (lines 309-317)

### 2. Minimal Valid UPDATE
```
\x00\x00  # Withdrawn routes length = 0
\x00\x00  # Path attributes length = 0
# No NLRI
```
Total: 4 bytes (would be detected as EOR)

### 3. Withdrawals Only
```
\x00\x05  # Withdrawn routes length = 5
[5 bytes of withdrawals]
\x00\x00  # Path attributes length = 0
# No NLRI
```

### 4. Announcements Only
```
\x00\x00  # Withdrawn routes length = 0
[attributes with length]
[NLRI data]
```

### 5. MP-BGP Only (no IPv4 unicast)
Uses MP_REACH_NLRI and MP_UNREACH_NLRI attributes instead of withdrawn/announced fields

---

## Testing Strategy

### Critical Paths to Test

1. **Length Validation**
   - Withdrawn routes length too large
   - Path attributes length too large
   - Total length mismatch
   - Off-by-one errors
   - Integer overflow (65536 wraps to 0)

2. **EOR Detection**
   - Valid EOR markers
   - Invalid EOR-like data
   - Edge cases around 4 and 11 byte messages

3. **Empty Fields**
   - No withdrawals
   - No attributes
   - No NLRI
   - All empty (EOR)

4. **Truncation**
   - Truncated in withdrawn length field
   - Truncated in withdrawn routes
   - Truncated in attributes length field
   - Truncated in attributes
   - Missing NLRI

5. **Overflow/Underflow**
   - Length fields that exceed message bounds
   - Negative effective lengths (wraparound)

6. **NLRI Parsing**
   - Invalid prefix lengths (>32 for IPv4)
   - Truncated prefixes
   - Extra data after prefixes

---

## Files to Test

### Primary Target
- `src/exabgp/bgp/message/update/__init__.py::split()` (lines 81-102)
- `src/exabgp/bgp/message/update/__init__.py::unpack_message()` (lines 253-330)

### Secondary Targets (for comprehensive testing)
- `src/exabgp/bgp/message/update/attribute/__init__.py::Attributes.unpack()`
- `src/exabgp/bgp/message/update/nlri/__init__.py::NLRI.unpack_nlri()`

---

## Coverage Goals

- **split()**: 100% - All validation paths
- **unpack_message()**: 90%+ - Main parsing logic
- **Edge cases**: All EOR detection paths
- **Error paths**: All Notify(3, 1) raises

---

## Next Steps

1. Create test helpers for UPDATE message construction
2. Add fuzzing tests for `split()` length validation
3. Add EOR detection tests
4. Add truncation tests
5. Add NLRI parsing tests
6. Measure coverage
