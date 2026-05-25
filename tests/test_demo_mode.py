import os
import unittest
from unittest.mock import patch

from app import demo_data, diagnostics, gpu_collector, main, system_collector


class DemoModeTests(unittest.TestCase):
    def test_demo_snapshot_uses_existing_api_contract(self):
        snapshot = demo_data.get_demo_snapshot(now=1_700_000_000.0)

        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["status"], "demo")
        self.assertTrue(snapshot["demo_mode"])
        self.assertEqual(snapshot["mode"], "demo")
        self.assertEqual(snapshot["gpu_count"], 4)
        self.assertEqual(len(snapshot["gpus"]), 4)
        self.assertEqual(snapshot["errors"], [])
        self.assertTrue(snapshot["diagnostics"]["demo_mode"])

        gpu = snapshot["gpus"][0]
        self.assertIn("uuid", gpu)
        self.assertIn("utilization", gpu)
        self.assertIn("memory", gpu)
        self.assertIn("temperature_c", gpu)
        self.assertIn("power", gpu)
        self.assertIn("processes", gpu)
        self.assertGreater(gpu["memory"]["total_mib"], 0)
        self.assertGreater(snapshot["gpus"][0]["processes"]["count"], 0)
        self.assertTrue(snapshot["gpus"][2]["unavailable_metrics"])

    def test_demo_snapshot_changes_over_time(self):
        first = demo_data.get_demo_snapshot(now=1_700_000_000.0)
        second = demo_data.get_demo_snapshot(now=1_700_000_006.0)

        first_values = [
            gpu["utilization"]["gpu_percent"]
            for gpu in first["gpus"]
        ]
        second_values = [
            gpu["utilization"]["gpu_percent"]
            for gpu in second["gpus"]
        ]

        self.assertNotEqual(first_values, second_values)

    def test_demo_diagnostics_are_clearly_labeled(self):
        result = demo_data.get_demo_diagnostics(now=1_700_000_000.0)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "demo")
        self.assertTrue(result["demo_mode"])
        self.assertEqual(result["mode"], "demo")
        self.assertTrue(result["nvml"]["demo"])
        self.assertTrue(
            any(
                check["label"] == "Demo mode"
                and "synthetic" in check["message"].lower()
                for check in result["checks"]
            )
        )

    def test_demo_system_snapshot_uses_system_contract(self):
        first = demo_data.get_demo_system_snapshot(now=1_700_000_000.0)
        second = demo_data.get_demo_system_snapshot(now=1_700_000_006.0)

        self.assertTrue(first["ok"])
        self.assertEqual(first["status"], "demo")
        self.assertTrue(first["demo_mode"])
        self.assertIn("cpu", first)
        self.assertIn("memory", first)
        self.assertIn("swap", first)
        self.assertIn("load_average", first)
        self.assertTrue(first["cpu"]["temperature"]["available"])
        self.assertGreater(first["memory"]["total_gib"], first["memory"]["used_gib"])
        self.assertNotEqual(
            first["cpu"]["utilization_percent"],
            second["cpu"]["utilization_percent"],
        )

    def test_collector_uses_demo_mode_without_pynvml(self):
        with patch.dict(os.environ, {"DEMO_MODE": "1"}), patch.object(
            gpu_collector,
            "pynvml",
            None,
        ):
            snapshot = gpu_collector.get_gpu_snapshot()

        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["status"], "demo")
        self.assertEqual(snapshot["gpu_count"], 4)

    def test_diagnostics_uses_demo_mode_without_pynvml(self):
        with patch.dict(os.environ, {"DEMO_MODE": "1"}), patch.object(
            diagnostics.gpu_collector,
            "pynvml",
            None,
        ):
            result = diagnostics.get_diagnostics()

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "demo")
        self.assertTrue(result["demo_mode"])

    def test_api_endpoints_use_demo_mode(self):
        with patch.dict(os.environ, {"DEMO_MODE": "1"}):
            snapshot = main.api_snapshot()
            diagnostics_payload = main.api_diagnostics()
            system_payload = main.api_system()

        self.assertEqual(snapshot["status"], "demo")
        self.assertEqual(diagnostics_payload["status"], "demo")
        self.assertTrue(diagnostics_payload["demo_mode"])
        self.assertEqual(system_payload["status"], "demo")
        self.assertTrue(system_payload["demo_mode"])

    def test_system_collector_uses_demo_mode(self):
        with patch.dict(os.environ, {"DEMO_MODE": "1"}):
            system_payload = system_collector.get_system_snapshot()

        self.assertTrue(system_payload["ok"])
        self.assertEqual(system_payload["status"], "demo")
        self.assertTrue(system_payload["demo_mode"])


if __name__ == "__main__":
    unittest.main()
