# Comprehensive Analysis of `Any` Type Usage in ExaBGP

**Generated:** 2025-11-13
**Total instances found:** 150+
**Files affected:** 32+

## Executive Summary

This document catalogs every use of the `Any` type annotation in the ExaBGP codebase. Each entry includes:
- Exact file path and line number
- Context (function/method/class)
- Current usage with `Any`
- Recommended replacement type

## Pattern Categories

1. **Circular Dependencies** (Reactor ↔ Peer ↔ Neighbor): ~40 occurrences
2. **Generator Yield Types**: ~30 occurrences
3. **Configuration Dictionaries**: ~25 occurrences
4. **Message Type Parameters**: ~20 occurrences
5. **Registry/Factory Patterns**: ~15 occurrences
6. **Logger/Formatter Callables**: ~10 occurrences
7. **Flow Parser Generics**: ~10 occurrences

---

## Category 1: Core Architecture - Reactor/Peer/Neighbor

### src/exabgp/reactor/listener.py

**Import:** Line 14
```python
from typing import Any, ClassVar, Dict, Generator, List, Optional, Tuple
```

**Occurrences:**

1. **Line 44** - Constructor parameter
```python
def __init__(self, reactor: Any, backlog: int = 200) -> None:
```
**Recommended:** `reactor: 'Reactor'`
**Fix approach:** Use TYPE_CHECKING import

2. **Line 47** - Instance variable
```python
self._reactor: Any = reactor
```
**Recommended:** `self._reactor: 'Reactor' = reactor`

3. **Line 182** - Local variable
```python
reactor: Any = self._reactor
```
**Recommended:** `reactor: Reactor = self._reactor`

4. **Line 183** - Ranged neighbor list
```python
ranged_neighbor: List[Any] = []
```
**Recommended:** `ranged_neighbor: List['Neighbor'] = []`

---

### src/exabgp/reactor/daemon.py

**Import:** Line 15
```python
from typing import Any
```

**Occurrences:**

1. **Line 27** - Constructor parameter
```python
def __init__(self, reactor: Any) -> None:
```
**Recommended:** `reactor: 'Reactor'`

2. **Line 34** - Instance variable
```python
self.reactor: Any = reactor
```
**Recommended:** `self.reactor: 'Reactor' = reactor`

---

### src/exabgp/reactor/protocol.py

**Import:** Line 13
```python
from typing import Any, Generator, Optional, Tuple
```

**Occurrences:**

1. **Line 57** - Constructor parameter (peer)
```python
def __init__(self, peer: Any) -> None:
```
**Recommended:** `peer: 'Peer'`

2. **Line 58** - Instance variable (peer)
```python
self.peer: Any = peer
```
**Recommended:** `self.peer: 'Peer' = peer`

3. **Line 59** - Instance variable (neighbor)
```python
self.neighbor: Any = peer.neighbor
```
**Recommended:** `self.neighbor: 'Neighbor' = peer.neighbor`

4. **Line 61** - Connection object
```python
self.connection: Optional[Any] = None
```
**Recommended:** `self.connection: Optional[Union['Outgoing', 'Incoming']] = None`

5. **Line 86** - Accept method parameter
```python
def accept(self, incoming: Any) -> Protocol:
```
**Recommended:** `incoming: 'Incoming'`

---

### src/exabgp/reactor/peer.py

**Import:** Line 12
```python
from typing import Any, Dict, Generator, Iterator, Optional, Set, Tuple
```

**Occurrences:**

1. **Line 66** - Stats format dict
```python
__format: Dict[str, Any] = {
```
**Recommended:** `Dict[str, Callable[[Any], str]]` (formatting functions)

2. **Line 70** - Stats constructor
```python
def __init__(self, *args: Tuple[Any, ...]) -> None:
```
**Recommended:** Keep as `Any` (variable args, appropriate here)

3. **Line 90** - Peer constructor parameters
```python
def __init__(self, neighbor: Any, reactor: Any) -> None:
```
**Recommended:** `neighbor: 'Neighbor', reactor: 'Reactor'`

4. **Line 98** - Reactor instance variable
```python
self.reactor: Any = reactor
```
**Recommended:** `self.reactor: 'Reactor' = reactor`

5. **Line 99** - Neighbor instance variable
```python
self.neighbor: Any = neighbor
```
**Recommended:** `self.neighbor: 'Neighbor' = neighbor`

6. **Line 101** - Next restart neighbor
```python
self._neighbor: Optional[Any] = None
```
**Recommended:** `self._neighbor: Optional['Neighbor'] = None`

