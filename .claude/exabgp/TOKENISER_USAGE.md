# Tokeniser Usage Guide

## Overview

The `Tokeniser` class (`src/exabgp/configuration/core/parser.py`) is a streaming token parser used throughout ExaBGP for configuration files and API commands. It provides a consistent pattern for consuming and peeking at tokens.

## Core API

### `tokeniser()` - Consume Next Token

Calling the tokeniser as a function consumes and returns the next token:

```python
def my_parser(tokeniser: Tokeniser) -> Result:
    value = tokeniser()  # Consume and return next token
    return Result(value)
```

### `tokeniser.peek()` - Look Ahead Without Consuming

Peek at the next token without consuming it:

```python
def as_path(tokeniser: Tokeniser) -> AS2Path:
    value = tokeniser()  # Get current token

    if value == '[':
        next_value = tokeniser.peek()  # Look at what's next

        if next_value != '{':
            insert = SEQUENCE()
        else:
            insert = CONFED_SEQUENCE()
```

### `tokeniser.consume(name)` - Consume Expected Token

Consume a token and raise ValueError if it doesn't match:

```python
def parse_block(tokeniser: Tokeniser):
    tokeniser.consume('{')  # Raises if next token isn't '{'
    # ... parse contents ...
    tokeniser.consume('}')  # Raises if next token isn't '}'
```

### `tokeniser.consume_if_match(name)` - Conditional Consume

Peek and consume only if it matches:

```python
def parse_optional_brackets(tokeniser: Tokeniser):
    if tokeniser.consume_if_match('['):
        # Has brackets, parse list
        while not tokeniser.consume_if_match(']'):
            yield tokeniser()
    else:
        # Single value
        yield tokeniser()
```

### `tokeniser.tokens` - Check If Tokens Remain

The `tokens` attribute contains the original token list (useful for checking if there are tokens):

```python
def aigp(tokeniser: Tokeniser) -> AIGP:
    if not tokeniser.tokens:
        raise ValueError('aigp requires a value')
    value = tokeniser()
```

### `tokeniser.replenish(content)` - Reset With New Tokens

Used to reset the tokeniser with a new list of tokens:

```python
tokeniser.replenish(['announce', 'route', '10.0.0.0/24'])
```

## Correct Patterns

### Pattern 1: Simple Value Parsing

```python
def origin(tokeniser: Tokeniser) -> Origin:
    value = tokeniser().lower()
    if value == 'igp':
        return Origin.from_int(Origin.IGP)
    if value == 'egp':
        return Origin.from_int(Origin.EGP)
    raise ValueError(f"'{value}' is not a valid origin")
```

### Pattern 2: Bracketed Lists

```python
def community(tokeniser: Tokeniser) -> Communities:
    communities = Communities()

    value = tokeniser()
    if value == '[':
        while True:
            value = tokeniser()
            if value == ']':
                break
            communities.add(_community(value))
    else:
        communities.add(_community(value))

    return communities
```

### Pattern 3: Look-Ahead for Branching

```python
def as_path(tokeniser: Tokeniser) -> AS2Path:
    value = tokeniser()

    if value == '[':
        # Peek to decide which type without consuming
        if tokeniser.peek() != '{':
            insert = SEQUENCE()
        else:
            insert = CONFED_SEQUENCE()
```

### Pattern 4: Nested Structures with Peek

```python
def parse_selectors(tokeniser: Tokeniser) -> list[str]:
    descriptions = []
    current = []

    while True:
        peeked = tokeniser.peek()
        if not peeked or peeked == ']':
            if peeked:
                tokeniser()  # Consume the ']'
            if current:
                descriptions.append(current)
            break
        if peeked == ',':
            tokeniser()  # Consume the ','
            if current:
                descriptions.append(current)
                current = []
            continue

        # Consume the actual token
        tok = tokeniser()
        current.append(tok)

    return descriptions
```

## Anti-Patterns to Avoid

### Anti-Pattern 1: Passing First Token as Parameter

**BAD:**
```python
def extract_selector_with_first(first_token: str, tokeniser: Tokeniser) -> list[str]:
    # The first token has already been consumed by the dispatch loop
    if first_token == '*':
        return ['*']
```

**WHY IT'S BAD:**
- Breaks the tokeniser abstraction
- Creates confusion about token ownership
- Harder to reason about state

**GOOD:**
```python
def extract_selector(tokeniser: Tokeniser) -> list[str]:
    first_token = tokeniser()  # Let this function consume
    if first_token == '*':
        return ['*']
```

### Anti-Pattern 2: Using `tokeniser.tokens` for Positional Access

**BAD:**
```python
def inherit(tokeniser) -> list[str]:
    if tokeniser.tokens[1] != '[':  # Direct array access
        return tokeniser.tokens[2:-1]  # Returns raw tokens, breaks abstraction
```

**WHY IT'S BAD:**
- Bypasses the consume/peek pattern
- Makes token consumption tracking unreliable
- Couples to internal representation

**GOOD:**
```python
def inherit(tokeniser) -> list[str]:
    first = tokeniser()  # Consume first
    if tokeniser.peek() != '[':
        return [first]

    tokeniser()  # Consume '['
    result = []
    while True:
        tok = tokeniser()
        if tok == ']':
            break
        if tok != ',':
            result.append(tok)
    return result
```

### Anti-Pattern 3: Not Using peek() When Branching

**BAD:**
```python
def parse_value(tokeniser: Tokeniser):
    value = tokeniser()
    if value == '[':
        # Now we need to know what's next but we consumed it
        next_val = tokeniser()
        if next_val == '{':
            # We consumed '{' but maybe we needed it for another reason
```

