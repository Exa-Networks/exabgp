# ExaBGP Performance Tests

Comprehensive performance and stress tests for ExaBGP under high message load conditions.

## Overview

This test suite evaluates ExaBGP's performance under various high-load scenarios, including:
- Message parsing throughput
- High message load handling
- Backlog saturation (up to MAX_BACKLOG=15,000)
- Concurrent peer handling
- Memory and resource utilization

## Test Categories

### 1. Message Parsing Performance (`test_message_parsing_performance.py`)

Tests the raw parsing performance of BGP messages.

**Test Classes:**
- `TestUpdateMessageParsingPerformance`: UPDATE message parsing benchmarks
  - Single route updates
  - Multi-route updates (10 routes)
  - Large updates (100 routes)
  - Batch processing (100, 1,000 messages)

- `TestKeepAliveParsingPerformance`: KEEPALIVE message parsing
  - Single message parsing
  - Batch processing (1,000 messages)

- `TestConnectionReaderPerformance`: Connection.reader() method benchmarks
  - Single UPDATE processing
  - Batch UPDATE processing (100 messages)
  - Mixed message types
  - Large UPDATE messages (50 messages with 100 routes each)

- `TestHighVolumeParsingStress`: Extreme volume stress tests
  - 10,000 KEEPALIVE messages
  - 5,000 UPDATE messages
  - 1,000 message continuous stream

**Key Metrics:**
- Messages per second parsing rate
- Latency per message type
- Throughput under sustained load

### 2. High Load Throughput (`test_high_load_throughput.py`)

Tests the Protocol handler's ability to process high message volumes.

**Test Classes:**
- `TestProtocolHandlerThroughput`: Protocol.read_message() performance
  - Single UPDATE processing
  - 100 UPDATE batch processing
  - 1,000 mixed message batch
  - Sustained UPDATE throughput (500 messages)

- `TestMessageQueuePerformance`: Message queue operations
  - Queue append performance (1,000 messages)
  - Queue append/popleft patterns
  - Large queue operations (10,000 messages)

- `TestConcurrentMessageProcessing`: Multi-source message handling
  - Interleaved message streams (5 peers, 200 messages each)
  - Burst message handling (10 bursts of 100 messages)

- `TestHighLoadStress`: Extreme load scenarios
  - 10,000 message processing
  - 10,000 mixed message types
  - 1,000 large UPDATE messages

**Key Metrics:**
- Protocol handler throughput (messages/sec)
- Queue operation latency
- Multi-stream processing efficiency

### 3. Backlog Saturation (`test_backlog_saturation.py`)

Tests behavior at and near the MAX_BACKLOG limit (15,000 messages).

**Test Classes:**
- `TestBacklogNearCapacity`: Backlog performance at various sizes
  - 1,000 messages
  - 5,000 messages
  - 10,000 messages
  - 15,000 messages (MAX_BACKLOG)

- `TestBacklogSaturationBehavior`: Saturation scenarios
  - Cycling at capacity (add/remove operations)
  - Burst handling with existing backlog
  - Large message backlog (memory intensive)

- `TestBacklogMemoryPressure`: Memory usage under backlog pressure
  - Memory growth monitoring
  - Mixed message sizes
  - Memory efficiency testing

- `TestBacklogRecovery`: Recovery from saturation
  - Recovery from MAX_BACKLOG to 10% capacity
  - Sustained processing rate
  - Backlog drain performance

- `TestBacklogStressScenarios`: Extreme stress tests
  - Rapid growth to capacity
  - Oscillating backlog (full/empty cycles)
  - Concurrent add/remove operations (50,000 messages)

**Key Metrics:**
- Backlog operation latency at various sizes
- Memory consumption per message
- Recovery time from saturation

### 4. Concurrent Peers (`test_concurrent_peers.py`)

Tests handling messages from multiple BGP peers simultaneously.