7. **Line 250** - Resend family parameter
```python
def resend(self, enhanced: bool, family: Optional[Tuple[Any, Any]] = None) -> None:
```
**Recommended:** `family: Optional[Tuple[AFI, SAFI]] = None`

8. **Line 254** - Reestablish parameter
```python
def reestablish(self, restart_neighbor: Optional[Any] = None) -> None:
```
**Recommended:** `restart_neighbor: Optional['Neighbor'] = None`

9. **Line 262** - Reconfigure parameter
```python
def reconfigure(self, restart_neighbor: Optional[Any] = None) -> None:
```
**Recommended:** `restart_neighbor: Optional['Neighbor'] = None`

10. **Line 276** - Handle connection
```python
def handle_connection(self, connection: Any) -> Optional[Any]:
```
**Recommended:** `connection: Union['Incoming', 'Outgoing']` → `Optional[bool]`

11. **Line 756** - CLI data return
```python
def cli_data(self) -> Dict[str, Any]:
```
**Recommended:** Keep as `Any` (mixed types: str, int, bool, FSM, etc.)

---

### src/exabgp/reactor/api/processes.py

**Import:** Line 17
```python
from typing import Any, Dict, Generator, List, Optional, Tuple, Union
```

**Occurrences:**

1. **Line 57** - Dispatch dict
```python
_dispatch: Dict[int, Any] = {}
```
**Recommended:** `Dict[int, Callable[..., None]]`

2. **Line 63** - Configuration dict
```python
self._configuration: Dict[str, Dict[str, Any]] = {}
```
**Recommended:** Keep as `Any` (mixed config values: str, bool, int, list)

3. **Line 199** - Start configuration parameter
```python
def start(self, configuration: Dict[str, Dict[str, Any]], restart: bool = False) -> None:
```
**Recommended:** Keep as `Any` (mixed config values)

4-20. **Lines 212, 307, 372, 389, 394, 399, 404, 409, 414, 420, 431, 444, 469, 474** - Neighbor parameters
```python
def broken(self, neighbor: Any) -> bool:
def write(self, process: str, string: Optional[str], neighbor: Any = None) -> bool:
# ... and 12 more methods
```
**Recommended:** All should be `neighbor: 'Neighbor'` or `Optional['Neighbor']`

21. **Line 409** - FSM parameter
```python
def fsm(self, neighbor: Any, fsm: Any) -> None:
```
**Recommended:** `neighbor: 'Neighbor', fsm: FSM`

22. **Line 444** - Message parameter
```python
def packets(self, neighbor: Any, direction: str, message: Any, ...) -> None:
```
**Recommended:** `message: Message`

23. **Line 469** - Open message
```python
def _open(self, peer: Any, direction: str, message: Any, ...) -> None:
```
**Recommended:** `peer: 'Peer', message: Open`

24. **Line 474** - Update message
```python
def _update(self, peer: Any, direction: str, update: Any, ...) -> None:
```
**Recommended:** `peer: 'Peer', update: Update`

---

### src/exabgp/reactor/loop.py

**Import:** Line 15
```python
from typing import Any, Dict, Generator, List, Optional, Set
```

**Occurrences:**

1. **Line 169** - Neighbor return type
```python
def neighbor(self, peer_name: str) -> Optional[Any]:
```
**Recommended:** `Optional['Neighbor']`

2. **Line 190** - CLI data return
```python
def neighbor_cli_data(self, peer_name: str) -> Any:
```
**Recommended:** `Union[Dict[str, Any], str]` (returns dict or empty string on error)

---

## Category 2: Generator Yield Types

### src/exabgp/reactor/protocol.py

**All generators currently:** `Generator[Any, None, None]`

1. **Line 201** - Read message
```python
def read_message(self) -> Generator[Any, None, None]:
```
**Yields:** Message objects or NOP
**Recommended:** `Generator[Union[Message, NOP], None, None]`

2. **Line 338** - Read open
```python
def read_open(self, ip: str) -> Generator[Any, None, None]:
```
**Yields:** Open messages or NOP
**Recommended:** `Generator[Union[Open, NOP], None, None]`

3. **Line 355** - Read keepalive
```python
def read_keepalive(self) -> Generator[Any, None, None]:
```
**Yields:** KeepAlive messages
**Recommended:** `Generator[KeepAlive, None, None]`

4. **Line 371** - New open
```python
def new_open(self) -> Generator[Any, None, None]:
```
**Yields:** Bytes for sending
**Recommended:** `Generator[bytes, None, None]`

5. **Line 394** - New keepalive
```python
def new_keepalive(self, comment: str = '') -> Generator[Any, None, None]:
```
**Yields:** Bytes
**Recommended:** `Generator[bytes, None, None]`

