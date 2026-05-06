import os
import unittest
from unittest.mock import patch

from app import diagnostics


class NvmlDriverNotLoaded(Exception):
    pass


class FakeNvml:
    def __init__(self, gpu_count=1, fail_init=None):
        self.gpu_count = gpu_count
        self.fail_init = fail_init
        self.shutdown_called = False

    def nvmlInit(self):
        if self.fail_init:
            raise self.fail_init

    def nvmlShutdown(self):
        self.shutdown_called = True

    def nvmlDeviceGetCount(self):
        return self.gpu_count

    def nvmlSystemGetDriverVersion(self):
        return b"570.172.08"

    def nvmlSystemGetNVMLVersion(self):
        return b"12.570.172.08"


class DiagnosticsTests(unittest.TestCase):
    def test_diagnostics_reports_nvml_available(self):
        nvml = FakeNvml(gpu_count=4)

        result = diagnostics.get_diagnostics(nvml=nvml)

        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["nvml"]["available"])
        self.assertEqual(result["nvml"]["gpu_count"], 4)
        self.assertEqual(result["nvml"]["driver_version"], "570.172.08")
        self.assertIn("checks", result)
        self.assertIn("common_issues", result)
        self.assertTrue(
            any(check["label"] == "GPU visibility" for check in result["checks"])
        )
        self.assertTrue(nvml.shutdown_called)

    def test_diagnostics_reports_no_gpus(self):
        nvml = FakeNvml(gpu_count=0)

        result = diagnostics.get_diagnostics(nvml=nvml)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "no_gpus")
        self.assertEqual(result["errors"][0]["code"], "no_nvidia_gpus")
        self.assertTrue(
            any(check["level"] == "warning" for check in result["checks"])
        )
        self.assertTrue(nvml.shutdown_called)

    def test_diagnostics_reports_driver_error(self):
        nvml = FakeNvml(fail_init=NvmlDriverNotLoaded("Driver Not Loaded"))

        result = diagnostics.get_diagnostics(nvml=nvml)

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "nvml_error")
        self.assertEqual(result["errors"][0]["code"], "nvidia_driver_unavailable")
        self.assertTrue(
            any(check["label"] == "NVML" and check["level"] == "error" for check in result["checks"])
        )
        self.assertFalse(nvml.shutdown_called)

    def test_diagnostics_reports_missing_pynvml_package(self):
        with patch.dict(os.environ, {"DEMO_MODE": ""}), patch.object(
            diagnostics.gpu_collector,
            "pynvml",
            None,
        ):
            result = diagnostics.get_diagnostics()

        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "pynvml_unavailable")
        self.assertEqual(result["errors"][0]["code"], "pynvml_unavailable")


if __name__ == "__main__":
    unittest.main()
