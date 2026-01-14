"""delaymetric.py

BGP-LS Performance Metric Extensions (RFC 8571).

TLV Code to Class Mapping:
+------+---------------------------------------+---------------------------+
| TLV  | IANA/RFC Name                         | ExaBGP Class              |
+------+---------------------------------------+---------------------------+
| 1114 | Unidirectional Link Delay             | UnidirectionalLinkDelay   |
| 1115 | Min/Max Unidirectional Link Delay     | MinMaxUnidirLinkDelay     |
| 1116 | Unidirectional Delay Variation        | UnidirectionalDelayVar    |
| 1117 | Unidirectional Link Loss              | UnidirectionalLinkLoss    |
| 1118 | Unidirectional Residual Bandwidth     | UnidirectionalResidualBw  |
| 1119 | Unidirectional Available Bandwidth    | UnidirectionalAvailableBw |
| 1120 | Unidirectional Utilized Bandwidth     | UnidirectionalUtilizedBw  |
+------+---------------------------------------+---------------------------+

Wire formats per RFC 8571:
- TLV 1114: [A(1)|Rsv(7)][Delay(24)] - 4 bytes, microseconds
- TLV 1115: [A(1)|Rsv(7)][MinDelay(24)][Rsv(8)][MaxDelay(24)] - 8 bytes
- TLV 1116: [Rsv(8)][Variation(24)] - 4 bytes, microseconds (NO A flag)
- TLV 1117: [A(1)|Rsv(7)][Loss(24)] - 4 bytes, units of 0.000003%
- TLV 1118-1120: [Bandwidth(32)] - 4 bytes, IEEE 754 float, bytes/sec

Based on work by Klaus Schneider (https://github.com/klausps).
Copyright (c) 2014-2017 Exa Networks. All rights reserved.
"""

from __future__ import annotations

from struct import pack, unpack

from exabgp.bgp.message.update.attribute.bgpls.linkstate import LinkState, BaseLS
from exabgp.util.types import Buffer

# 24-bit maximum value (0xFFFFFF)
_MAX_24BIT: int = 16777215
# Maximum link loss percentage (24-bit max * 0.000003)
_MAX_LOSS_PERCENT = _MAX_24BIT * 0.000003  # ~50.331645%


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |A|  RESERVED   |                   Delay                       |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  RFC 8571 Section 3 - Unidirectional Link Delay


@LinkState.register_lsid(tlv=1114, json_key='unidirectional-link-delay', repr_name='Unidirectional Link Delay')
class UnidirectionalLinkDelay(BaseLS):
    LEN = 4

    @property
    def content(self) -> dict[str, int | bool]:
        """Unpack delay value and anomalous flag from packed bytes."""
        anomalous = bool(self._packed[0] & 0x80)
        delay_us = int.from_bytes(b'\x00' + bytes(self._packed[1:4]), 'big')
        return {'delay-us': delay_us, 'anomalous': anomalous}

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> UnidirectionalLinkDelay:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_link_delay(cls, delay_us: int, anomalous: bool = False) -> UnidirectionalLinkDelay:
        """Factory method to create UnidirectionalLinkDelay.

        Args:
            delay_us: Delay in microseconds (0-16777215, ~16.7 seconds max)
            anomalous: True if value is anomalous/unreliable
        """
        if not 0 <= delay_us <= _MAX_24BIT:
            raise ValueError(f'delay_us must be 0-{_MAX_24BIT}, got {delay_us}')
        flags = 0x80 if anomalous else 0x00
        delay_bytes = delay_us.to_bytes(3, 'big')
        return cls(bytes([flags]) + delay_bytes)


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |A|  RESERVED   |                   Min Delay                   |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |   RESERVED    |                   Max Delay                   |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  RFC 8571 Section 4 - Min/Max Unidirectional Link Delay


