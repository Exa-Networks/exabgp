# Tokeniser Usage Guide

## Overview

The `Tokeniser` class (`src/exabgp/reactor/api/tokeniser.py`) is a streaming token reader for the API commands. It provides a consistent pattern for consuming and peeking at tokens.

The configuration files are not read with it any more: the configuration grammar
(`src/exabgp/configuration/grammar/`) has its own lexer and reads a statement through
`Words` (`peek`, `word`, `expect`, `where`), see `.claude/exabgp/CONFIGURATION_GRAMMAR.md`.

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

### `tokeniser.remaining_string()` - Get Unconsumed Tokens

Returns remaining unconsumed tokens joined as a string:

```python
tokeniser.replenish(['peer', '*', 'announce', 'route', '10.0.0.0/24'])
_ = tokeniser()  # 'peer'
_ = tokeniser()  # '*'
remaining = tokeniser.remaining_string()  # 'announce route 10.0.0.0/24'
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

## Reading a configuration

The configuration is read by the grammar, not with a tokeniser loop:

```python
from exabgp.configuration.grammar.read import read_file

settings = read_file('config.conf')  # ConfigurationSettings, or ConfigError with its position
```

## Important Notes

1. **Replenish Behavior**: `replenish()` resets `consumed` to 0
2. **Empty Tokens**: `tokeniser()` returns `''` when exhausted, not `None`

## Summary

| Method | Consumes? | Use Case |
|--------|-----------|----------|
| `tokeniser()` | Yes | Get next token |
| `tokeniser.peek()` | No | Look ahead for branching |
| `tokeniser.consume(x)` | Yes | Assert expected token |
| `tokeniser.consume_if_match(x)` | Conditionally | Optional structure |
| `tokeniser.tokens` | No | Check if tokens exist |
| `tokeniser.replenish(list)` | Resets | Initialize with new tokens |
| `tokeniser.remaining_string()` | No | Get unconsumed tokens as string |

**Key Rules:**
1. Always consume tokens via `tokeniser()` or `consume()` methods
2. Use `peek()` when you need to branch without consuming
3. Don't pass already-consumed tokens as parameters to other functions
4. Don't access `tokeniser.tokens` for positional data - use consume pattern
5. Let each function own its token consumption

---

**Updated:** 2025-12-19
