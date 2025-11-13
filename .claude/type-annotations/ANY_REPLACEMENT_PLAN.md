# Plan: Replace All `Any` Type Annotations

**Status:** Phase 3 Complete ✅
**Total instances:** 160
**Instances fixed:** 65
**Estimated effort:** 4-7 hours
**Approach:** 8 phases, ordered by impact and dependency

---

## ⚠️  Python 3.8.1+ Compatibility REQUIRED

**Before working on ANY phase, read:** `PYTHON38_COMPATIBILITY.md`

ExaBGP must support Python 3.8.1+. All type annotations MUST:
- Use `typing.Optional`, `typing.Union`, `typing.List/Dict/Tuple` (NOT built-in generics)
- Avoid `|` operator (Python 3.10+ only)
- Have `from __future__ import annotations` at top of file
- Use `TYPE_CHECKING` for circular dependency imports

---

## Overview

This plan systematically replaces all `Any` type annotations in ExaBGP with proper, specific types. Work is organized into phases that can be completed independently while respecting dependencies.

**Key Strategy:**
- Use `TYPE_CHECKING` imports to break circular dependencies
- Start with core architecture (highest impact)
- Test after each file/small set of changes
- Document any intentional `Any` usage that remains
- **Maintain Python 3.8.1+ compatibility** (see PYTHON38_COMPATIBILITY.md)

---

## Phase 1: Core Architecture Types 🔴 HIGH PRIORITY

**Goal:** Fix Reactor ↔ Peer ↔ Neighbor circular dependencies
**Impact:** Enables all subsequent type improvements
**Instances:** ~40
**Estimated time:** 2-3 hours

### Files to Update

1. **src/exabgp/reactor/listener.py**
   - Lines 44, 47, 182: `reactor: Any` → `'Reactor'`
   - Line 183: `List[Any]` → `List['Neighbor']`

2. **src/exabgp/reactor/daemon.py**
   - Lines 27, 34: `reactor: Any` → `'Reactor'`

3. **src/exabgp/reactor/peer.py**
   - Lines 90, 98, 99: `neighbor: Any, reactor: Any` → `'Neighbor', 'Reactor'`
   - Line 101: `Optional[Any]` → `Optional['Neighbor']`
   - Lines 250, 254, 262: neighbor parameters → `'Neighbor'`
   - Line 250: `Tuple[Any, Any]` → `Tuple[AFI, SAFI]`
   - Line 276: `connection: Any` → `Union['Incoming', 'Outgoing']`

4. **src/exabgp/reactor/protocol.py**
   - Lines 57, 58, 59: peer/neighbor → `'Peer'`, `'Neighbor'`
   - Line 61: `Optional[Any]` → `Optional[Union['Outgoing', 'Incoming']]`
   - Line 86: `incoming: Any` → `'Incoming'`

5. **src/exabgp/reactor/api/processes.py**
   - Lines 212, 307, 372, 389, 394, 399, 404, 409, 414, 420, 431, 444: neighbor → `'Neighbor'`
   - Line 409: `fsm: Any` → `FSM`
   - Lines 444, 469, 474: message/peer types → specific types

6. **src/exabgp/reactor/loop.py**
   - Line 169: return `Optional[Any]` → `Optional['Neighbor']`
   - Line 190: return `Any` → `Union[Dict[str, Any], str]`

### Implementation Approach

Add to each file:
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from exabgp.reactor.loop import Reactor
    from exabgp.reactor.peer import Peer
    from exabgp.bgp.neighbor import Neighbor
    from exabgp.reactor.network.outgoing import Outgoing
    from exabgp.reactor.network.incoming import Incoming
```

### Testing After Phase 1
```bash
# Lint check
ruff format src/exabgp/reactor && ruff check src/exabgp/reactor

# Unit tests
env exabgp_log_enable=false pytest ./tests/unit/

