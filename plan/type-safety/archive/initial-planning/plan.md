# Type Annotation Implementation Plan for ExaBGP

**Created**: 2025-11-12
**Status**: In Progress - Sprint 1
**Estimated Duration**: 14 weeks (6 sprints)
**Total Files**: ~341 Python files in `src/exabgp/`

## Overview

### Goals
- Add comprehensive type annotations to entire ExaBGP codebase
- Enable mypy strict type checking
- Maintain Python 3.8+ compatibility
- Use stdlib `typing` module only (no external dependencies)
- Ensure all CI/CD tests pass throughout

### Strategy
- **Bottom-up approach**: Annotate leaf classes → base classes → integration systems
- **One commit per file**: Easy rollback if issues arise
- **Single PR with multiple commits**: Organized by sprint/phase
- **mypy from start**: Incremental type checking added to CI/CD immediately
- **Full testing**: CI/CD must pass after each phase

---

## Codebase Analysis Summary

**Total Files**: 341 Python files in `src/exabgp/`

**Module Distribution**:
- `bgp/`: 176 files (52%) - Core BGP protocol
- `configuration/`: 45 files (13%) - Config parsing
- `reactor/`: 31 files (9%) - Event loop and networking
- Other modules: 89 files (26%)

**File Size Distribution**:
- Small (<100 lines): 204 files (60%)
- Medium (100-300 lines): 107 files (31%)
- Large (300+ lines): 31 files (9%)

**Current Type Annotation Status**:
- Only 2 files currently use `from typing import`
- ~21 files have basic inline type hints
- Most files already use `from __future__ import annotations`

**Key Architecture Patterns**:
1. **Registry/Factory Pattern**: `@Message.register`, `@NLRI.register`, etc.
2. **Resource Pattern**: Int-like enums with caching (AFI, SAFI, Family)
3. **Template Method**: Base classes with specialized implementations
4. **State Machine**: BGP FSM (IDLE → ESTABLISHED)
5. **LRU Caching**: Attribute caching for performance

**Major Class Hierarchies**:
- **Message**: Base → Open, Update, Notification, KeepAlive, etc. (8 implementations)
- **NLRI**: Base → INET, Flow, EVPN, BGPLS, VPN, etc. (51 implementations)
- **Attribute**: Base → Origin, ASPath, Communities, etc. (87 implementations)
- **Capability**: Base → MultiProtocol, ASN4, AddPath, etc. (16 implementations)

---

## Sprint Breakdown

### Sprint 1: Foundation (Weeks 1-2, ~40 files)
**Goal**: Annotate utilities and core base classes

**Setup Tasks**:
- Add mypy configuration to `pyproject.toml`
- Update CI/CD with mypy checking
- Create typing guidelines document

**Phase 1A - Pure Utilities** (10 files):
```
util/cache.py          - LRU cache (START HERE - simplest)
util/od.py             - Hex dump utilities
util/errstr.py         - Error formatting
util/dictionary.py     - Dict utilities
util/dns.py            - DNS resolution
util/enumeration.py    - Enum utilities
util/ip.py             - IP utilities
util/usage.py          - Resource usage
util/coroutine.py      - Coroutine helpers
util/__init__.py       - Module init
```

**Phase 1B - Protocol Primitives** (11 files):
```
protocol/resource.py             - Base Resource class (CRITICAL)
protocol/family.py               - AFI/SAFI definitions (used everywhere)
protocol/ip/__init__.py          - IP class (356 lines)
protocol/ip/netmask.py           - Netmask handling
protocol/ip/fragment.py          - IP fragmentation
protocol/ip/icmp.py              - ICMP types
protocol/ip/port.py              - Port definitions (4981 lines - LARGE!)
protocol/ip/tcp/flag.py          - TCP flags
protocol/iso/__init__.py         - ISO addresses
+ 2 more protocol files
```

**Phase 1C - Support Infrastructure** (7 files):
```
logger/color.py            - ANSI color codes
logger/history.py          - Log history
logger/tty.py              - TTY detection
+ 4 more logger files
environment/__init__.py    - Environment config (357 lines)
data/__init__.py           - Data structures
data/check.py              - Validation utilities (339 lines)
```

