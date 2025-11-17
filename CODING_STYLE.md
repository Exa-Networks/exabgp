# ExaBGP Coding Style Guide

This document defines the coding style and conventions used throughout the ExaBGP project. These conventions have been derived from analysis of the existing codebase and should be followed for consistency.

## 1. General Formatting

### Indentation and Line Length
- **Indentation**: Use **4 spaces**, never tabs
- **Line length**: Maximum **120 characters** (configured in ruff)
- **Hanging indents**: Use for function parameters and multi-line expressions

```python
# Good
def long_function_name(
    parameter_one, parameter_two, parameter_three,
    parameter_four, parameter_five
):
    return result

# Good
message = self._message(
    self.version.pack_version()
    + self.asn.trans().pack_asn()
    + self.hold_time.pack_holdtime()
)
```

### String Quotes
- **Default**: Use **single quotes** (`'`) for strings
- **Exceptions**: Use double quotes when string contains single quotes or for docstrings
- **Configured in ruff**: `quote-style = "single"`

```python
# Good
log.debug('notification sent', 'reactor')
error_msg = 'invalid message type'

# Good (contains single quote)
message = "can't process this request"
```

## 2. Naming Conventions

### Classes
- **PascalCase** for all class names
- Descriptive names reflecting BGP/networking concepts

```python
class Message:
class KeepAlive:
class NetworkError:
class RouteRefresh:
```

### Functions and Methods
- **snake_case** for all functions and methods
- Descriptive verbs for actions

```python
def unpack_message(cls, data, direction, negotiated):
def handle_connection(self):
def check_generation(self):
```

### Variables and Constants
- **snake_case** for variables and instance attributes
- **UPPER_SNAKE_CASE** for constants and class-level constants
- **Leading underscore** for private/internal variables

```python
# Variables
negotiated = None
message_len = 19
recv_timer = 60

# Constants
MARKER = bytes([0xFF] * 16)
HEADER_LEN = 19
CODE = _MessageCode

# Private
self._restart = True
self._teardown = None
```

## 3. Import Organization

### Order and Style
1. **Future imports** (always first)
2. **Standard library imports**
3. **Third-party imports** (if any)
4. **Local ExaBGP imports**

```python
from __future__ import annotations

import time
from collections import defaultdict
from struct import pack, unpack

from exabgp.bgp.message import Message
from exabgp.bgp.message import Notification
from exabgp.reactor.network.error import NetworkError
```

### Import Preferences
- Use explicit imports: `from module import Class`
- Avoid `import *`
- Group related imports from same module
- One import per line for clarity

## 4. Flow Control and Exception Handling

### Early Returns and Guard Clauses
- **Prefer early returns** to reduce nesting
- **Use guard clauses** for input validation
- **De-indent final actions** when flow control is already handled

```python
# Good - early return pattern
def process_message(self, data):
    if not data:
        return None
    if len(data) < HEADER_LEN:
        raise InvalidMessage('insufficient data')
    return self._parse(data)

# Good - flow control with de-indented final action
if message_exception.message_class == Notify:
    self._handle_notify(message_exception)
    return
elif message_exception.message_class == Notification:
    self._handle_notification(message_exception)
    return
# Final fallback - de-indented
self._handle_unknown(message_exception)
```

### Loop Flow Control
- **Prefer `continue`** over deep nesting in loops
- **De-indent main logic** after handling exceptions

```python
# Good - early continue pattern
for item in items:
    if skip_condition(item):
        continue
    if error_condition(item):
        handle_error(item)
        continue
    # Main logic de-indented
    process_item(item)
```

### Exception Handling
- **Catch specific exceptions first**, then general ones
- **Use `raise` without arguments** to preserve stack trace
- **Include context** in exception messages
- **Use BGP error codes** for protocol-related exceptions

```python
# Good
try:
    message = self.parse(data)
except Message.MessageException as exc:
    if exc.message_class == Notify:
        self._send_notification(exc)
        return
    raise  # Re-raise unexpected exceptions

# Good - BGP-specific error handling
except Message.MessageException as exc:
    if exc.message_class == Notify:
        notify = Notify(exc.code, exc.subcode, exc.data)
        return notify
    # This should never happen - document unexpected paths
    raise RuntimeError(f"Unexpected MessageException from {exc.message_class.__name__}") from exc
```

