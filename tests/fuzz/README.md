# ExaBGP Fuzz Testing Suite

This directory contains fuzz tests for ExaBGP using property-based testing with [Hypothesis](https://hypothesis.readthedocs.io/).

## Overview

Fuzz testing helps discover edge cases, boundary conditions, and potential security vulnerabilities by testing with randomly generated inputs. These tests validate that ExaBGP's parsers and validators handle malformed, unexpected, or malicious input gracefully without crashing.

## Test Coverage

### Configuration Parser Tests (`test_random_input_validation.py`)

**Tokenizer Robustness:**
- Random text input validation
- Whitespace-only configurations
- Empty configurations
- Nested configuration blocks

**Value Validation:**
- IPv4 address and prefix creation
- Port number ranges (1-65535)
- ASN number ranges (0-4294967295)
- Community values

### BGP Message Wire Format Tests

**Connection Reader:**
- Random binary data handling
- BGP message header validation (marker, length, type)
- Truncated message handling

**Message Types:**
- OPEN message parsing with valid parameters
- UPDATE message robustness with random data
- MPLS label validation

### Edge Cases and Boundary Tests

- Truncated BGP headers
- Invalid marker patterns
- Length field mismatches
- Empty and whitespace-only inputs

## Running the Tests

### Run all fuzz tests:
```bash
uv run pytest tests/fuzz -m fuzz -v
```

### Run specific test file:
```bash
uv run pytest tests/fuzz/test_random_input_validation.py -v
```

### Run with coverage:
```bash
uv run pytest tests/fuzz -m fuzz --cov=exabgp --cov-report=html
```

### Adjust number of test examples:
```bash
# Run with more examples for deeper fuzzing
uv run pytest tests/fuzz -m fuzz --hypothesis-seed=12345
```

## Test Configuration

Tests use Hypothesis settings configured in the test files:
- `max_examples`: Number of random inputs to generate (default: 50-100)
- `deadline`: Maximum time per test (typically disabled for fuzz tests)
- `suppress_health_check`: Suppresses warnings for slow tests

## What These Tests Validate

1. **No Crashes**: Parsers handle invalid input without segfaults or uncaught exceptions
2. **Proper Error Handling**: Invalid input produces appropriate error messages
3. **Boundary Conditions**: Edge cases at min/max values are handled correctly
4. **Type Safety**: Type validation prevents incorrect data types
5. **Protocol Compliance**: Wire-format parsers reject malformed BGP messages

## Test Results

As of the latest run:
- **14 fuzz tests** implemented
- **14 tests passing** (100% pass rate)
- **Coverage areas**: Configuration parsing, BGP message parsing, value validation

### Sample Test Output:
```
tests/fuzz/test_random_input_validation.py::test_tokeniser_robustness PASSED
tests/fuzz/test_random_input_validation.py::test_ipv4_creation PASSED
tests/fuzz/test_random_input_validation.py::test_port_number_range PASSED
tests/fuzz/test_random_input_validation.py::test_asn_number_range PASSED
tests/fuzz/test_random_input_validation.py::test_connection_reader_robustness PASSED
tests/fuzz/test_random_input_validation.py::test_bgp_header_validation PASSED
...

============================== 14 passed in 2.15s ==============================
```

## Adding New Fuzz Tests

To add new fuzz tests:

1. Import Hypothesis strategies:
```python
from hypothesis import given, strategies as st, settings, HealthCheck
```

2. Define a test with random inputs:
```python
@pytest.mark.fuzz
@given(data=st.binary(min_size=0, max_size=1000))
@settings(deadline=None, max_examples=100)
def test_my_parser(data):
    """Test parser with random binary data."""
    try:
        result = my_parser(data)
        # Validate result
    except ExpectedException:
        # Expected for invalid input
        pass
```

3. Mark the test with `@pytest.mark.fuzz` decorator

4. Run the new test to verify it works

## Integration with CI/CD

Fuzz tests are integrated into the test suite and can be:
- **Included in CI**: Add `-m fuzz` to pytest command
- **Excluded from quick tests**: Use `-m "not fuzz"` for faster test runs
- **Run separately**: Execute fuzz tests in dedicated fuzzing pipelines

## References

- [Hypothesis Documentation](https://hypothesis.readthedocs.io/)
- [Property-Based Testing](https://increment.com/testing/in-praise-of-property-based-testing/)
- [BGP RFC 4271](https://www.rfc-editor.org/rfc/rfc4271.html)
- [ExaBGP Documentation](https://github.com/Exa-Networks/exabgp/wiki)

## Maintenance

- Review and update tests when adding new parsers or protocols
- Increase `max_examples` periodically for deeper fuzzing
- Monitor test execution time and adjust timeouts as needed
- Use `--hypothesis-seed` for reproducible test runs when debugging failures
