# Registry and Extension Patterns

How to extend ExaBGP - adding NLRI types, attributes, capabilities, and API commands.

---

## Overview

ExaBGP uses **registry pattern** for extensibility:
- Classes register themselves via decorators
- Lookup happens via dispatcher at runtime
- No hardcoded lists - all dynamic

**Key registries:**
1. NLRI types → `@NLRI.register(afi, safi)`
2. Attributes → `@Attribute.register()`
3. Messages → `@Message.register(type_code)`
4. Capabilities → `@Capability.register(code)`
5. API Commands → `@Command.register('name')`

---

## Pattern 1: Adding a New NLRI Type

### When to Use
- Adding support for new address family (AFI/SAFI combination)
- Example: New EVPN route type, new FlowSpec family

### Step-by-Step

#### 1. Define AFI/SAFI in protocol/family.py

**If new family not registered:**
```python
# File: src/exabgp/protocol/family.py

class AFI(int):
    ipv4 = 0x01
    ipv6 = 0x02
    # Add new AFI if needed
    new_afi = 0xXX

class SAFI(int):
    unicast = 0x01
    multicast = 0x02
    # Add new SAFI if needed
    new_safi = 0xYY

# Register combination
known_families.append((AFI.new_afi, SAFI.new_safi))
```

#### 2. Create NLRI Class File

**File:** `src/exabgp/bgp/message/update/nlri/{typename}.py`

```python
from __future__ import annotations

from typing import Optional
from exabgp.bgp.message.update.nlri.nlri import NLRI
from exabgp.bgp.message.update.attribute.attributes import Attributes
from exabgp.protocol.family import AFI, SAFI
from exabgp.bgp.message import Action, IN, Negotiated

# Register for one or more AFI/SAFI combinations
@NLRI.register(AFI.new_afi, SAFI.new_safi)
class NewNLRI(NLRI):
    """
    New NLRI type description

    Wire format:
    - Byte 0: ...
    - Byte 1-N: ...
    """

    def __init__(self, field1, field2, action=IN.ANNOUNCED):
        NLRI.__init__(self, AFI.new_afi, SAFI.new_safi, action)
        self.field1 = field1
        self.field2 = field2

    def index(self) -> bytes:
        """
        Unique identifier for this NLRI (used for deduplication)
        Usually returns packed representation
        """
        return self.pack_nlri(None)

    def pack_nlri(self, negotiated: Optional[Negotiated] = None) -> bytes:
        """
        Encode NLRI to bytes for BGP UPDATE message

        Args:
            negotiated: Negotiated capabilities (may be None)

        Returns:
            Encoded bytes (no length prefix - handled by UPDATE)
        """
        # Pack field1, field2, etc.
        data = b''
        data += self.field1.pack()
        data += self.field2.pack()
        return data

    @classmethod
    def unpack_nlri(
        cls,
        afi: AFI,
        safi: SAFI,
        data: bytes,
        action: Action,
        addpath: Optional[int],
        negotiated: Negotiated,
    ) -> NewNLRI:
        """
        Decode NLRI from bytes received in BGP UPDATE

        Args:
            afi: Address Family Identifier
            safi: Subsequent AFI
            data: Raw bytes to parse
            action: ANNOUNCED or WITHDRAWN
            addpath: Path ID if AddPath enabled
            negotiated: Negotiated capabilities

        Returns:
            NewNLRI instance

        Raises:
            Notify: If malformed data
        """
        offset = 0

        # Parse field1
        field1 = Field1.unpack(data[offset:offset+N])
        offset += N

        # Parse field2
        field2 = Field2.unpack(data[offset:offset+M])
        offset += M

        return cls(field1, field2, action)

    def __str__(self) -> str:
        """String representation for logging/display"""
        return f"new-nlri {self.field1} {self.field2}"

    def __repr__(self) -> str:
        """Debugging representation"""
        return f"NewNLRI({self.field1!r}, {self.field2!r})"

    def __hash__(self) -> int:
        """Hash for use in sets/dicts"""
        return hash(self.index())

    def __eq__(self, other) -> bool:
        """Equality comparison"""
        if not isinstance(other, NewNLRI):
            return False
        return self.index() == other.index()
```

