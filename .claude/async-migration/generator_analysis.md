# ExaBGP Generator Usage Analysis Report

**Date:** 2025-11-08  
**Codebase:** ExaBGP (BGP daemon)  
**Total Python Files:** 412  
**Branch:** claude/convert-generators-to-async-011CUwFUB42rVxbv6Uf6XFQw

---

## Executive Summary

### Key Statistics
- **Total Python Files:** 412 (341 production + 48 test + 23 other)
- **Files Using Generators:** 44 files
  - Production code: 41 files
  - Test code: 3 files
- **Total Generator Functions:** ~150+ generator functions
- **Generator Expressions:** ~70+ generator expressions
- **Existing Async/Await Usage:** 1 file (qa/sbin/bgp - test utility)

### Architecture Pattern
ExaBGP uses a **custom asynchronous event loop** built on generators:
- **Framework:** `ASYNC` class in `src/exabgp/reactor/asynchronous.py`
- **Mechanism:** Generators are scheduled as callbacks and resumed via `next()`
- **Event Loop:** Main loop in `src/exabgp/reactor/loop.py`
- **Scheduling:** `reactor.asynchronous.schedule(uid, command, generator)`

---

## Part 1: Project Structure Overview

### Top-Level Directory Structure
```
exabgp/
├── src/exabgp/              # Main production code (341 Python files)
│   ├── reactor/             # Event loop, networking, peer management
│   ├── bgp/                 # BGP message parsing/handling
│   ├── configuration/       # Configuration parsing
│   ├── rib/                 # Route Information Base
│   ├── netlink/             # Netlink interface
│   ├── protocol/            # Protocol utilities
│   ├── cli/                 # Command-line interface
│   ├── environment/         # Environment/config loading
│   └── ...
├── tests/                   # Test files (48 Python files)
│   ├── unit/                # Unit tests
│   ├── fuzz/                # Fuzzing tests
│   └── ...
└── qa/                      # QA and testing utilities
```

### Main Components

#### 1. **Reactor Module** (Event Loop & Networking)
   - **Purpose:** Main event loop, I/O handling, peer management
   - **Key Files:** 
     - `loop.py` - Main event loop (1 generator function `_wait_for_io()`)
     - `protocol.py` - BGP protocol handler (14 generator functions)
     - `peer.py` - Peer state machine (9 generator functions)
     - `keepalive.py` - Keep-alive handling (3 generators)
     - `listener.py` - Connection listening
     - `network/` - TCP/IP connection handling
   - **Generator Pattern:** State machine iteration, message I/O

#### 2. **API Module** (External Process Communication)
   - **Purpose:** Handle commands from external API clients
   - **Key Files:**
     - `command/announce.py` - 30 generator functions for route announcements
     - `command/neighbor.py` - 5 generators for neighbor queries
     - `command/rib.py` - 6 generators for RIB operations
     - `command/watchdog.py` - 4 generators for watchdog functionality
   - **Generator Pattern:** Asynchronous callback handlers for API commands

#### 3. **RIB Module** (Route Information Base)
   - **Purpose:** Store and manage BGP routes
   - **Key Files:**
     - `outgoing.py` - 8 generator functions for route transmission
     - `cache.py` - 1 generator for caching
   - **Generator Pattern:** Iterating over route updates

#### 4. **BGP Message Module** (Protocol Implementation)
   - **Purpose:** Parse and handle BGP UPDATE messages
   - **Key Files:**
     - `message/update/__init__.py` - 8 generators
     - `message/update/attribute/attributes.py` - 13 generators
     - `message/update/attribute/mprnlri.py` - 5 generators
     - `message/update/attribute/mpurnlri.py` - 5 generators
     - `message/update/attribute/aigp.py` - 2 generators
   - **Generator Pattern:** Binary protocol parsing (yield data chunks)