**GOOD:**
```python
def parse_value(tokeniser: Tokeniser):
    value = tokeniser()
    if value == '[':
        # Peek to decide without consuming
        if tokeniser.peek() == '{':
            # Handle confed case, can still consume '{' later if needed
```

## State Tracking

### `tokeniser.consumed` - Track Consumption

The `consumed` attribute tracks how many tokens have been consumed:

```python
tokeniser.replenish(['peer', '*', 'announce', 'route'])
_ = tokeniser()  # 'peer' - consumed = 1
_ = tokeniser()  # '*' - consumed = 2

# Used to extract remaining command string
remaining_tokens = original_command.split()[tokeniser.consumed:]
```

### `tokeniser.afi` - Address Family Context

Parser functions can set/check AFI context:

```python
def prefix(tokeniser: Tokeniser) -> IPRange:
    ip = tokeniser()
    ip_obj = IP.from_string(ip)
    tokeniser.afi = IP.toafi(ip)  # Set context for later parsers
    return ip_obj
```

## The Parser Class

The `Parser` class (`src/exabgp/configuration/core/parser.py`) wraps `Tokeniser` and handles line-by-line reading from files, text, or API commands.

### Parser Architecture

```
Input Source (file/text/api)
    ↓
format.py:tokens() - Lexical analysis
    ↓ yields list[tuple[line, col, word]]
Parser._tokenise() - Extract words
    ↓ yields list[str] per line
Parser.__call__() - Advance to next line
    ↓ replenishes tokeniser
Tokeniser - Token-by-token consumption
```

### Parser Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `tokeniser` | `Tokeniser` | The tokeniser for current line |
| `line` | `list[str]` | Current line's tokens (including terminator) |
| `end` | `str` | Line terminator: `{`, `}`, or `;` |
| `number` | `int` | Current line number |
| `fname` | `str` | Source filename |
| `type` | `str` | Source type: `'file'`, `'text'`, or `'unset'` |
| `finished` | `bool` | True when all lines consumed |
| `scope` | `Scope` | Configuration scope for nested blocks |
| `error` | `Error` | Error handler |

### Input Methods

#### `parser.set_file(filename)` - Parse Configuration File

```python
parser = Parser(scope, error)
if parser.set_file('/etc/exabgp/config.conf'):
    while parser():
        process_line(parser)
```

Features:
- Handles line continuation with `\`
- Tracks line numbers for errors
- Processes escape sequences (`\n`, `\t`, etc.)

#### `parser.set_text(text)` - Parse String

```python
parser = Parser(scope, error)
parser.set_text('''
neighbor 10.0.0.1 {
    router-id 1.2.3.4;
}
''')
while parser():
    process_line(parser)
```

#### `parser.set_api(line)` - Parse Single API Command

```python
parser = Parser(scope, error)
parser.set_api('announce route 10.0.0.0/24 next-hop 1.2.3.4')
parser()  # Advance to the line
# Now parser.tokeniser has: ['announce', 'route', '10.0.0.0/24', 'next-hop', '1.2.3.4']
```

### Line Termination

The `format.py:tokens()` function treats these as line terminators:
- `;` - Statement end
- `{` - Block open
- `}` - Block close

After `parser()` is called:
- `parser.line` contains all tokens including terminator
- `parser.tokeniser` is replenished with tokens EXCLUDING terminator
- `parser.end` contains the terminator

Example:
```python
# Input: "neighbor 10.0.0.1 {"
parser()
# parser.line = ['neighbor', '10.0.0.1', '{']
# parser.end = '{'
# parser.tokeniser has ['neighbor', '10.0.0.1'] (no '{')
```

### Token Preprocessing (format.py)

The `format.py` module performs lexical preprocessing:

```python
# Adds spaces around brackets
'[a,b]' → '[ a , b ]'
'(x)' → '( x )'

# Handles quoted strings (preserves spaces)
'"hello world"' → 'hello world'  # As single token

# Handles escape sequences
'\\n' → '\n'
'\\t' → '\t'
'\\uXXXX' → Unicode character
```

### Parser Usage Pattern

```python
from exabgp.configuration.core.parser import Parser
from exabgp.configuration.core.scope import Scope
from exabgp.configuration.core.error import Error

scope = Scope()
error = Error()
parser = Parser(scope, error)

parser.set_file('config.conf')

while parser():
    keyword = parser.tokeniser()

    if keyword == 'neighbor':
        ip = parser.tokeniser()
        if parser.end == '{':
            # Start of neighbor block
            parse_neighbor_block(parser, ip)
        else:
            # Single line neighbor statement
            parse_neighbor_statement(parser, ip)

    elif keyword == 'route':
        prefix = parser.tokeniser()
        parse_route(parser, prefix)
```

### Important Notes

1. **Line vs Tokeniser**: `parser.line` includes the terminator, `parser.tokeniser` does not
2. **Terminator Check**: Always check `parser.end` to know if entering a block
3. **Replenish Behavior**: `replenish()` decrements `consumed` by 1 (for internal tracking)
4. **Empty Tokens**: `tokeniser()` returns `''` when exhausted, not `None`

## Summary

| Method | Consumes? | Use Case |
|--------|-----------|----------|
| `tokeniser()` | Yes | Get next token |
| `tokeniser.peek()` | No | Look ahead for branching |
| `tokeniser.consume(x)` | Yes | Assert expected token |
| `tokeniser.consume_if_match(x)` | Conditionally | Optional structure |
| `tokeniser.tokens` | No | Check if tokens exist |
| `tokeniser.replenish(list)` | Resets | Initialize with new tokens |

**Key Rules:**
1. Always consume tokens via `tokeniser()` or `consume()` methods
2. Use `peek()` when you need to branch without consuming
3. Don't pass already-consumed tokens as parameters to other functions
4. Don't access `tokeniser.tokens` for positional data - use consume pattern
5. Let each function own its token consumption