**Phase 1D - Core Base Classes** (8 files):
```
bgp/message/message.py                            - Message base (CRITICAL)
bgp/message/notification.py                       - Notify exception
bgp/message/action.py, direction.py               - Enums
bgp/message/update/nlri/nlri.py                   - NLRI base (CRITICAL)
bgp/message/update/nlri/cidr.py                   - CIDR handling
bgp/message/update/attribute/attribute.py         - Attribute base (CRITICAL)
bgp/message/open/capability/capability.py         - Capability base (CRITICAL)
```

**Deliverables**:
- ✅ 40 commits (one per file)
- ✅ mypy configured and running in CI/CD
- ✅ All existing tests pass
- ✅ Type checking baseline established

---

### Sprint 2: Simple Implementations (Weeks 3-4, ~60 files)
**Goal**: Annotate leaf classes with straightforward logic

**Phase 2A - Simple Messages** (5 files):
```
bgp/message/keepalive.py
bgp/message/nop.py
bgp/message/refresh.py
bgp/message/unknown.py
bgp/message/source.py
```

**Phase 2B - Simple Attributes** (~30 files):
```
Well-known mandatory:
  - origin.py, med.py, localpref.py, nexthop.py

Simple optional:
  - atomicaggregate.py, originatorid.py, clusterlist.py

BGP-LS attributes:
  - bgpls/link/* (20+ small files)
  - bgpls/node/*
  - bgpls/prefix/*
```

**Phase 2C - Simple Capabilities** (~10 files):
```
asn4.py, refresh.py, extended.py
hostname.py, software.py
open/asn.py, holdtime.py, routerid.py, version.py
+ supporting classes
```

**Phase 2D - NLRI Qualifiers** (~10 files):
```
qualifier/esi.py       - Ethernet Segment Identifier
qualifier/etag.py      - Ethernet Tag
qualifier/labels.py    - MPLS labels
qualifier/mac.py       - MAC address
qualifier/path.py      - Path identifier
qualifier/rd.py        - Route Distinguisher
+ 4 more qualifiers
```

**Deliverables**:
- ✅ 60 commits
- ✅ All CI/CD tests pass
- ✅ mypy passes for all annotated modules
- ✅ Registry pattern types working correctly

---

### Sprint 3: Complex Implementations (Weeks 5-7, ~50 files)
**Goal**: Annotate complex leaf classes

**Phase 3A - Complex Messages** (3 files):
```
bgp/message/open/__init__.py        - Open message
bgp/message/operational.py          - ExaBGP extensions (336 lines)
bgp/message/update/__init__.py      - Update message (337 lines)
```

**Phase 3B - Complex Attributes** (~20 files):
```
aspath.py (245 lines)
aigp.py, aggregator.py, pmsi.py
mprnlri.py (205 lines), mpurnlri.py

Community types:
  - community/ subdirectory
  - extended/ subdirectory
  - large/ subdirectory

Segment Routing:
  - sr/ subdirectory
```

**Phase 3C - Complex NLRIs** (~15 files):
```
inet.py (200+ lines), label.py
ipvpn.py, vpls.py, rtc.py

EVPN types:
  - evpn/ subdirectory (6 files)

BGP-LS types:
  - bgpls/ subdirectory (9 files)

MUP types:
  - mup/ subdirectory (5 files)

MVPN types:
  - mvpn/ subdirectory (4 files)
```

**Phase 3D - Very Complex** (3 files):
```
bgp/message/update/nlri/flow.py                    - FlowSpec (714 lines!)
bgp/message/update/attribute/attributes.py         - Collection (507 lines)
bgp/message/open/capability/capabilities.py        - Collection (272 lines)
```

**Deliverables**:
- ✅ 50 commits
- ✅ All CI/CD tests pass
- ✅ Functional encoding tests pass
- ✅ Complex patterns fully typed

---

### Sprint 4: Integration Systems (Weeks 8-11, ~80 files)
**Goal**: Annotate high-level systems (HIGHEST RISK)

**Phase 4A - RIB Management** (5 files):
```
rib/outgoing.py (251 lines)
rib/incoming.py
rib/change.py
rib/cache.py
+ 1 more
```

**Phase 4B - Reactor Networking** (8 files):
```
reactor/network/ subdirectory
  - TCP connection handling
  - Socket management
  - Error handling
```

**Phase 4C - Reactor API** (14 files):
```
reactor/api/ subdirectory
  - External process communication
  - JSON API
  - Command dispatching
```

**Phase 4D - Core Reactor** (4 files):
```
reactor/loop.py          - Main event loop (548 lines)
reactor/listener.py      - Connection listener (250 lines)
reactor/daemon.py        - Daemonization (222 lines)
+ support files
```