**Test Classes:**
- `TestMultiplePeerProcessing`: Multi-peer message handling
  - 10 peers, 100 messages each
  - 50 concurrent peers
  - 100 peers with mixed message types

- `TestPeerBacklogManagement`: Per-peer backlog management
  - Per-peer backlogs (10 peers, 500 messages each)
  - Shared backlog across peers (20 peers)
  - Priority-based processing (15 peers, 3 priority levels)

- `TestPeerLoadBalancing`: Load balancing algorithms
  - Fair scheduling (10 peers, round-robin)
  - Weighted scheduling (10 peers, variable weights)

- `TestHighPeerCountStress`: High peer count scenarios
  - 500 concurrent peers
  - 1,000 peers with light load
  - Variable load across 200 peers

**Key Metrics:**
- Per-peer message processing rate
- Fair scheduling efficiency
- Scalability with peer count

### 5. Resource Monitoring (`test_resource_monitoring.py`)

Tests with comprehensive system resource monitoring using psutil.

**Test Classes:**
- `TestMemoryUsage`: Memory consumption analysis
  - Baseline message parsing memory
  - Memory growth with backlog
  - Large message handling
  - Memory recovery after load

- `TestResourceUtilization`: CPU and resource usage
  - CPU usage during parsing (5,000 messages)
  - Multi-peer resource utilization (50 peers)

- `TestMemoryLeakDetection`: Memory leak detection
  - Repeated allocation/deallocation cycles
  - Backlog growth/shrink cycles

- `TestScalabilityLimits`: Scalability boundaries
  - Maximum sustainable message rate
  - Backlog size limits testing

- `TestStressWithMonitoring`: Comprehensive stress tests
  - Extreme load with full monitoring (20,000 messages)
  - Sustained high throughput (5 rounds, 5,000 messages each)

**Key Metrics:**
- Memory usage (MB)
- CPU time (seconds)
- Memory leak indicators
- Peak vs. sustained resource usage

## Running the Tests

### Prerequisites

Ensure all dependencies are installed:
```bash
pytest>=7.0
pytest-benchmark>=4.0
psutil
hypothesis>=6.0
```

These are already configured in `pyproject.toml`.

### Run All Performance Tests

```bash
pytest tests/performance/ -v
```

### Run Specific Test Modules

```bash
# Message parsing performance
pytest tests/performance/test_message_parsing_performance.py -v

# High load throughput
pytest tests/performance/test_high_load_throughput.py -v

# Backlog saturation
pytest tests/performance/test_backlog_saturation.py -v

# Concurrent peers
pytest tests/performance/test_concurrent_peers.py -v

# Resource monitoring
pytest tests/performance/test_resource_monitoring.py -v
```

### Run Specific Test Classes

```bash
pytest tests/performance/test_backlog_saturation.py::TestBacklogNearCapacity -v
```

### Benchmark Options

pytest-benchmark provides various options:

```bash
# Save benchmark results
pytest tests/performance/ --benchmark-save=baseline

# Compare with saved results
pytest tests/performance/ --benchmark-compare=baseline

# Only run benchmarks (skip if not benchmark)
pytest tests/performance/ --benchmark-only

# Disable benchmarks
pytest tests/performance/ --benchmark-disable

# Generate histogram
pytest tests/performance/ --benchmark-histogram

# Set minimum rounds
pytest tests/performance/ --benchmark-min-rounds=10
```

### Performance Testing Best Practices

1. **Isolate the test environment**: Close other applications for consistent results
2. **Run multiple times**: Use `--benchmark-min-rounds=10` for statistical significance
3. **Compare baselines**: Save results and compare across code changes
4. **Monitor system resources**: Use resource monitoring tests to detect issues
5. **Test on production-like systems**: Run on hardware similar to production

## Interpreting Results

### Benchmark Output

pytest-benchmark provides detailed statistics:

```
Name (time in ms)                                Min       Max      Mean    StdDev    Median
test_parse_single_route_update                 0.0150    0.0200   0.0165   0.0015    0.0160
test_parse_multi_route_update                  0.0450    0.0550   0.0485   0.0030    0.0480
```