6. **Line 407** - New notification
```python
def new_notification(self, notification: Notify) -> Generator[Any, None, None]:
```
**Yields:** Bytes
**Recommended:** `Generator[bytes, None, None]`

7. **Line 416** - New update
```python
def new_update(self, include_withdraw: bool) -> Generator[Any, None, None]:
```
**Yields:** Bytes
**Recommended:** `Generator[bytes, None, None]`

8. **Line 429** - New EOR
```python
def new_eor(self, afi: AFI, safi: SAFI) -> Generator[Any, None, None]:
```
**Yields:** Bytes
**Recommended:** `Generator[bytes, None, None]`

9. **Line 436** - New EORs
```python
def new_eors(self, afi: AFI = AFI.undefined, safi: SAFI = SAFI.undefined) -> Generator[Any, None, None]:
```
**Yields:** Bytes
**Recommended:** `Generator[bytes, None, None]`

10. **Line 457** - New operational
```python
def new_operational(self, operational: Operational, negotiated: Negotiated) -> Generator[Any, None, None]:
```
**Yields:** Bytes
**Recommended:** `Generator[bytes, None, None]`

11. **Line 463** - New refresh
```python
def new_refresh(self, refresh: Any) -> Generator[Any, None, None]:
```
**Parameter & yields:** RouteRefresh
**Recommended:** `refresh: RouteRefresh` → `Generator[bytes, None, None]`

---

### src/exabgp/reactor/peer.py

1. **Line 369** - Send open
```python
def _send_open(self) -> Generator[Any, None, None]:
```
**Yields:** int or bool (state transitions)
**Recommended:** `Generator[Union[int, bool], None, None]`

2. **Line 376** - Read open
```python
def _read_open(self) -> Generator[Any, None, None]:
```
**Yields:** int or bool
**Recommended:** `Generator[Union[int, bool], None, None]`

---

### src/exabgp/reactor/keepalive.py

**Import:** Line 9
```python
from typing import Any, Generator, Optional
```

**Occurrences:**

1. **Line 28** - Generator variable
```python
generator: Optional[Generator[Any, None, None]] = None
```
**Recommended:** `Optional[Generator[bytes, None, None]]`

---

### src/exabgp/reactor/api/processes.py

1. **Line 372** - Notify generator
```python
def _notify(self, neighbor: Any, event: str) -> Generator[str, None, None]:
```
**Note:** Already properly typed as yielding str, but neighbor should be `'Neighbor'`

---

## Category 3: Configuration Dictionaries

### src/exabgp/environment/environment.py

**Import:** Line 11
```python
from typing import Any, ClassVar, Dict, Iterator, List, Optional
```

**Occurrences:**

1. **Line 34** - Definition dict
```python
definition: ClassVar[Dict[str, Dict[str, Any]]] = {}
```
**Structure:** Inner dict has keys: 'read', 'write', 'value', 'help'
**Recommended:** Create TypedDict for structure

2. **Line 45** - Values dict
```python
values: Dict[str, Any] = cls.definition[section][option]
```
**Recommended:** TypedDict or keep as Any

3. **Line 46** - Default value
```python
default: Any
```
**Recommended:** `Union[str, int, bool, List[str]]`

4-10. **Lines 61-76** - Multiple func/value variables
```python
func: Any
value: Any
```
**Recommended:** `func: Callable`, `value: Union[str, int, bool, List]`

11. **Line 86** - Setup configuration
```python
def setup(cls, configuration: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
```
**Recommended:** Same TypedDict structure

---

### src/exabgp/bgp/neighbor.py

**Import:** Line 15
```python
from typing import Any, ClassVar, Dict, List, Optional, Tuple, TYPE_CHECKING
```

**Occurrences:**

1. **Line 57** - Capability defaults
```python
defaults: ClassVar[Dict[str, Any]] = {
```
**Values:** bool, int, None, str
**Recommended:** `Dict[str, Union[bool, int, None, str]]`

2. **Line 70** - Neighbor defaults
```python
defaults: ClassVar[Dict[str, Any]] = {
```
**Values:** Mixed types (IP, HoldTime, TTL, etc.)
**Recommended:** TypedDict or keep as Any (too varied)

---

### src/exabgp/configuration/check.py

**Multiple functions:**

```python
def _negotiated(neighbor: Dict[str, Any]) -> Negotiated:
# ... and many more functions with neighbor: Dict[str, Any]
```
**Lines:** 66, 93-443
**Recommended:** Create NeighborConfigDict TypedDict

---

## Category 4: Message and Connection Types

