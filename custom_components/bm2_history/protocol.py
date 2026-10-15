"""BM2 history protocol, ported from KrystianD/bm2-battery-monitor (MIT).

Upstream: bm2_python/src/bm2/{client,encryption,bit_utils}.py.
Records have no clock; timestamps assume uninterrupted two-minute sampling.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = bytes([108, 101, 97, 103, 101, 110, 100, 255, 254, 49, 56, 56, 50, 52, 54, 54])
READ_UUID = "0000fff4-0000-1000-8000-00805f9b34fb"
WRITE_UUID = "0000fff3-0000-1000-8000-00805f9b34fb"
MAX_HISTORY_BYTES = 1024 * 1024


def encrypt_command(data: bytes) -> bytes:
    encryptor = Cipher(algorithms.AES(KEY), modes.CBC(bytes(16))).encryptor()
    padded = data + bytes((-len(data)) % 16)
    return encryptor.update(padded) + encryptor.finalize()


def decrypt_notification(data: bytes) -> bytes:
    if not data or len(data) % 16:
        raise ValueError("BM2 notification must contain complete AES blocks")
    result = bytearray()
    # BM2 resets its IV for each block, including within one notification.
    for offset in range(0, len(data), 16):
        decryptor = Cipher(algorithms.AES(KEY), modes.CBC(bytes(16))).decryptor()
        result.extend(decryptor.update(data[offset : offset + 16]) + decryptor.finalize())
    return bytes(result)


class HistoryBuffer:
    """Accept decrypted notifications and validate the final byte count."""

    def __init__(self):
        self.receiving = False
        self.complete = False
        self.data = bytearray()

    def feed(self, packet: bytes) -> int | None:
        if len(packet) != 16:
            raise ValueError("Expected one decrypted AES block")
        if packet[0] == 0xF5:
            return None
        if packet[0] == 0xE7:
            size = int.from_bytes(packet[1:4], "big")
            if size > MAX_HISTORY_BYTES + 9:
                raise ValueError("BM2 history exceeds the 1 MiB limit")
            if size == 0:
                self.complete = True
            return size
        if packet[:3] == b"\xff\xff\xfe":
            self.receiving = True
            self.data.clear()
        elif self.receiving and packet[:3] == b"\xff\xfe\xfe":
            size = int.from_bytes(packet[3:6], "big") - 9
            if size < 0 or size > len(self.data) or size % 4:
                raise ValueError("Invalid or truncated BM2 history")
            del self.data[size:]
            self.receiving = False
            self.complete = True
        elif self.receiving:
            if len(self.data) + len(packet) > MAX_HISTORY_BYTES:
                raise ValueError("BM2 history exceeds the 1 MiB limit")
            self.data.extend(packet)
        return None


@dataclass(frozen=True)
class Reading:
    timestamp: datetime
    voltage: float
    min_crank_voltage: float
    kind: int


def decode_records(data: bytes, downloaded_at: datetime) -> list[Reading]:
    if len(data) % 4:
        raise ValueError("History records must be four bytes")
    if downloaded_at.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")
    anchor = downloaded_at.replace(second=0, microsecond=0)
    count = len(data) // 4
    readings = []
    for index in range(count):
        value = int.from_bytes(data[index * 4 : index * 4 + 4], "big")
        readings.append(
            Reading(
                anchor - timedelta(minutes=(count - 1 - index) * 2),
                (value >> 20) / 100,
                ((value >> 4) & 0xFFF) / 100,
                value & 0xF,
            )
        )
    return readings


def hourly_statistics(readings: list[Reading], now: datetime) -> list[dict]:
    """Export complete UTC hours only, without inventing partial-hour extrema."""
    buckets = defaultdict(list)
    for reading in readings:
        hour = reading.timestamp.replace(minute=0, second=0, microsecond=0)
        buckets[hour].append(reading.voltage)
    current_hour = now.replace(minute=0, second=0, microsecond=0)
    return [
        {
            "start": hour,
            "min": min(values),
            "max": max(values),
            "mean": sum(values) / len(values),
            "mean_weight": len(values),
        }
        for hour, values in sorted(buckets.items())
        if hour < current_hour and len(values) == 30
    ]