@LinkState.register_lsid(
    tlv=1115, json_key='minmax-unidirectional-link-delay', repr_name='Min/Max Unidirectional Link Delay'
)
class MinMaxUnidirLinkDelay(BaseLS):
    LEN = 8

    @property
    def content(self) -> dict[str, int | bool]:
        """Unpack min/max delay values and anomalous flag from packed bytes."""
        anomalous = bool(self._packed[0] & 0x80)
        min_delay_us = int.from_bytes(b'\x00' + bytes(self._packed[1:4]), 'big')
        max_delay_us = int.from_bytes(b'\x00' + bytes(self._packed[5:8]), 'big')
        return {'min-delay-us': min_delay_us, 'max-delay-us': max_delay_us, 'anomalous': anomalous}

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> MinMaxUnidirLinkDelay:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_minmax_delay(cls, min_delay_us: int, max_delay_us: int, anomalous: bool = False) -> MinMaxUnidirLinkDelay:
        """Factory method to create MinMaxUnidirLinkDelay.

        Args:
            min_delay_us: Minimum delay in microseconds (0-16777215)
            max_delay_us: Maximum delay in microseconds (0-16777215)
            anomalous: True if values are anomalous/unreliable
        """
        if not 0 <= min_delay_us <= _MAX_24BIT:
            raise ValueError(f'min_delay_us must be 0-{_MAX_24BIT}, got {min_delay_us}')
        if not 0 <= max_delay_us <= _MAX_24BIT:
            raise ValueError(f'max_delay_us must be 0-{_MAX_24BIT}, got {max_delay_us}')
        flags = 0x80 if anomalous else 0x00
        min_bytes = min_delay_us.to_bytes(3, 'big')
        max_bytes = max_delay_us.to_bytes(3, 'big')
        return cls(bytes([flags]) + min_bytes + bytes([0x00]) + max_bytes)


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |   RESERVED    |               Delay Variation                 |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  RFC 8571 Section 5 - Unidirectional Delay Variation
#  NOTE: No A (anomalous) flag for this TLV per RFC 8571


@LinkState.register_lsid(
    tlv=1116, json_key='unidirectional-delay-variation', repr_name='Unidirectional Delay Variation'
)
class UnidirectionalDelayVar(BaseLS):
    LEN = 4

    @property
    def content(self) -> int:
        """Unpack delay variation value from packed bytes (microseconds)."""
        return int.from_bytes(b'\x00' + bytes(self._packed[1:4]), 'big')

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> UnidirectionalDelayVar:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_delay_variation(cls, variation_us: int) -> UnidirectionalDelayVar:
        """Factory method to create UnidirectionalDelayVar.

        Args:
            variation_us: Delay variation in microseconds (0-16777215)
        """
        if not 0 <= variation_us <= _MAX_24BIT:
            raise ValueError(f'variation_us must be 0-{_MAX_24BIT}, got {variation_us}')
        variation_bytes = variation_us.to_bytes(3, 'big')
        return cls(bytes([0x00]) + variation_bytes)


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |A|  RESERVED   |                  Link Loss                    |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  RFC 8571 Section 6 - Unidirectional Link Loss
#  Value in units of 0.000003% (range 0-50.331642%)


@LinkState.register_lsid(tlv=1117, json_key='unidirectional-link-loss', repr_name='Unidirectional Link Loss')
class UnidirectionalLinkLoss(BaseLS):
    LEN = 4

    # RFC 8571: Link loss is encoded as (loss% / 0.000003), giving 24 bits for 0-50.331642%
    _UNIT_PERCENT = 0.000003

    @property
    def content(self) -> dict[str, float | bool]:
        """Unpack link loss value and anomalous flag from packed bytes."""
        anomalous = bool(self._packed[0] & 0x80)
        encoded = int.from_bytes(b'\x00' + bytes(self._packed[1:4]), 'big')
        loss_percent = encoded * self._UNIT_PERCENT
        return {'loss-percent': loss_percent, 'anomalous': anomalous}

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> UnidirectionalLinkLoss:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_link_loss(cls, loss_percent: float, anomalous: bool = False) -> UnidirectionalLinkLoss:
        """Factory method to create UnidirectionalLinkLoss.

        Args:
            loss_percent: Link loss percentage (0.0-50.331645%)
            anomalous: True if value is anomalous/unreliable
        """
        if not 0.0 <= loss_percent <= _MAX_LOSS_PERCENT:
            raise ValueError(f'loss_percent must be 0.0-{_MAX_LOSS_PERCENT:.6f}, got {loss_percent}')
        encoded = int(loss_percent / cls._UNIT_PERCENT)
        if encoded > _MAX_24BIT:
            encoded = _MAX_24BIT
        flags = 0x80 if anomalous else 0x00
        loss_bytes = encoded.to_bytes(3, 'big')
        return cls(bytes([flags]) + loss_bytes)


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |                     Residual Bandwidth                        |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  RFC 8571 Section 7 - Unidirectional Residual Bandwidth
#  IEEE 754 single-precision float, bytes per second