#### 3. Register Import in __init__.py

**File:** `src/exabgp/bgp/message/update/nlri/__init__.py`

```python
# Add import to trigger @NLRI.register decorator
from exabgp.bgp.message.update.nlri.newtype import NewNLRI

# Add to __all__ if needed
__all__ = [
    # ... existing
    'NewNLRI',
]
```

**CRITICAL:** Import must execute for registration to happen!

#### 4. Add Configuration Syntax (if applicable)

**File:** `src/exabgp/configuration/announce/new_nlri.py`

Parse config syntax like:
```
neighbor 10.0.0.1 {
    announce new-nlri {
        field1 value1;
        field2 value2;
    }
}
```

Then register in `configuration/configuration.py`

#### 5. Write Unit Tests

**File:** `tests/unit/bgp/message/update/nlri/test_newtype.py`

```python
from exabgp.bgp.message.update.nlri.newtype import NewNLRI
from exabgp.bgp.message import IN
from exabgp.protocol.family import AFI, SAFI

def test_pack_nlri():
    """Test NLRI encoding"""
    nlri = NewNLRI(field1='value1', field2='value2')
    packed = nlri.pack_nlri(None)

    # Verify expected bytes
    assert packed == b'\x...'

def test_unpack_nlri():
    """Test NLRI decoding"""
    data = b'\x...'
    nlri = NewNLRI.unpack_nlri(
        AFI.new_afi,
        SAFI.new_safi,
        data,
        IN.ANNOUNCED,
        None,
        None,
    )

    assert nlri.field1 == 'value1'
    assert nlri.field2 == 'value2'

def test_round_trip():
    """Test pack → unpack returns same object"""
    original = NewNLRI(field1='value1', field2='value2')
    packed = original.pack_nlri(None)
    unpacked = NewNLRI.unpack_nlri(
        AFI.new_afi, SAFI.new_safi, packed, IN.ANNOUNCED, None, None
    )

    assert original == unpacked
```

#### 6. Add Functional Test

**Create files in qa/encoding/:**
- `api-newtype.ci` - Points to config file
- `api-newtype.msg` - Expected BGP messages (hex)
- `etc/exabgp/api-newtype.conf` - ExaBGP config
- `etc/exabgp/run/api-newtype.run` - API commands

**Example .msg file:**
```
option_01:FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF00XX0200000000...
```

**Run test:**
```bash
./qa/bin/functional encoding <test_id>
```

#### 7. Files Modified Summary

✅ Created:
- `src/exabgp/bgp/message/update/nlri/newtype.py`
- `tests/unit/bgp/message/update/nlri/test_newtype.py`
- `qa/encoding/api-newtype.{ci,msg}`
- `etc/exabgp/api-newtype.conf`
- `etc/exabgp/run/api-newtype.run` (if API-based)

✅ Modified:
- `src/exabgp/protocol/family.py` (if new AFI/SAFI)
- `src/exabgp/bgp/message/update/nlri/__init__.py` (import)
- `src/exabgp/configuration/announce/` (if config syntax needed)

---

## Pattern 2: Adding a New Path Attribute

### When to Use
- Implementing new BGP path attribute from RFC
- Example: New community type, new performance metric

### Step-by-Step

#### 1. Create Attribute Class File

**File:** `src/exabgp/bgp/message/update/attribute/{name}.py`