# Quick functional test
./qa/bin/functional encoding A
```

---

## Phase 2: Generator Return Types ✅ COMPLETE

**Goal:** Specify what generators yield for better type safety
**Impact:** Improves protocol layer type checking
**Instances:** 14 (fixed)
**Completion time:** <1 hour

### Files to Update

1. **src/exabgp/reactor/protocol.py**

All generators currently: `Generator[Any, None, None]`

Replace with specific yield types:
- Line 201: `read_message()` → `Generator[Union[Message, NOP], None, None]`
- Line 338: `read_open()` → `Generator[Union[Open, NOP], None, None]`
- Line 355: `read_keepalive()` → `Generator[KeepAlive, None, None]`
- Lines 371, 394, 407, 416, 429, 436, 457: new_* methods → `Generator[bytes, None, None]`
- Line 463: `new_refresh()` parameter `refresh: Any` → `RouteRefresh`

2. **src/exabgp/reactor/peer.py**
- Lines 369, 376: `_send_open()`, `_read_open()` → `Generator[Union[int, bool], None, None]`

3. **src/exabgp/reactor/keepalive.py**
- Line 28: `generator: Optional[Generator[Any, None, None]]` → `Optional[Generator[bytes, None, None]]`

### Add Imports
```python
from exabgp.bgp.message import Message, Open, KeepAlive, Notify
from exabgp.bgp.message.update import Update
from exabgp.bgp.message.refresh import RouteRefresh
from exabgp.reactor.protocol import NOP
```

### Testing After Phase 2 ✅
```bash
# All tests PASSED
ruff format src/exabgp/reactor && ruff check src/exabgp/reactor  # PASS (1 file reformatted)
env exabgp_log_enable=false pytest ./tests/unit/  # PASS (1376/1376)
./qa/bin/functional encoding A  # PASS
```

---

## Phase 3: Message and Connection Types ✅ COMPLETE

**Goal:** Specify message types in API and handlers
**Impact:** Better type checking for message processing
**Instances:** 11 (fixed)
**Completion time:** <30 minutes

### Files to Update

1. **src/exabgp/reactor/api/__init__.py**
   - Lines 64, 78, 93, 108, 122: `List[Any]` → `List[Change]`
   - Line 133: `peers: Any` → `Dict[str, Peer]`
   - Line 177: `Union[bool, Any]` → `Union[bool, Operational]`

2. **src/exabgp/bgp/message/open/capability/negotiated.py**
   - Lines 28, 29: `Optional[Any]` → `Optional[Open]`

### Add Imports
```python
from exabgp.rib.change import Change
from exabgp.bgp.message import Open, Operational
```

### Testing After Phase 3 ✅
```bash
# All tests PASSED
ruff format src/exabgp/reactor/api src/exabgp/bgp/message && ruff check src  # PASS (no changes)
env exabgp_log_enable=false pytest ./tests/unit/  # PASS (1376/1376)
./qa/bin/functional encoding B  # PASS
```

---

## Phase 4: Configuration Dictionaries 🟢 LOWER PRIORITY

**Goal:** Define structured types for configuration
**Impact:** Better documentation and validation
**Instances:** ~25
**Estimated time:** 1-2 hours

### Approach

Create TypedDict definitions for common structures:

```python
from typing import TypedDict, Union

class EnvironmentValue(TypedDict):
    read: Callable[[str], Any]
    write: Callable[[Any], str]
    value: Union[str, int, bool, List[str]]
    help: str

class ProcessConfig(TypedDict, total=False):
    encoder: str
    run: List[str]
    neighbor: List[str]
    receive: List[str]
    send: List[str]
```

### Files to Update

1. **src/exabgp/environment/environment.py**
   - Line 34: Use EnvironmentValue TypedDict
   - Lines 45, 46, 61-76: Refine types based on usage
   - Line 86: Use consistent config type

2. **src/exabgp/configuration/check.py**
   - Create NeighborConfigDict TypedDict
   - Lines 66, 93-443: Use typed config dicts

3. **src/exabgp/bgp/neighbor.py**
   - Line 57: `Dict[str, Union[bool, int, None, str]]`
   - Line 70: Keep as `Any` (too heterogeneous)

### Decision: Some configs should stay `Any`

**Keep as `Any` where appropriate:**
- Runtime configuration with truly mixed types
- Neighbor defaults (contains IP, HoldTime, TTL, etc.)
- Process configuration values (legitimately heterogeneous)

### Testing After Phase 4
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/test_configuration.py
./qa/bin/parsing
```