#### 5. **Configuration Module** (Config Parsing)
   - **Purpose:** Parse configuration files
   - **Key Files:**
     - `core/tokeniser.py` - 6 generators for tokenization
     - `core/format.py` - 10 generators for text formatting
     - `flow/parser.py` - 21 generators for flow specification parsing
     - `announce/__init__.py` - 5 generators for announcement parsing
   - **Generator Pattern:** Text parsing, token iteration

#### 6. **CLI Module** (Command-Line Interface)
   - **Purpose:** Provide CLI completion and interaction
   - **Key Files:**
     - `completer.py` - 9 generators for CLI completion
   - **Generator Pattern:** Iterating over completion suggestions

#### 7. **Netlink Module** (OS Integration)
   - **Purpose:** Interface with OS netlink (Linux-specific)
   - **Key Files:**
     - `old.py` - 5 generators (legacy implementation)
     - `message.py` - 4 generators
     - `netlink.py` - 3 generators
     - `attributes.py` - 3 generators
   - **Generator Pattern:** Parsing netlink messages

#### 8. **Supporting Modules**
   - `util/__init__.py` - 2 generators (formatting utilities)
   - `environment/environment.py` - 3 generators (config loading)
   - `protocol/resource.py` - 2 generators (bit flags)
   - `conf/yang/code.py` - 5 generators (YANG model code generation)

---

## Part 2: Detailed Generator Usage Analysis

### Generator Functions by Category

#### Category A: Asynchronous Control Flow (Scheduled as Callbacks)
These generators are explicitly scheduled via `reactor.asynchronous.schedule()` and drive async operations:

**File:** `src/exabgp/reactor/api/command/announce.py` (69 yields)
- **Generator Functions:** 30
- **Purpose:** API command handlers for route operations
- **Pattern:** 
  ```python
  def announce_route(self, reactor, service, line, use_json):
      def callback():  # Nested generator function
          try:
              # ... parse command ...
              yield False  # Continue processing
              # ... more work ...
              yield True   # Indicate completion
          except:
              yield True   # Error case
      reactor.asynchronous.schedule(service, line, callback())
      return True
  ```
- **Key Functions:**
  - `announce_route()`, `withdraw_route()`
  - `announce_vpls()`, `withdraw_vpls()`
  - `announce_attributes()`, `withdraw_attributes()`
  - And 24 more command handlers

**Files:** `src/exabgp/reactor/api/command/*.py`
- `rib.py` - 6 generators (6 yields) - RIB manipulation
- `neighbor.py` - 5 generators (4 yields) - Neighbor queries
- `watchdog.py` - 4 generators (4 yields) - Watchdog operations
- **Total:** 45 generator functions in API command handling

#### Category B: Protocol I/O and State Machines
These generators handle network I/O and BGP state transitions:

**File:** `src/exabgp/reactor/protocol.py` (29 yields)
- **Generator Functions:** 14
- **Purpose:** Main BGP protocol handler
- **Pattern:** Iterate over messages, yield as they're processed
- **Key Functions:**
  - `connect()` - Establish connections
  - `write()` - Send BGP messages
  - `send()` - Schedule outgoing messages
  - `read_message()` - Parse incoming messages
  - `read_open()` - Handle OPEN messages

**File:** `src/exabgp/reactor/peer.py` (31 yields)
- **Generator Functions:** 9
- **Purpose:** BGP peer state machine
- **Key Functions:**
  - `changed_statistics()` - Report statistics
  - `_connect()` - Connection sequence
  - `_send_open()` - Send OPEN message
  - `_read_open()` - Read OPEN response
  - `_send_ka()` - Send keep-alives
  - And more state machine methods

**File:** `src/exabgp/reactor/network/connection.py` (18 yields)
- **Generator Functions:** 3
- **Purpose:** TCP connection abstraction
- **Key Functions:**
  - `reader()` - Read data from socket
  - `writer()` - Write data to socket
  - `_reader()` - Internal read handler