```python
from __future__ import annotations

from typing import Optional
from exabgp.bgp.message.update.attribute.attribute import Attribute
from exabgp.bgp.message import Negotiated

@Attribute.register()
class NewAttribute(Attribute):
    """
    New Attribute description

    RFC XXXX: Brief description

    Wire format:
    - Flags: 0xC0 (well-known mandatory) or 0x80 (optional transitive)
    - Code: 0xNN
    - Length: variable
    - Value: ...
    """

    ID = 0xNN  # Attribute code from RFC
    FLAG = 0xC0  # Or 0x80, 0x40, etc.

    def __init__(self, value):
        Attribute.__init__(self)
        self.value = value

    def pack(self, negotiated: Optional[Negotiated] = None) -> bytes:
        """
        Encode attribute value (NOT including flags/code/length)

        Args:
            negotiated: Negotiated capabilities

        Returns:
            Attribute value bytes
        """
        return self.value.pack()

    @classmethod
    def unpack(cls, data: bytes, negotiated: Optional[Negotiated] = None) -> NewAttribute:
        """
        Decode attribute value

        Args:
            data: Attribute value bytes (after flags/code/length)
            negotiated: Negotiated capabilities

        Returns:
            NewAttribute instance
        """
        value = Value.unpack(data)
        return cls(value)

    def __str__(self) -> str:
        return f"new-attribute {self.value}"

    def __repr__(self) -> str:
        return f"NewAttribute({self.value!r})"

    def __hash__(self) -> int:
        return hash(self.value)

    def __eq__(self, other) -> bool:
        if not isinstance(other, NewAttribute):
            return False
        return self.value == other.value
```

#### 2. Register Import in __init__.py

**File:** `src/exabgp/bgp/message/update/attribute/__init__.py`

```python
from exabgp.bgp.message.update.attribute.newattr import NewAttribute

__all__ = [
    # ... existing
    'NewAttribute',
]
```

#### 3. Add to Attributes Collection (if needed)

**File:** `src/exabgp/bgp/message/update/attribute/attributes.py`

Only if special handling needed (most attributes auto-register):

```python
class Attributes(dict):
    # ...

    def add(self, attribute: Attribute) -> None:
        """Add attribute to collection"""
        self[attribute.ID] = attribute
```

#### 4. Add Configuration Syntax

**File:** Update relevant config parser

```python
# In configuration/announce/ or configuration/neighbor/
def parse_attribute(tokens):
    if tokens[0] == 'new-attribute':
        value = tokens[1]
        return NewAttribute(value)
```

#### 5. Write Tests

**File:** `tests/unit/bgp/message/update/attribute/test_newattr.py`

```python
from exabgp.bgp.message.update.attribute.newattr import NewAttribute

def test_pack():
    attr = NewAttribute(value='test')
    packed = attr.pack(None)
    assert packed == b'\x...'

def test_unpack():
    data = b'\x...'
    attr = NewAttribute.unpack(data, None)
    assert attr.value == 'test'

def test_round_trip():
    original = NewAttribute(value='test')
    packed = original.pack(None)
    unpacked = NewAttribute.unpack(packed, None)
    assert original == unpacked
```

---

## Pattern 3: Adding an API Command

### When to Use
- Adding new CLI/API functionality
- Example: New show command, new route manipulation

### Step-by-Step

#### 1. Choose Command File

**Location:** `src/exabgp/reactor/api/command/{category}.py`

Categories:
- `announce.py` - Route announcements
- `neighbor.py` - Neighbor operations
- `peer.py` - Peer lifecycle
- `rib.py` - RIB operations
- `reactor.py` - Reactor status

#### 2. Define Command Function

```python
from exabgp.reactor.api.command.command import Command

@Command.register(
    'new command',  # Command name (space-separated)
    neighbor=True,   # Supports neighbor filtering?
    json_support=True  # Supports --json flag?
)
def new_command_handler(self, reactor, service, line, use_json=False):
    """
    Handler for 'new command' API/CLI command

    Args:
        self: Reactor instance
        reactor: Reactor instance (same as self)
        service: Service name (api, cli, etc.)
        line: Full command line
        use_json: True if --json flag present

    Yields:
        Response strings to send back
    """

    # Parse command arguments
    parts = line.split()
    if len(parts) < 3:
        yield 'error: insufficient arguments\n'
        return

    arg1 = parts[2]

    # Perform operation
    for peer in reactor.peers():
        # Access peer state
        if peer.state == 'established':
            result = do_something(peer, arg1)

            if use_json:
                import json
                yield json.dumps({'peer': str(peer), 'result': result}) + '\n'
            else:
                yield f"peer {peer}: {result}\n"

    yield 'done\n'
```