**Phase 4E - BGP State Machine** (2 files):
```
bgp/neighbor.py          - Neighbor config (629 lines)
bgp/fsm.py               - Finite state machine (845 lines - VERY COMPLEX!)
```

**Phase 4F - Protocol Handler** (2 files):
```
reactor/protocol.py      - Protocol handler (467 lines)
reactor/peer.py          - Peer management (845 lines)
```

**Phase 4G - Configuration System** (45 files):
```
configuration/configuration.py          - Main parser (605 lines)
configuration/check.py                  - Validation (461 lines)
configuration/static/parser.py          - Static routes (607 lines)
configuration/flow/parser.py            - FlowSpec config (447 lines)
configuration/neighbor/ subdirectory    - Neighbor config
configuration/announce/ subdirectory    - Route announcements
configuration/core/ subdirectory        - Parser infrastructure
```

**Deliverables**:
- ✅ 80 commits
- ✅ All CI/CD tests pass
- ✅ FSM and reactor fully typed
- ✅ Configuration parsing typed

---

### Sprint 5: Applications & Specialized (Weeks 12-13, ~35 files)
**Goal**: Annotate CLI applications and specialized modules

**Phase 5A - Applications** (20 files):
```
application/cli.py            - CLI interface (344 lines)
application/healthcheck.py    - Health check (620 lines)
application/server.py         - BGP server (265 lines)
application/pipe.py           - Pipe mode (323 lines)
application/decode.py         - Message decoder
application/tojson.py         - JSON converter
application/validate.py       - Config validator
cli/ subdirectory             - CLI interface (6 files)
__main__.py                   - Entry point
```

**Phase 5B - Specialized Modules** (15 files):
```
netlink/ subdirectory         - Linux netlink (13 files)
conf/yang/ subdirectory       - YANG model support (7 files, optional)
debug/ subdirectory           - Debug utilities (2 files)
```

**Skipped**:
```
vendoring/ - Third-party code (no modifications)
```

**Deliverables**:
- ✅ 35 commits
- ✅ All applications typed
- ✅ All CI/CD tests pass

---

### Sprint 6: Polish & Validation (Week 14)
**Goal**: Comprehensive validation and documentation

**Tasks**:
1. Run `mypy --strict` across entire codebase
2. Fix remaining type errors or add justified `type: ignore` comments
3. Add `py.typed` marker file (PEP 561 compliance)
4. Create typing guidelines document for contributors
5. Update main documentation
6. Final CI/CD validation (Python 3.8-3.13)
7. Performance regression testing
8. Code review preparation

**Deliverables**:
- ✅ Zero mypy errors with strict checking
- ✅ Documentation updated
- ✅ All CI/CD passes on all Python versions
- ✅ PR ready for merge
- ✅ ~341 total commits in one PR

---

## mypy Configuration

### Initial Configuration (Sprint 1)

Add to `pyproject.toml`:

```toml
[tool.mypy]
python_version = "3.8"
warn_unused_configs = true
warn_return_any = true
warn_redundant_casts = true
warn_unused_ignores = true

# Start permissive, tighten gradually
disallow_untyped_defs = false
disallow_untyped_calls = false
disallow_incomplete_defs = false

# Incremental checking
follow_imports = "normal"
ignore_missing_imports = true

# Exclude vendored code
exclude = [
    "src/exabgp/vendoring/",
]
```

### Progressive Strictness

Add per-module overrides as sprints complete:

```toml
# After Sprint 1
[[tool.mypy.overrides]]
module = "exabgp.util.*"
disallow_untyped_defs = true

[[tool.mypy.overrides]]
module = "exabgp.protocol.*"
disallow_untyped_defs = true

# After Sprint 2
[[tool.mypy.overrides]]
module = "exabgp.bgp.message.keepalive"
disallow_untyped_defs = true
# ... add more as completed

# Final state (Sprint 6)
[tool.mypy]
disallow_untyped_defs = true  # Enable globally
disallow_untyped_calls = true
disallow_incomplete_defs = true
check_untyped_defs = true
```

---

## Special Typing Patterns

### 1. Registry/Factory Pattern

Used by: Message, NLRI, Attribute, Capability