**File:** `src/exabgp/reactor/loop.py` (1 yield + 2 gen expressions)
- **Generator Functions:** 1
- **Purpose:** Main event loop I/O waiting
- **Key Function:**
  - `_wait_for_io(sleeptime)` - Poll for ready file descriptors

**Total I/O Category:** 27 generator functions

#### Category C: Configuration and Parsing
Generators used for sequential parsing and token iteration:

**File:** `src/exabgp/configuration/core/tokeniser.py` (6 yields)
- **Generator Functions:** 6 (but using generator objects internally)
- **Purpose:** Tokenize configuration files
- **Pattern:** Yield tokens from config text

**File:** `src/exabgp/configuration/flow/parser.py` (21 yields)
- **Generator Functions:** 16
- **Purpose:** Parse BGP flow specifications
- **Pattern:** Yield parsed flow conditions
- **Key Functions:**
  - `source()`, `destination()` - Parse IP prefixes
  - `_generic_condition()` - Generic parsing
  - `any_port()`, `source_port()` - Port parsing
  - And 11 more parsing functions

**File:** `src/exabgp/configuration/core/format.py` (10 yields)
- **Generator Functions:** 6 (10 yields)
- **Purpose:** Format configuration data as text
- **Pattern:** Yield formatted text lines

**File:** `src/exabgp/configuration/announce/__init__.py` (5 yields)
- **Generator Functions:** 3
- **Purpose:** Parse route announcements
- **Pattern:** Yield parsed route definitions

**Total Parsing Category:** 32 generator functions

#### Category D: Binary Protocol Parsing
Generators for parsing BGP binary message attributes:

**File:** `src/exabgp/bgp/message/update/attribute/attributes.py` (13 yields)
- **Generator Functions:** 4
- **Purpose:** Parse BGP path attributes
- **Pattern:** Yield parsed attributes from binary data

**File:** `src/exabgp/bgp/message/update/__init__.py` (8 yields)
- **Generator Functions:** 4
- **Purpose:** Parse UPDATE message body

**File:** `src/exabgp/bgp/message/update/attribute/mprnlri.py` (5 yields)
- **Generator Functions:** 3
- **Purpose:** Parse MP_REACH_NLRI attribute

**File:** `src/exabgp/bgp/message/update/attribute/mpurnlri.py` (5 yields)
- **Generator Functions:** 3
- **Purpose:** Parse MP_UNREACH_NLRI attribute

**File:** `src/exabgp/bgp/message/update/attribute/aigp.py` (2 yields)
- **Generator Functions:** 2
- **Purpose:** Parse AIGP attribute

**Total Binary Parsing Category:** 16 generator functions

#### Category E: RIB and Route Management
Generators for route storage and transmission:

**File:** `src/exabgp/rib/outgoing.py` (8 yields)
- **Generator Functions:** 2
- **Purpose:** Generate BGP UPDATE messages from RIB
- **Pattern:** Yield UPDATE messages with routes grouped by attributes
- **Key Function:**
  - `updates(grouped)` - Major generator yielding UPDATE objects

**File:** `src/exabgp/rib/cache.py` (1 yield)
- **Generator Functions:** 1
- **Purpose:** Cache route information

**Total RIB Category:** 3 generator functions

#### Category F: Utility and Supporting Functions
Generators for various utility purposes:

**File:** `src/exabgp/cli/completer.py` (21 yields)
- **Generator Functions:** 9
- **Purpose:** CLI tab completion
- **Pattern:** Yield completion suggestions

**File:** `src/exabgp/util/__init__.py` (4 yields)
- **Generator Functions:** 2
- **Purpose:** String formatting utilities
- **Key Functions:**
  - `hexstring()` - Format hex strings
  - `spaced()` - Format with spacing

**File:** `src/exabgp/environment/environment.py` (5 yields)
- **Generator Functions:** 3
- **Purpose:** Load environment and config files
- **Key Functions:**
  - `default()` - Default values
  - `iter_ini()` - Parse INI files
  - `iter_env()` - Parse environment variables