@LinkState.register_lsid(
    tlv=1118, json_key='unidirectional-residual-bandwidth', repr_name='Unidirectional Residual Bandwidth'
)
class UnidirectionalResidualBw(BaseLS):
    LEN = 4

    @property
    def content(self) -> float:
        """Unpack residual bandwidth from packed bytes (bytes/sec)."""
        value: float = unpack('!f', self._packed)[0]
        return value

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> UnidirectionalResidualBw:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_residual_bandwidth(cls, bandwidth: float) -> UnidirectionalResidualBw:
        """Factory method to create UnidirectionalResidualBw.

        Args:
            bandwidth: Residual bandwidth in bytes/sec (non-negative)
        """
        if bandwidth < 0:
            raise ValueError(f'bandwidth must be non-negative, got {bandwidth}')
        return cls(pack('!f', bandwidth))


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |                    Available Bandwidth                        |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  RFC 8571 Section 8 - Unidirectional Available Bandwidth
#  IEEE 754 single-precision float, bytes per second


@LinkState.register_lsid(
    tlv=1119, json_key='unidirectional-available-bandwidth', repr_name='Unidirectional Available Bandwidth'
)
class UnidirectionalAvailableBw(BaseLS):
    LEN = 4

    @property
    def content(self) -> float:
        """Unpack available bandwidth from packed bytes (bytes/sec)."""
        value: float = unpack('!f', self._packed)[0]
        return value

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> UnidirectionalAvailableBw:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_available_bandwidth(cls, bandwidth: float) -> UnidirectionalAvailableBw:
        """Factory method to create UnidirectionalAvailableBw.

        Args:
            bandwidth: Available bandwidth in bytes/sec (non-negative)
        """
        if bandwidth < 0:
            raise ValueError(f'bandwidth must be non-negative, got {bandwidth}')
        return cls(pack('!f', bandwidth))


#   0                   1                   2                   3
#   0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1 2 3 4 5 6 7 8 9 0 1
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  |                    Utilized Bandwidth                         |
#  +-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+-+
#  RFC 8571 Section 9 - Unidirectional Utilized Bandwidth
#  IEEE 754 single-precision float, bytes per second


@LinkState.register_lsid(
    tlv=1120, json_key='unidirectional-utilized-bandwidth', repr_name='Unidirectional Utilized Bandwidth'
)
class UnidirectionalUtilizedBw(BaseLS):
    LEN = 4

    @property
    def content(self) -> float:
        """Unpack utilized bandwidth from packed bytes (bytes/sec)."""
        value: float = unpack('!f', self._packed)[0]
        return value

    @classmethod
    def unpack_bgpls(cls, data: Buffer) -> UnidirectionalUtilizedBw:
        cls.check(data)
        return cls(data)

    @classmethod
    def make_utilized_bandwidth(cls, bandwidth: float) -> UnidirectionalUtilizedBw:
        """Factory method to create UnidirectionalUtilizedBw.

        Args:
            bandwidth: Utilized bandwidth in bytes/sec (non-negative)
        """
        if bandwidth < 0:
            raise ValueError(f'bandwidth must be non-negative, got {bandwidth}')
        return cls(pack('!f', bandwidth))