```python
from typing import Type, TypeVar, Dict, ClassVar

T = TypeVar('T', bound='Message')

class Message:
    registered_message: ClassVar[Dict[int, Type['Message']]] = {}
    TYPE: ClassVar[int]

    @classmethod
    def register(cls, klass: Type[T]) -> Type[T]:
        cls.registered_message[klass.TYPE] = klass
        return klass

    def message(self) -> bytes:
        """Serialize to wire format"""
        raise NotImplementedError()

@Message.register
class KeepAlive(Message):
    TYPE = 4

    def message(self) -> bytes:
        return b'\xff' * 16 + b'\x00\x13\x04'
```

### 2. Resource Pattern (Int-like Enums with Caching)

Used by: AFI, SAFI, Family

```python
from typing import ClassVar, Dict, Optional

class Resource(int):
    _instances: ClassVar[Dict[int, 'Resource']] = {}

    def __new__(cls, value: int) -> 'Resource':
        if value in cls._instances:
            return cls._instances[value]
        instance = super().__new__(cls, value)
        cls._instances[value] = instance
        return instance

    def __str__(self) -> str:
        return str(int(self))

class AFI(Resource):
    ipv4 = 1
    ipv6 = 2
```

### 3. LRU Cache Generic

Used by: `util/cache.py`, Attribute caching

```python
from typing import TypeVar, Generic, Optional, Dict, Tuple

KT = TypeVar('KT')
VT = TypeVar('VT')

class Cache(dict, Generic[KT, VT]):
    def __init__(self, maxsize: int = 1000) -> None:
        dict.__init__(self)
        self.maxsize = maxsize
        self._order: list[KT] = []

    def cache(self, key: KT, value: VT) -> VT:
        if key in self:
            self._order.remove(key)
        self[key] = value
        self._order.append(key)
        if len(self) > self.maxsize:
            oldest = self._order.pop(0)
            del self[oldest]
        return value
```

### 4. Binary Protocol Unpacking

Used by: NLRI, Attribute parsing

```python
from typing import Tuple, Optional, Type, TypeVar

T = TypeVar('T', bound='NLRI')

class NLRI:
    @classmethod
    def unpack_nlri(
        cls: Type[T],
        afi: int,
        safi: int,
        data: bytes,
        offset: int,
        action: int,
        addpath: Optional[int] = None
    ) -> Tuple[Optional[T], int]:
        """
        Unpack NLRI from wire format.

        Returns:
            (nlri_instance, bytes_consumed) or (None, 0) on error
        """
        ...
```

### 5. Message as Exception

Used by: Message hierarchy

```python
from typing import ClassVar

class Message(Exception):
    """
    BGP Message base class.

    Inherits from Exception to enable use as error/signal.
    """
    TYPE: ClassVar[int]
    ID: ClassVar[int]

    def message(self) -> bytes:
        """Serialize message to BGP wire format"""
        raise NotImplementedError()

    def __str__(self) -> str:
        return self.__class__.__name__
```

### 6. State Machine Typing

Used by: BGP FSM

```python
from typing import Optional, Callable, Dict
from enum import IntEnum

class FSM_STATE(IntEnum):
    IDLE = 1
    ACTIVE = 2
    CONNECT = 3
    OPENSENT = 4
    OPENCONFIRM = 5
    ESTABLISHED = 6

class FSM:
    state: FSM_STATE

    def __init__(self, neighbor: 'Neighbor') -> None:
        self.state = FSM_STATE.IDLE
        self.neighbor = neighbor

    def run(self, message: Optional[Message]) -> Optional[FSM_STATE]:
        """Process message and return new state if changed"""
        ...
```

---

## Testing Strategy

### After Each Commit
```bash
# Linting
uv run ruff format && uv run ruff check

# Unit tests
env exabgp_log_enable=false uv run pytest --cov --cov-reset ./tests/*_test.py

# Type checking (incremental)
uv run mypy src/exabgp/
```

### After Each Phase
```bash
# Parsing tests
./qa/bin/parsing

# Encoding tests (IMPORTANT: ensure ulimit -n 64000)
ulimit -n 64000
killall -9 Python  # macOS uses capital P
./qa/bin/functional encoding
```

### Before Sprint Complete
```bash
# Full CI/CD validation
uv run ruff format && uv run ruff check
env exabgp_log_enable=false uv run pytest --cov --cov-reset ./tests/*_test.py
./qa/bin/parsing
./qa/bin/functional encoding
uv run mypy src/exabgp/
```

---