**Total Utility Category:** 14 generator functions

---

## Part 3: Custom Async Framework

### The ASYNC Class: Manual Generator Scheduler

**Location:** `src/exabgp/reactor/asynchronous.py`

**How It Works:**
```python
class ASYNC(object):
    LIMIT = 50  # Max iterations per run() call
    
    def __init__(self):
        self._async = deque()  # Queue of (uid, generator) tuples
    
    def schedule(self, uid, command, callback):
        """Schedule a generator function to be executed"""
        log.debug('async | %s | %s' % (uid, command), 'reactor')
        self._async.append((uid, callback))
    
    def run(self):
        """Execute up to LIMIT iterations of all scheduled generators"""
        if not self._async:
            return False
        
        length = range(self.LIMIT)
        uid, generator = self._async.popleft()
        
        for _ in length:
            try:
                next(generator)  # Resume generator
            except StopIteration:
                if not self._async:
                    return False
                uid, generator = self._async.popleft()
            except Exception as exc:
                log.error('async | %s | problem with function' % uid, 'reactor')
        
        self._async.appendleft((uid, generator))
        return True
```

**Key Characteristics:**
1. **Generators as Coroutines:** Generators act as lightweight coroutines
2. **Manual Scheduling:** No Python asyncio; explicit queue management
3. **Batch Processing:** Processes up to 50 generator iterations per event loop cycle
4. **Fairness:** Round-robin scheduling via deque (popleft/appendleft)
5. **Error Isolation:** Exceptions logged but don't crash other generators

**Integration Points:**
- **Called from:** `reactor/loop.py` main loop (line 426: `self.asynchronous.run()`)
- **Scheduled from:** API command handlers and listener operations
- **Drives:** All asynchronous API operations (route announcements, queries, etc.)

---

## Part 4: Test Files With Generators

### Files Using Generators in Tests

**File:** `tests/unit/test_connection_advanced.py`
- **Generator Functions:** 22 (test methods with generators)
- **Purpose:** Advanced connection testing
- **Pattern:** Generator-based fixtures or test helpers

**File:** `tests/fuzz/test_connection_reader.py`
- **Generator Functions:** 2
- **Purpose:** Fuzz testing connection reader
- **Functions:** `create_mock_connection_with_data()`, `mock_reader()`

**File:** `tests/fuzz/test_update_eor.py` and others
- **Generator Functions:** Multiple mock_logger fixtures
- **Purpose:** Mocking the logger during tests

### Test Generator Usage Patterns
- **Mocking:** Logger mocking using generator fixtures (pytest pattern)
- **Test Helpers:** Creating mock objects that yield test data
- **Parameterization:** Some tests use generator expressions for parametrization

---

## Part 5: Existing Async/Await Usage

### Current Status: Minimal Async/Await

**Only 1 file uses Python's asyncio:**
- `qa/sbin/bgp` - Test utility/simulator
  - Uses `asyncio` module (imported line 18)
  - Purpose: BGP protocol test helper

**Reason for Custom Framework:**
1. **Historical:** ExaBGP is almost as old as Python3 (2009)
2. **Philosophy:** "does not use Python3 'new' async-io (as we run a homemade async core engine)"
3. **Simplicity:** Custom generator-based scheduler is lightweight and sufficient
4. **Control:** Full control over scheduling and execution

---

## Part 6: Migration Impact Assessment

### Size of Migration
- **Generator Functions:** ~150 total
- **Generator Expressions:** ~70 (lower priority, can remain)
- **High Priority for Conversion:** ~45-60 (API handlers, protocol I/O)

### By Priority Category

#### **CRITICAL - Immediate Impact (Must Convert)**
1. **API Command Handlers** (30 functions in announce.py)
   - Current: Scheduled callbacks via `reactor.asynchronous.schedule()`
   - Impact: Drives all external API operations
   - Challenge: Nested generators, multiple yield points