---

## Phase 5: Registry/Factory Patterns 🟢 LOWER PRIORITY

**Goal:** Use Generic types for registration patterns
**Impact:** Type-safe decorator patterns
**Instances:** ~15
**Estimated time:** 1 hour

### Files to Update

1. **src/exabgp/reactor/api/command/command.py**
   - Line 14: Better structure for callback dict
   - Line 20: `options: Optional[Dict[str, Any]]`
   - Lines 21, 27: Consider using ParamSpec for decorator types

2. **src/exabgp/bgp/message/update/attribute/sr/srv6/*.py**
   - Use TypeVar for registry patterns:

```python
from typing import TypeVar, Type

T = TypeVar('T', bound='GenericSrv6ServiceSubTlv')

@classmethod
def register(cls) -> Callable[[Type[T]], Type[T]]:
    def decorator(klass: Type[T]) -> Type[T]:
        cls.registered_subtlvs[klass.CODE] = klass
        return klass
    return decorator
```

### Testing After Phase 5
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/
```

---

## Phase 6: Logger and Formatter Types 🟢 LOWER PRIORITY

**Goal:** Proper typing for logging infrastructure
**Impact:** Better type checking for logger usage
**Instances:** ~10
**Estimated time:** 30 minutes

### Files to Update

1. **src/exabgp/logger/__init__.py**
   - Line 22: `ClassVar[Optional[Callable[[str], None]]]`
   - Line 25: `env: Env`
   - Lines 30, 42: `cls: Type[_log]`
   - Line 76: `logger: Callable[[str], None]`

2. **src/exabgp/logger/option.py**
   - Line 19: `ClassVar[Callable[[str], str]]`
   - Lines 63, 97: `env: Env`

3. **src/exabgp/logger/tty.py**
   - Line 14: `Dict[str, TextIO]`

4. **src/exabgp/logger/format.py**
   - Line 12: `FormatterFunc = Callable[[str, str, str, time.struct_time], str]`

### Add Imports
```python
from typing import TextIO
import time
from exabgp.environment import Env
```

### Testing After Phase 6
```bash
ruff format src/exabgp/logger && ruff check src/exabgp/logger
env exabgp_log_enable=false pytest ./tests/unit/
```

---

## Phase 7: Flow Parser and Operations 🟢 LOWER PRIORITY

**Goal:** Type-safe flow specification parsing
**Impact:** Better validation for FlowSpec routes
**Instances:** ~10
**Estimated time:** 1 hour

### Files to Update

1. **src/exabgp/bgp/message/update/nlri/flow.py**

Create TypeVar for operation values:
```python
from typing import TypeVar

ValueType = TypeVar('ValueType', int, 'Protocol', 'Port', 'ICMPType', 'ICMPCode')

class IOperation(Generic[ValueType]):
    value: ValueType
    first: Optional[bool]

    def __init__(self, operations: int, value: ValueType) -> None:
        ...

    def encode(self, value: ValueType) -> Tuple[int, bytes]:
        ...
```

Update:
- Lines 201-202, 204, 214: Use ValueType TypeVar
- Lines 256, 292: Specific Union types
- Lines 316-329: TypeVar in converter/decoder
- Lines 412-455: Specific protocol types

2. **src/exabgp/configuration/flow/*.py**
   - Update `known` dicts: `Dict[str, Callable[[Tokeniser], IOperation]]`
   - Line 184: `tokeniser: Tokeniser, klass: Type[IOperation]` → `Generator[IOperation, None, None]`

### Testing After Phase 7
```bash
ruff format src/exabgp/bgp/message/update/nlri && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/test_flow*.py
./qa/bin/functional encoding | grep -i flow
```

---

## Phase 8: Miscellaneous Types 🟢 LOWER PRIORITY

**Goal:** Clean up remaining `Any` instances
**Impact:** Complete type annotation coverage
**Instances:** ~10
**Estimated time:** 30 minutes

### Files to Update

1. **src/exabgp/bgp/message/update/nlri/mup/*.py**
   - All `json()` methods: `compact: Optional[bool] = None`

2. **src/exabgp/protocol/iso/__init__.py**
   - Line 34: `compact: Optional[bool] = None`

3. **src/exabgp/configuration/static/parser.py**
   - Line 604: `tokeniser: Optional[Tokeniser]` → `Withdrawn`

4. **src/exabgp/reactor/asynchronous.py**
   - Line 22: `Deque[Tuple[str, Union[Generator, Coroutine]]]`

### Testing After Phase 8
```bash
ruff format src && ruff check src
env exabgp_log_enable=false pytest ./tests/unit/
./qa/bin/functional encoding
```

---

## Intentionally Kept as `Any`

These uses of `Any` are appropriate and should remain:

1. **src/exabgp/data/check.py**
   - Line 84: `CHECK_TYPE: Dict[int, Callable[[Any], bool]]` - Generic type checking
   - Line 318: `_flow_numeric(data: Any, ...)` - Generic validation

2. **src/exabgp/util/dictionary.py**
   - Line 19: `default_factory: ... Dict[Any, Any]` - From defaultdict, inherently generic

3. **src/exabgp/reactor/peer.py**
   - Line 66: `__format: Dict[str, Any]` - Mixed formatter functions
   - Line 70: `*args: Tuple[Any, ...]` - Variable args, appropriate
   - Line 756: `cli_data() -> Dict[str, Any]` - Mixed runtime data

4. **src/exabgp/bgp/neighbor.py**
   - Line 70: Neighbor defaults - too heterogeneous (IP, TTL, HoldTime, etc.)

5. **src/exabgp/environment/environment.py**
   - Some config dict values - legitimately mixed types at runtime

**Total kept as `Any`:** ~15-20 instances where it's the correct choice

---

## Testing Strategy

### After Each File Edit
```bash
# Quick syntax check
ruff check <file>

# Format
ruff format <file>
```

### After Each Phase
```bash
# 1. Lint the affected directory/files
ruff format src && ruff check src

# 2. Run unit tests
env exabgp_log_enable=false pytest ./tests/unit/

# 3. Run relevant functional tests
./qa/bin/functional encoding

# 4. If parsers/config changed
./qa/bin/parsing
```

### Before Completion
```bash
# Full test suite
ruff format src && ruff check src
env exabgp_log_enable=false pytest --cov ./tests/unit/
./qa/bin/functional encoding
./qa/bin/parsing
```

---

## Progress Tracking

Use `PROGRESS.md` to track:
- [x] Phase 1: Core Architecture (40 instances) ✅
- [x] Phase 2: Generators (14 instances) ✅
- [x] Phase 3: Messages (11 instances) ✅
- [ ] Phase 4: Configuration (25 instances)
- [ ] Phase 5: Registries (15 instances)
- [ ] Phase 6: Logging (10 instances)
- [ ] Phase 7: Flow Parsers (10 instances)
- [ ] Phase 8: Miscellaneous (10 instances)

**Total to fix:** ~160 instances
**Kept as `Any`:** ~15-20 instances
**Net reduction:** ~85-90% of `Any` usage eliminated

---

## Success Criteria

✅ All tests pass (ruff, pytest, functional)
✅ No new mypy errors introduced
✅ All `Any` either replaced or documented as intentional
✅ TYPE_CHECKING imports properly used for circular dependencies
✅ Generator types properly specify yield values
✅ Configuration types use TypedDict where appropriate
✅ Documentation updated in ANALYSIS.md and PROGRESS.md

---

## Notes

- **Circular dependencies:** Solved with `TYPE_CHECKING` imports
- **Runtime overhead:** None - type annotations are stripped at runtime
- **Compatibility:** No changes to runtime behavior
- **Incremental approach:** Each phase can be completed and tested independently
- **Rollback safe:** Changes are purely type annotations, easy to revert if issues arise

## References

- Full analysis: `ANALYSIS.md`
- Progress tracking: `PROGRESS.md`
- Phase details: `phases/` directory