## Risk Management

### High-Risk Files
1. **`bgp/fsm.py`** (845 lines) - Complex state machine
2. **`bgp/message/update/nlri/flow.py`** (714 lines) - FlowSpec complexity
3. **`configuration/configuration.py`** (605 lines) - String parsing
4. **`reactor/peer.py`** (845 lines) - Peer state management
5. **`reactor/loop.py`** (548 lines) - Custom event loop
6. **`protocol/ip/port.py`** (4981 lines!) - Huge definition file

### Mitigation Strategy
1. **One commit per file** - Easy rollback
2. **Run full CI/CD after high-risk files** - Catch issues immediately
3. **Review complex files with maintainer** - Before committing
4. **Keep encoding tests passing** - Critical validation
5. **Document type: ignore with explanation** - Where unavoidable

### If Tests Fail
1. **Immediately revert the commit**: `git revert HEAD`
2. **Analyze the failure**: Check test output, mypy errors
3. **Fix locally**: Correct the type annotations
4. **Re-test before recommit**: Ensure all tests pass
5. **Document the issue**: Add to lessons learned

---

## Commit Message Format

```
Add type annotations to <module_path>

- Add function parameter and return type hints
- Add class attribute type annotations
- Add method return type annotations
- Use stdlib typing module (List, Dict, Optional, Union, Tuple)
- Maintain Python 3.8+ compatibility with future annotations

Module: <module_name>
Lines: <line_count>
Complexity: <Low|Medium|High>
Sprint: <sprint_number>, Phase: <phase_letter>

Part of comprehensive type annotation rollout
```

Example:
```
Add type annotations to util/cache.py

- Add function parameter and return type hints
- Add class attribute type annotations
- Add method return type annotations
- Use stdlib typing module (Dict, Generic, TypeVar)
- Maintain Python 3.8+ compatibility with future annotations

Module: util.cache
Lines: 59
Complexity: Low
Sprint: 1, Phase: 1A

Part of comprehensive type annotation rollout
```

---

## Success Criteria

### Per Sprint
- ✅ All files in sprint have type annotations
- ✅ One commit per file
- ✅ All CI/CD tests pass
- ✅ mypy passes for annotated modules
- ✅ No performance regression

### Final (Sprint 6)
- ✅ All ~341 files in `src/exabgp/` annotated (excluding vendoring/)
- ✅ `mypy --strict` passes with zero errors
- ✅ All CI/CD tests pass on Python 3.8-3.13
- ✅ `py.typed` marker present
- ✅ Documentation updated
- ✅ ~341 commits in single PR
- ✅ PR approved and ready for merge

---

## Timeline

| Sprint | Dates | Files | Commits | Focus | Risk |
|--------|-------|-------|---------|-------|------|
| 1 | Weeks 1-2 | 40 | 40 | Foundation | Low |
| 2 | Weeks 3-4 | 60 | 60 | Simple implementations | Low |
| 3 | Weeks 5-7 | 50 | 50 | Complex implementations | Medium |
| 4 | Weeks 8-11 | 80 | 80 | Integration systems | **High** |
| 5 | Weeks 12-13 | 35 | 35 | Applications | Low |
| 6 | Week 14 | - | - | Polish & validation | Low |
| **Total** | **14 weeks** | **~265** | **~265** | **Full codebase** | **Managed** |

---

## Resources

### Documentation
- [PEP 484 - Type Hints](https://www.python.org/dev/peps/pep-0484/)
- [PEP 526 - Variable Annotations](https://www.python.org/dev/peps/pep-0526/)
- [PEP 563 - Postponed Annotation Evaluation](https://www.python.org/dev/peps/pep-0563/)
- [mypy Documentation](https://mypy.readthedocs.io/)
- [Python typing Module](https://docs.python.org/3/library/typing.html)

### Tools
- **mypy**: Type checker
- **ruff**: Linter/formatter (already in use)
- **pytest**: Testing framework (already in use)

### ExaBGP Specific
- `.claude/docs/CI_TESTING_GUIDE.md`: CI/CD requirements
- `CLAUDE.md`: Development workflow and architecture

---

## Progress Tracking

See `.claude/TYPE_ANNOTATION_PROGRESS.md` for detailed progress tracking.

---

**Last Updated**: 2025-11-12
**Current Status**: Sprint 1 In Progress
**Next Milestone**: Complete Sprint 1 (40 files, 2 weeks)