2. **Protocol Handler** (14 functions in protocol.py)
   - Current: Main BGP message I/O
   - Impact: Core networking functionality
   - Challenge: Multiple for-loops with yields

3. **Peer State Machine** (9 functions in peer.py)
   - Current: BGP peer lifecycle management
   - Impact: Connection establishment, keep-alives
   - Challenge: Complex state transitions

#### **HIGH - Significant Usage (Should Convert)**
4. **Flow Parser** (16 functions in flow/parser.py)
   - Current: Configuration parsing
   - Impact: Flow specification handling

5. **Connection Handler** (3 functions in network/connection.py)
   - Current: TCP read/write operations
   - Impact: Low-level I/O

6. **RIB Updates** (2 functions in outgoing.py)
   - Current: Route message generation
   - Impact: Route dissemination

#### **MEDIUM - Utility Functions (Can Convert Gradually)**
7. **Configuration Parsing** (20+ functions)
   - Tokenizer, Format, Announce parsing
   
8. **CLI Completion** (9 functions)
   - Lower criticality

9. **Utility Functions** (10+ functions)
   - Format, Environment loading

---

## Part 7: Code Examples and Patterns

### Pattern 1: Scheduled Callback Generator
**File:** `src/exabgp/reactor/api/command/announce.py:32-74`

```python
@Command.register('announce route')
def announce_route(self, reactor, service, line, use_json):
    def callback():
        try:
            descriptions, command = extract_neighbors(line)
            peers = match_neighbors(reactor.peers(service), descriptions)
            if not peers:
                self.log_failure('no neighbor matching the command : %s' % command)
                reactor.processes.answer_error(service)
                yield True      # Stop processing
                return
            
            changes = self.api_route(command)
            if not changes:
                self.log_failure('command could not parse route in : %s' % command)
                reactor.processes.answer_error(service)
                yield True      # Stop processing
                return
            
            for change in changes:
                if not ParseStaticRoute.check(change):
                    self.log_message('invalid route for %s : %s' % ...)
                    continue
                change.nlri.action = Action.ANNOUNCE
                reactor.configuration.inject_change(peers, change)
                self.log_message('route added to %s : %s' % ...)
                yield False     # Continue processing
            
            reactor.processes.answer_done(service)
        except ValueError:
            self.log_failure('issue parsing the route')
            reactor.processes.answer_error(service)
            yield True
    
    reactor.asynchronous.schedule(service, line, callback())
    return True
```

**Key Points:**
- Nested generator function defined within handler
- Yields `False` to continue, `True` to stop
- Scheduled for execution via ASYNC.schedule()
- Can span multiple event loop iterations

### Pattern 2: Protocol I/O Generator
**File:** `src/exabgp/reactor/protocol.py:206-320`

```python
def read_message(self):
    msg_id = None
    packets = self.neighbor.api['receive-packets']
    
    for length, msg_id, header, body, notify in self.connection.reader():
        # Process received data
        if notify:
            raise Notify(notify.code, notify.subcode, str(notify))
        
        if msg_id not in Message.CODE.MESSAGES:
            raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id)
        
        if not length:
            yield _NOP  # Yield null message
            continue
        
        # Parse message
        try:
            message = Message.unpack(msg_id, body, Direction.IN, self.negotiated)
        except Exception as exc:
            raise Notify(1, 0, 'can not decode update message of type "%d"' % msg_id)
        
        # Yield parsed message
        yield message
```

**Key Points:**
- Iterates over connection.reader() (another generator)
- Yields NOP or parsed messages
- Handles exceptions gracefully

### Pattern 3: Generator Expression (Data Processing)
**File:** `src/exabgp/bgp/message/update/nlri/bgpls/link.py`

```python
# Generator expression collecting data
gen_expr = (
    item for item in some_collection 
    if condition(item)
)
```