**Key columns:**
- **Min/Max**: Best and worst case timings
- **Mean**: Average performance
- **StdDev**: Consistency (lower is better)
- **Median**: Typical performance (less affected by outliers)

### Performance Indicators

**Good Performance:**
- Low and consistent StdDev
- Linear scaling with message count
- Stable memory usage
- CPU usage proportional to workload

**Performance Issues:**
- High StdDev (inconsistent performance)
- Non-linear scaling
- Memory growth over time (potential leak)
- Excessive CPU usage

### Resource Monitoring

Memory tests return metrics in the results:
- `memory_delta_mb`: Memory change in megabytes
- `cpu_delta`: CPU seconds consumed
- `rate`: Messages per second

## Test Configuration

### MAX_BACKLOG Constant

The backlog saturation tests reference the `MAX_BACKLOG` constant from `exabgp/reactor/protocol.py`:

```python
MAX_BACKLOG = 15000
```

Tests verify behavior at:
- 10% capacity (1,500 messages)
- 33% capacity (5,000 messages)
- 67% capacity (10,000 messages)
- 100% capacity (15,000 messages)

### Message Sizes

Tests use realistic BGP message sizes:
- **Simple UPDATE**: ~60-80 bytes (1 route)
- **Multi-route UPDATE**: ~200-500 bytes (10 routes)
- **Large UPDATE**: ~2,000-4,000 bytes (100-200 routes)
- **KEEPALIVE**: 19 bytes
- **NOTIFICATION**: ~21 bytes

## Continuous Integration

These tests can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Performance Tests
  run: |
    pytest tests/performance/ --benchmark-only --benchmark-save=ci_run
    pytest tests/performance/ --benchmark-compare=baseline --benchmark-compare-fail=mean:10%
```

The `--benchmark-compare-fail` option will fail the build if performance degrades by more than 10%.

## Extending the Tests

### Adding New Benchmarks

1. Create a test class in the appropriate module
2. Use the `benchmark` fixture provided by pytest-benchmark
3. Follow the pattern:

```python
def test_my_benchmark(self, benchmark):
    def my_function():
        # Code to benchmark
        return result

    result = benchmark(my_function)
    assert result == expected
```

### Adding Resource Monitoring

Use psutil to monitor resources:

```python
import psutil
import os

def test_with_monitoring(self, benchmark):
    process = psutil.Process(os.getpid())

    def monitored_function():
        mem_before = process.memory_info().rss / 1024 / 1024
        # Do work
        mem_after = process.memory_info().rss / 1024 / 1024
        return mem_after - mem_before

    result = benchmark(monitored_function)
```

## Known Limitations

1. **Resource tests are environment-dependent**: Memory and CPU measurements vary by system
2. **Concurrent tests are simulated**: Tests simulate concurrent peers but run single-threaded
3. **Network I/O not tested**: Tests use BytesIO instead of real sockets
4. **Platform differences**: Performance may vary between Linux, macOS, Windows

## Troubleshooting

### Tests Running Slowly

- Reduce iteration counts in stress tests
- Use `--benchmark-disable` for quick functional checks
- Run specific test classes instead of full suite

### Inconsistent Results

- Close other applications
- Run with `--benchmark-min-rounds=20` for better statistics
- Check system load: `uptime` or `top`

### Memory Errors

- Reduce message counts in large tests
- Monitor system memory: `free -h` (Linux) or Activity Monitor (macOS)
- Tests may need adjustment for systems with <8GB RAM

## References

- pytest-benchmark documentation: https://pytest-benchmark.readthedocs.io/
- psutil documentation: https://psutil.readthedocs.io/
- ExaBGP Protocol Handler: `src/exabgp/reactor/protocol.py`
- ExaBGP Connection Reader: `src/exabgp/reactor/network/connection.py`