### src/exabgp/reactor/api/__init__.py

**Occurrences:**

1-5. **Lines 64, 78, 93, 108, 122** - Route API methods
```python
def api_route(self, command: str) -> List[Any]:
def api_announce_v4(self, command: str) -> List[Any]:
def api_announce_v6(self, command: str) -> List[Any]:
def api_flow(self, command: str) -> List[Any]:
def api_vpls(self, command: str) -> List[Any]:
```
**Recommended:** All should return `List[Change]`

6. **Line 133** - Attributes method
```python
def api_attributes(self, command: str, peers: Any) -> List[Any]:
```
**Recommended:** `peers: Dict[str, Peer]` → `List[Change]`

7. **Line 177** - Operational method
```python
def api_operational(self, command: str) -> Union[bool, Any]:
```
**Recommended:** `Union[bool, Operational]`

---

### src/exabgp/bgp/message/open/capability/negotiated.py

**Occurrences:**

1. **Line 28** - Sent open
```python
self.sent_open: Optional[Any] = None
```
**Recommended:** `Optional[Open]`

2. **Line 29** - Received open
```python
self.received_open: Optional[Any] = None
```
**Recommended:** `Optional[Open]`

---

## Category 5: Registry/Factory Patterns

### src/exabgp/reactor/api/command/command.py

**Import:** Line 10
```python
from typing import Any, Callable, ClassVar, Dict, List, Optional
```

**Occurrences:**

1. **Line 14** - Callback registry
```python
callback: ClassVar[Dict[str, Dict[str, Any]]] = {'text': {}, 'json': {}, 'neighbor': {}, 'options': {}}
```
**Recommended:** `Dict[str, Dict[str, Union[Callable, bool, Dict]]]`

2. **Line 20** - Register decorator (options parameter)
```python
def register(cls, name: str, neighbor: bool = True, options: Optional[Any] = None, json_support: bool = False) -> ...:
```
**Recommended:** `options: Optional[Dict[str, Any]]`

3-4. **Lines 21, 27** - Decorator return types
```python
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
def register(function: Callable[..., Any]) -> Callable[..., Any]:
```
**Recommended:** Could use ParamSpec for more precise typing

---

### src/exabgp/bgp/message/update/attribute/sr/srv6/*.py

**Pattern in multiple files:**

```python
registered_subtlvs: ClassVar[Dict[int, Type[Any]]] = dict()

@classmethod
def register(cls) -> Callable[[Type[Any]], Type[Any]]:
```
**Recommended:** Use TypeVar bound to base TLV class

---

## Category 6: Logger and Formatter Types

### src/exabgp/logger/__init__.py

**Import:** Line 4
```python
from typing import Any, Callable, ClassVar, Union
```

**Occurrences:**

1. **Line 22** - Logger instance
```python
logger: ClassVar[Any] = None
```
**Recommended:** `ClassVar[Optional[Callable[[str], None]]]`

2. **Line 25** - Init env parameter
```python
def init(env: Any) -> None:
```
**Recommended:** `env: Env`

3-4. **Lines 30, 42** - Eat method cls parameter
```python
def eat(cls: Any, message: LogMessage, source: str = '', level: str = '') -> None:
```
**Recommended:** `cls: Type[_log]`

5. **Line 76** - Logger callable
```python
def logger(logger: Any, message: LogMessage, source: str, level: str) -> None:
```
**Recommended:** `logger: Callable[[str], None]`

---

### src/exabgp/logger/option.py

**Import:** Line 6
```python
from typing import Any, ClassVar, Dict, Optional
```

**Occurrences:**

1. **Line 19** - Formatter
```python
formater: ClassVar[Any] = echo
```
**Recommended:** `ClassVar[Callable[[str], str]]`

2-3. **Lines 63, 97** - Env parameter
```python
def load(cls, env: Any) -> None:
def setup(cls, env: Any) -> None:
```
**Recommended:** `env: Env`

---

### src/exabgp/logger/tty.py

**Import:** Line 4
```python
from typing import Any, Dict
```

**Occurrences:**

1. **Line 14** - Standard output dict
```python
_std: Dict[str, Any] = {
```
**Recommended:** `Dict[str, TextIO]`

---

### src/exabgp/logger/format.py

**Import:** Line 5
```python
from typing import Callable, Optional, Tuple, Dict, Any
```

**Occurrences:**

1. **Line 12** - FormatterFunc type alias
```python
FormatterFunc = Callable[[str, str, str, Any], str]
```
**Recommended:** Last parameter should be `time.struct_time`

---

## Category 7: Flow Parser and Operations