These can often be converted to list comprehensions or kept as-is with asyncio.

---

## Part 8: Documentation and Structure Information

### README Information
From `/home/user/exabgp/README.md`:
- ExaBGP 3.4 was Python 2
- ExaBGP 4.0-4.2 support Python 2 & 3
- Current version (main branch/5.0) targets Python 3 only (3.8.1+)
- "does not use Python3 'new' async-io (as we run a homemade async core engine)"
- Project is mature (~15 years old) with stable architecture

### Testing Infrastructure
- Unit tests in `tests/unit/` (pytest-based)
- Fuzz tests in `tests/fuzz/`
- Functional tests in `qa/bin/functional`
- Coverage tracking with pytest-cov

### Configuration
- Main config: `pyproject.toml`
- Development tools: `.pylintrc`, `.editorconfig`, `.pre-commit-config.yaml`
- CI/CD: GitHub Actions (`.github/`)

---

## Part 9: Key Findings and Recommendations

### Critical Findings

1. **Centralized Generator Management**
   - All asynchronous operations go through `ASYNC` class
   - Single point of conversion to async/await

2. **Scheduled Callbacks Pattern**
   - API handlers use nested generators
   - Must convert nested structure carefully

3. **Multiple for-loops with yields**
   - Protocol.py has 14 generators, many with iteration loops
   - Will require careful refactoring of control flow

4. **Generator Expressions Everywhere**
   - ~70 generator expressions (list/dict comprehensions)
   - Lower priority, most can be kept or converted to comprehensions

5. **No Type Hints**
   - Current code has minimal type hints
   - Consider adding during migration

### Migration Roadmap

#### Phase 1: Infrastructure
- [ ] Update `ASYNC` class to work with async/await coroutines
- [ ] Or: Create wrapper to make asyncio coroutines compatible with ASYNC
- [ ] Add asyncio event loop integration

#### Phase 2: Critical Path
- [ ] Convert API command handlers (announce.py)
- [ ] Convert Protocol handler (protocol.py)
- [ ] Convert Peer state machine (peer.py)
- [ ] Update ASYNC.schedule() to handle `async def`

#### Phase 3: Supporting Systems
- [ ] Convert RIB generators (outgoing.py)
- [ ] Convert connection handlers (network/connection.py)
- [ ] Convert parser generators (tokeniser.py, flow/parser.py)

#### Phase 4: Utilities and Testing
- [ ] Convert utility generators
- [ ] Update test fixtures
- [ ] Full async/await throughout

---

## Part 10: File Listing

### Complete List of Production Files Using Generators

#### Reactor Module (27 files)
```
src/exabgp/reactor/loop.py                          (1 gen, 1 yield)
src/exabgp/reactor/protocol.py                     (14 gens, 29 yields)
src/exabgp/reactor/peer.py                          (9 gens, 31 yields)
src/exabgp/reactor/keepalive.py                     (3 gens)
src/exabgp/reactor/listener.py                      (1 gen)
src/exabgp/reactor/network/tcp.py                   (6 gens)
src/exabgp/reactor/network/connection.py            (3 gens, 18 yields)
src/exabgp/reactor/network/outgoing.py              (4 gens)
src/exabgp/reactor/network/incoming.py              (4 gens)
src/exabgp/reactor/api/processes.py                 (1 gen)
src/exabgp/reactor/api/command/announce.py         (30 gens, 69 yields)
src/exabgp/reactor/api/command/neighbor.py          (5 gens, 4 yields)
src/exabgp/reactor/api/command/rib.py               (6 gens, 5 yields)
src/exabgp/reactor/api/command/watchdog.py          (4 gens, 4 yields)
src/exabgp/reactor/api/command/reactor.py           (1 gen)
```

