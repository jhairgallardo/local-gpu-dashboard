import unittest
from collections import namedtuple
from unittest.mock import patch

from app import system_collector

Temp = namedtuple("Temp", "label current high critical")
Freq = namedtuple("Freq", "current min max")
Memory = namedtuple("Memory", "total available used free percent")


class SystemCollectorTests(unittest.TestCase):
    def test_selects_cpu_temperature_and_ignores_non_cpu_sensors(self):
        sensors = {
            "enp69s0": [Temp("PHY Temperature", 65.3, None, None)],
            "k10temp": [
                Temp("Tctl", 59.0, None, None),
                Temp("Tdie", 58.5, 70.0, 70.0),
            ],
        }

        selected_name, selected_entry = system_collector._select_cpu_temperature(sensors)

        self.assertEqual(selected_name, "k10temp")
        self.assertEqual(selected_entry.label, "Tdie")

    def test_unavailable_temperature_has_clear_reason(self):
        errors = []

        with patch.object(system_collector.psutil, "sensors_temperatures", return_value={}):
            payload = system_collector._cpu_temperature_payload(errors)

        self.assertFalse(payload["available"])
        self.assertIsNone(payload["current_c"])
        self.assertIn("No CPU-specific thermal sensor", payload["reason"])
        self.assertEqual(errors, [])

    def test_system_snapshot_uses_psutil_without_nvidia(self):
        with patch.object(system_collector.psutil, "cpu_percent", side_effect=[25.0, [20.0, 30.0]]), \
            patch.object(system_collector.psutil, "cpu_count", side_effect=[8, 4]), \
            patch.object(system_collector.psutil, "cpu_freq", return_value=Freq(3200.0, 800.0, 5200.0)), \
            patch.object(
                system_collector.psutil,
                "sensors_temperatures",
                return_value={"k10temp": [Temp("Tdie", 56.5, 70.0, 70.0)]},
            ), \
            patch.object(
                system_collector.psutil,
                "virtual_memory",
                return_value=Memory(32 * 1024 ** 3, 20 * 1024 ** 3, 12 * 1024 ** 3, 18 * 1024 ** 3, 37.5),
            ), \
            patch.object(
                system_collector.psutil,
                "swap_memory",
                return_value=Memory(8 * 1024 ** 3, 7 * 1024 ** 3, 1 * 1024 ** 3, 7 * 1024 ** 3, 12.5),
            ), \
            patch.object(system_collector.psutil, "getloadavg", return_value=(1.1, 1.2, 1.3)), \
            patch.object(system_collector.psutil, "boot_time", return_value=1_699_999_000.0):
            snapshot = system_collector.get_system_snapshot(now=1_700_000_000.0)

        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["status"], "ok")
        self.assertFalse(snapshot["demo_mode"])
        self.assertEqual(snapshot["cpu"]["utilization_percent"], 25.0)
        self.assertEqual(snapshot["cpu"]["per_core_percent"], [20.0, 30.0])
        self.assertEqual(snapshot["cpu"]["temperature"]["sensor"], "k10temp")
        self.assertEqual(snapshot["cpu"]["temperature"]["label"], "Tdie")
        self.assertEqual(snapshot["memory"]["used_gib"], 12.0)
        self.assertEqual(snapshot["swap"]["used_gib"], 1.0)
        self.assertEqual(snapshot["load_average"]["one_min"], 1.1)
        self.assertEqual(snapshot["uptime"]["seconds"], 1000)

    def test_system_snapshot_is_partial_without_cpu_temperature(self):
        with patch.object(system_collector.psutil, "cpu_percent", side_effect=[5.0, [5.0]]), \
            patch.object(system_collector.psutil, "cpu_count", side_effect=[1, 1]), \
            patch.object(system_collector.psutil, "cpu_freq", return_value=None), \
            patch.object(system_collector.psutil, "sensors_temperatures", return_value={}), \
            patch.object(
                system_collector.psutil,
                "virtual_memory",
                return_value=Memory(4 * 1024 ** 3, 3 * 1024 ** 3, 1 * 1024 ** 3, 3 * 1024 ** 3, 25.0),
            ), \
            patch.object(
                system_collector.psutil,
                "swap_memory",
                return_value=Memory(0, 0, 0, 0, 0.0),
            ), \
            patch.object(system_collector.psutil, "getloadavg", return_value=(0.1, 0.2, 0.3)), \
            patch.object(system_collector.psutil, "boot_time", return_value=1_699_999_990.0):
            snapshot = system_collector.get_system_snapshot(now=1_700_000_000.0)

        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["status"], "partial")
        self.assertFalse(snapshot["cpu"]["temperature"]["available"])
        self.assertIn("No CPU-specific thermal sensor", snapshot["cpu"]["temperature"]["reason"])


if __name__ == "__main__":
    unittest.main()