## 5. Class Design Patterns

### Registry Pattern
- Use class decorators for registration
- Implement factory methods as classmethods

```python
@Message.register
class KeepAlive(Message):
    ID = Message.CODE.KEEPALIVE
    TYPE = bytes([Message.CODE.KEEPALIVE])

@classmethod
def exception(cls, code, subcode=0, message="BGP message error", data=None):
    return cls.MessageException(cls, code, subcode, message, data)
```

### Exception Design
- Create specific exception classes for different error types
- Include all relevant debugging information
- Follow BGP protocol error code conventions

```python
class MessageException(Exception):
    def __init__(self, message_class, code, subcode=0, message="BGP message error", data=None):
        super().__init__(message)
        self.message_class = message_class
        self.code = code
        self.subcode = subcode
        self.data = data
```

## 6. Documentation and Comments

### File Headers
- Include standard header with encoding, description, author, copyright

```python
# encoding: utf-8
"""
message.py

Created by Thomas Mangin on 2010-01-15.
Copyright (c) 2009-2017 Exa Networks. All rights reserved.
License: 3-clause BSD. (See the COPYRIGHT file)
"""
```

### Comment Styles
- **Section dividers**: Use `# ===` pattern for major sections
- **Inline comments**: Reference RFCs, explain BGP protocol details
- **ASCII art**: Use for protocol diagrams and bit field layouts
- **TODO markers**: Use `XXX: FIXME:` for known issues

```python
# =================================================================== KeepAlive
# RFC 4271 Section 4.4

# 0                   1                   2                   3
# 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
# |                           Marker                              |
# +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+

# XXX: FIXME: we could optimize this by caching the packed message
```

## 7. Type Hints and Modern Python

### Type Hints
- **Limited use**: Most legacy code doesn't use type hints
- **Future imports**: Always include `from __future__ import annotations`
- **New code**: Consider adding type hints for complex interfaces

### String Formatting
- **Legacy code**: Uses `%` formatting and `.format()`
- **New code**: Prefer f-strings for readability

```python
# Legacy (acceptable)
message = 'notification sent (%d,%d)' % (code, subcode)

# Modern (preferred for new code)
message = f'notification sent ({code},{subcode})'
```

## 8. BGP-Specific Conventions

### Error Codes and Messages
- Follow RFC 4271 BGP error code conventions
- Include BGP context in error messages
- Use proper notification codes and subcodes

```python
# Good - proper BGP error codes
raise Notify.exception(
    code=1,  # Message Header Error
    subcode=2,  # Bad Message Length
    message=f'Keepalive can not have any payload but contains {hexstring(data)}',
    data=data
)
```

### Protocol Implementation
- **Fail fast**: Validate BGP protocol compliance early
- **Log extensively**: Include debugging information for protocol analysis
- **Follow RFCs**: Reference relevant RFCs in comments

## 9. Testing and Quality

### Searchable Patterns
- Use consistent factory method names (`exception`, `create_message`)
- Enable easy searching for specific patterns in the codebase
- Maintain consistent naming for similar operations

### Error Handling Philosophy
- **Document unexpected code paths** with clear error messages
- **Preserve debugging context** in exceptions
- **Use specific exception types** rather than generic ones

```python
# Good - specific, searchable, documented
raise RuntimeError(f"Unexpected MessageException from {exc.message_class.__name__}") from exc
```

## 10. Tools and Configuration

### Ruff Configuration
The project uses ruff for linting and formatting with these key settings:
- `line-length = 120`
- `quote-style = "single"`
- Indentation: 4 spaces
- Excludes: `dev/` and vendoring directories

### Development Commands
- Format: `ruff format`
- Lint: `ruff check`
- Tests: `./qa/bin/functional encoding` (requires `ulimit -n 64000`)

---

## Summary

The ExaBGP coding style prioritizes:
1. **Consistency** across the large codebase
2. **Clarity** in BGP protocol implementation
3. **Maintainability** through clear naming and structure
4. **Debugging** support through extensive logging and error context
5. **RFC compliance** in protocol implementation

When in doubt, examine existing code in similar modules and follow the established patterns. The style has evolved to support the complex requirements of BGP protocol implementation while maintaining Python best practices.
- `./qa/bin/parsing` - Configuration file parsing tests