#### 3. Register Command Category

**File:** `src/exabgp/reactor/api/command/__init__.py`

```python
from exabgp.reactor.api.command import newcategory

# Import triggers @Command.register
```

#### 4. Add Command Metadata (Optional)

**File:** `src/exabgp/reactor/api/command/registry.py`

```python
COMMAND_DESCRIPTIONS = {
    'new command': 'Description of what it does',
}
```

#### 5. Write Tests

**File:** `tests/unit/reactor/api/test_command_newcmd.py`

```python
def test_new_command():
    # Mock reactor, peers, etc.
    # Call command handler
    # Verify output
    pass
```

---

## Pattern 4: Adding a Capability

### When to Use
- Implementing new BGP capability from RFC
- Example: New extended capability, new feature negotiation

### Step-by-Step

#### 1. Create Capability Class

**File:** `src/exabgp/bgp/message/open/capability/{name}.py`

```python
from exabgp.bgp.message.open.capability.capability import Capability

@Capability.register(code=0xNN)  # Capability code from RFC
class NewCapability(Capability):
    """
    New Capability description (RFC XXXX)
    """

    def __init__(self, value):
        Capability.__init__(self)
        self.value = value

    def pack(self) -> bytes:
        """Encode capability value"""
        return self.value.pack()

    @classmethod
    def unpack(cls, data: bytes) -> NewCapability:
        """Decode capability value"""
        value = Value.unpack(data)
        return cls(value)
```

#### 2. Register in __init__.py

**File:** `src/exabgp/bgp/message/open/capability/__init__.py`

```python
from exabgp.bgp.message.open.capability.newcap import NewCapability
```

---

## Common Pitfalls

### ❌ Forgetting to Import

Registration doesn't happen unless module imported:
```python
# This doesn't work:
# File exists but never imported → Not registered

# Fix: Add to __init__.py
from exabgp.bgp.message.update.nlri.newtype import NewNLRI
```

### ❌ Wrong Signature

`pack_nlri(negotiated)` and `unpack_nlri(...)` have fixed signatures:
```python
# Wrong:
def pack_nlri(self):  # Missing negotiated

# Right:
def pack_nlri(self, negotiated: Optional[Negotiated] = None):
```

### ❌ Not Handling None

`negotiated` can be None in some contexts:
```python
# Wrong:
def pack_nlri(self, negotiated):
    if negotiated.asn4:  # Crashes if None!

# Right:
def pack_nlri(self, negotiated):
    if negotiated and negotiated.asn4:
```

### ❌ Unused negotiated Parameter

It's OK and expected:
```python
# This is FINE:
def pack(self, negotiated: Negotiated) -> bytes:
    return self.value.pack()  # negotiated unused
```

See `CODING_STANDARDS.md` - unused `negotiated` parameters are acceptable.

---

## Testing Checklist

Before declaring new type complete:

- [ ] Unit tests pass (pytest)
- [ ] Functional test added (qa/encoding/)
- [ ] Functional test passes (./qa/bin/functional encoding <id>)
- [ ] Linting passes (ruff format + ruff check)
- [ ] Python 3.8+ compatibility (`Union`, not `|`)
- [ ] Documentation updated (if public API)

---

**See also:**
- `CODEBASE_ARCHITECTURE.md` - Where files go
- `DATA_FLOW_GUIDE.md` - How registration fits into data flow
- `CODING_STANDARDS.md` - Python version, API requirements
- `TESTING_PROTOCOL.md` - Test requirements

---

**Updated:** 2025-11-24
