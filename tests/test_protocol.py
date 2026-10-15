"""Protocol tests run without installing Home Assistant."""

import importlib.util
import sys
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

path = Path(__file__).parents[1] / "custom_components/bm2_history/protocol.py"
spec = importlib.util.spec_from_file_location("bm2_protocol", path)
protocol = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = protocol
spec.loader.exec_module(protocol)


def packet(data):
    return data.ljust(16, b"\0")


class ProtocolTests(unittest.TestCase):
    def test_crypto_and_per_block_iv_reset(self):
        first = packet(b"\xe7\x01")
        second = packet(b"\xe3\x00\x00\x00\x00\x00\x04")
        wire = protocol.encrypt_command(first) + protocol.encrypt_command(second)
        self.assertEqual(protocol.decrypt_notification(wire), first + second)
        with self.assertRaises(ValueError):
            protocol.decrypt_notification(b"short")

    def test_count_stream_and_padding(self):
        buffer = protocol.HistoryBuffer()
        self.assertEqual(buffer.feed(packet(b"\xe7\x00\x00\x0d")), 13)
        buffer.feed(packet(b"\xff\xff\xfe"))
        record = bytes.fromhex("4d411111")
        buffer.feed(packet(record))
        buffer.feed(packet(b"\xff\xfe\xfe\x00\x00\x0d"))
        self.assertTrue(buffer.complete)
        self.assertEqual(buffer.data, record)
        reading = protocol.decode_records(record, datetime(2026, 10, 14, tzinfo=UTC))[0]
        self.assertEqual(reading.voltage, 12.36)
        self.assertEqual(reading.min_crank_voltage, 2.73)
        self.assertEqual(reading.kind, 1)

    def test_empty_history(self):
        buffer = protocol.HistoryBuffer()
        self.assertEqual(buffer.feed(packet(b"\xe7")), 0)
        self.assertTrue(buffer.complete)

    def test_truncated_history_is_rejected(self):
        buffer = protocol.HistoryBuffer()
        buffer.feed(packet(b"\xff\xff\xfe"))
        with self.assertRaises(ValueError):
            buffer.feed(packet(b"\xff\xfe\xfe\x00\x00\x0d"))

    def test_unaligned_record_count_is_rejected(self):
        buffer = protocol.HistoryBuffer()
        buffer.feed(packet(b"\xff\xff\xfe"))
        buffer.feed(bytes(16))
        with self.assertRaises(ValueError):
            buffer.feed(packet(b"\xff\xfe\xfe\x00\x00\x0e"))

    def test_estimated_timestamps_and_hourly_stats(self):
        now = datetime(2026, 10, 14, 12, 0, 45, tzinfo=UTC)
        data = bytes.fromhex("4d411111") * 31
        readings = protocol.decode_records(data, now)
        self.assertEqual(readings[0].timestamp, now.replace(hour=11, second=0))
        self.assertEqual(readings[-1].timestamp, now.replace(second=0))
        stats = protocol.hourly_statistics(readings, now)
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats[0]["start"].hour, 11)
        self.assertAlmostEqual(stats[0]["mean"], 12.36)
        self.assertEqual(stats[0]["min"], 12.36)
        self.assertEqual(stats[0]["max"], 12.36)

    def test_partial_oldest_hour_is_not_imported(self):
        now = datetime(2026, 10, 14, 12, 10, tzinfo=UTC)
        readings = protocol.decode_records(bytes.fromhex("4d411111") * 31, now)
        self.assertEqual(protocol.hourly_statistics(readings, now), [])

    def test_sample_extrema_and_mean(self):
        start = datetime(2026, 10, 14, 11, tzinfo=UTC)
        readings = [
            protocol.Reading(start + timedelta(minutes=i * 2), 10 + i / 10, 0, 0) for i in range(30)
        ]
        stat = protocol.hourly_statistics(readings, start + timedelta(hours=1))[0]
        self.assertEqual(stat["min"], 10)
        self.assertEqual(stat["max"], 12.9)
        self.assertAlmostEqual(stat["mean"], 11.45)


if __name__ == "__main__":
    unittest.main()