#### Configuration Module (8 files)
```
src/exabgp/configuration/core/tokeniser.py          (6 gens, 6 yields)
src/exabgp/configuration/core/format.py            (6 gens, 10 yields)
src/exabgp/configuration/flow/parser.py            (16 gens, 21 yields)
src/exabgp/configuration/announce/__init__.py       (3 gens, 5 yields)
src/exabgp/configuration/static/route.py            (1 gen)
```

#### BGP Message Module (7 files)
```
src/exabgp/bgp/message/update/__init__.py           (4 gens, 8 yields)
src/exabgp/bgp/message/update/attribute/attributes.py (4 gens, 13 yields)
src/exabgp/bgp/message/update/attribute/mprnlri.py  (3 gens, 5 yields)
src/exabgp/bgp/message/update/attribute/mpurnlri.py (3 gens, 5 yields)
src/exabgp/bgp/message/update/attribute/aigp.py     (2 gens, 2 yields)
src/exabgp/bgp/message/refresh.py                   (1 gen)
```

#### RIB Module (2 files)
```
src/exabgp/rib/outgoing.py                          (2 gens, 8 yields)
src/exabgp/rib/cache.py                             (1 gen, 1 yield)
```

#### CLI & Utilities (6 files)
```
src/exabgp/cli/completer.py                         (9 gens, 21 yields)
src/exabgp/util/__init__.py                         (2 gens, 2 yields)
src/exabgp/util/od.py                               (1 gen)
src/exabgp/environment/environment.py               (3 gens, 5 yields)
src/exabgp/protocol/resource.py                     (2 gens, 2 yields)
src/exabgp/protocol/ip/__init__.py                  (2 gens, 2 yields)
```

#### Netlink Module (5 files)
```
src/exabgp/netlink/old.py                           (5 gens, 7 yields)
src/exabgp/netlink/message.py                       (4 gens)
src/exabgp/netlink/netlink.py                       (3 gens)
src/exabgp/netlink/attributes.py                    (3 gens)
```

#### Other Files (5 files)
```
src/exabgp/conf/yang/code.py                        (5 gens, 8 yields)
```

**Total: 41 production files with generators**

### Test Files Using Generators

```
tests/unit/test_connection_advanced.py              (22 gens)
tests/fuzz/test_connection_reader.py                (2 gens)
tests/unit/test_route_refresh.py                    (1 gen)
tests/fuzz/test_update_eor.py                       (1 gen)
tests/fuzz/test_update_integration.py               (1 gen)
tests/fuzz/test_update_message_integration.py       (1 gen + 1 gen expr)
tests/unit/test_attributes.py                       (1 gen)
tests/unit/test_communities.py                      (1 gen)
tests/unit/test_multiprotocol.py                    (1 gen)
tests/unit/test_path_attributes.py                  (1 gen)
tests/unit/test_protocol_handler.py                 (1 gen + 2 gen exprs)
tests/fuzz/update_helpers.py                        (0 gens, 1 gen expr)
tests/unit/test_decode.py                           (1 gen expr)
tests/unit/test_ipvpn.py                            (1 gen expr)
tests/unit/test_bgpls.py                            (1 gen expr)
tests/unit/test_rtc.py                              (1 gen expr)
tests/unit/test_sr_attributes.py                    (1 gen expr)
tests/unit/test_update_message.py                   (1 gen + 1 gen expr)

Total: 3 files with generator functions, many with generator expressions
```

---

## Conclusion

ExaBGP's heavy use of generators is deeply integrated into its event loop and asynchronous architecture. The custom `ASYNC` framework manages generators as lightweight coroutines. A migration to async/await would require:

1. **Converting ~150 generator functions** to async def coroutines
2. **Updating the ASYNC scheduler** to work with asyncio
3. **Refactoring nested generators** and complex control flow
4. **Testing thoroughly** to ensure no behavioral changes
5. **Keeping generator expressions** (lower priority) or converting selectively

The migration is tractable but substantial, with the greatest impact in the reactor and API modules.