### src/exabgp/bgp/message/update/nlri/flow.py

**Occurrences:**

1-2. **Lines 201-202** - IOperation value field
```python
value: Any
first: Optional[Any]
```
**Recommended:** `value` depends on subclass, `first: Optional[bool]`

3. **Line 204** - Constructor
```python
def __init__(self, operations: int, value: Any) -> None:
```
**Recommended:** Use TypeVar for value type

4. **Line 214** - Encode method
```python
def encode(self, value: Any) -> Tuple[int, bytes]:
```
**Recommended:** Use TypeVar matching value type

5-6. **Lines 256, 292** - NumericString and BinaryString
```python
value: Optional[Any] = None
```
**Recommended:** `Union[int, Protocol, Port, ICMPType, ICMPCode]`

7-10. **Lines 316-329** - Converter/decoder factories
```python
def converter(function: Callable[[str], Any], klass: Optional[Type] = None) -> Callable[[str], Any]:
def decoder(function: Callable[[bytes], Any], klass: Type = int) -> Callable[[bytes], Any]:
```
**Recommended:** Use TypeVar for return types

11-20. **Lines 412-455** - Class-level converters/decoders
```python
ClassVar[Callable[[str/bytes], Any]]
```
**Recommended:** Specific types (Protocol, Port, ICMPType, etc.)

---

### src/exabgp/configuration/flow/*.py

**Pattern in multiple files:**

```python
known: Dict[str, Callable[[Any], Any]]

def _generic_condition(tokeniser: Any, klass: Any) -> Generator[Any, None, None]:
```
**Recommended:**
- `known: Dict[str, Callable[[Tokeniser], IOperation]]`
- `tokeniser: Tokeniser, klass: Type[IOperation]` → `Generator[IOperation, None, None]`

---

## Category 8: Miscellaneous

### src/exabgp/bgp/message/update/nlri/mup/*.py

**Pattern in multiple MUP NLRI files:**

```python
def json(self, compact: Optional[Any] = None) -> str:
```
**Recommended:** `compact: Optional[bool] = None`

---

### src/exabgp/configuration/static/parser.py

**Occurrences:**

1. **Line 604** - Withdraw function
```python
def withdraw(tokeniser: Optional[Any] = None) -> Any:
```
**Recommended:** `tokeniser: Optional[Tokeniser] = None` → `Withdrawn`

---

### src/exabgp/protocol/iso/__init__.py

**Occurrences:**

1. **Line 34** - JSON method
```python
def json(self, compact: Optional[Any] = None) -> str:
```
**Recommended:** `compact: Optional[bool] = None`

---

### src/exabgp/reactor/asynchronous.py

**Import:** Line 13
```python
from typing import Any, Deque, Optional, Tuple
```

**Occurrences:**

1. **Line 22** - Async queue
```python
self._async: Deque[Tuple[str, Any]] = deque()
```
**Recommended:** `Deque[Tuple[str, Union[Generator, Coroutine]]]`

---

### src/exabgp/data/check.py

**Occurrences:**

1. **Line 84** - Check type dict
```python
CHECK_TYPE: Dict[int, Callable[[Any], bool]] = {
```
**Recommended:** Keep as `Any` (generic type checking)

2. **Line 318** - Flow numeric check
```python
def _flow_numeric(data: Any, check: Callable[[Any], bool]) -> bool:
```
**Recommended:** Keep as `Any` (generic validation)

---

### src/exabgp/util/dictionary.py

**Occurrences:**

1. **Line 19** - Default factory override
```python
default_factory: Optional[Callable[[], Dict[Any, Any]]]
```
**Recommended:** Keep as `Any` (from defaultdict, generic)

---

## Summary by Priority

### High Priority (Core Architecture - 40 instances)
- Reactor/Peer/Neighbor circular dependencies
- Fix using TYPE_CHECKING imports
- Files: reactor/*.py

### Medium Priority (Type Safety - 50 instances)
- Generator yield types
- Message type parameters
- Connection types
- Files: reactor/protocol.py, reactor/api/*.py

### Lower Priority (Documentation - 60 instances)
- Configuration dictionaries (mixed types, may keep as Any)
- Registry patterns (use generics)
- Logger types
- Flow parsers
- Miscellaneous JSON methods

## Files to Keep As `Any`

Some uses of `Any` are appropriate and should be kept:
1. **data/check.py**: Generic type validation functions
2. **util/dictionary.py**: defaultdict generic types
3. **Peer.cli_data()**: Returns mixed runtime data types
4. **Configuration dicts**: Truly heterogeneous runtime config
5. **Stats.__init__(*args)**: Variable positional arguments
