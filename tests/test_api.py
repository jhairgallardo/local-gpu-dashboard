import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.responses import FileResponse

from app import CURRENT_PHASE, SERVICE_NAME, __version__
from app import main


class ApiTests(unittest.TestCase):
    def test_expected_routes_are_registered(self):
        paths = {route.path for route in main.app.routes}

        self.assertIn("/", paths)
        self.assertIn("/health", paths)
        self.assertIn("/api/snapshot", paths)
        self.assertIn("/api/diagnostics", paths)
        self.assertIn("/static", paths)

    def test_health_response(self):
        self.assertEqual(
            main.health(),
            {
                "status": "ok",
                "service": SERVICE_NAME,
                "version": __version__,
                "phase": CURRENT_PHASE,
            },
        )

    def test_fastapi_version_matches_package_version(self):
        self.assertEqual(main.app.version, __version__)

    def test_index_serves_static_html(self):
        response = main.read_index()

        self.assertIsInstance(response, FileResponse)
        self.assertEqual(Path(response.path).name, "index.html")
        self.assertTrue(Path(response.path).exists())

    def test_snapshot_endpoint_uses_collector(self):
        snapshot = {
            "ok": True,
            "status": "ok",
            "timestamp": "2026-05-05T00:00:00Z",
            "gpu_count": 0,
            "gpus": [],
            "errors": [],
        }

        with patch.object(main, "get_gpu_snapshot", return_value=snapshot):
            self.assertEqual(main.api_snapshot(), snapshot)

    def test_snapshot_endpoint_returns_collector_errors(self):
        snapshot = {
            "ok": False,
            "status": "error",
            "timestamp": "2026-05-05T00:00:00Z",
            "gpu_count": 0,
            "gpus": [],
            "errors": [
                {
                    "code": "nvml_library_missing",
                    "message": "The NVIDIA Management Library could not be loaded.",
                }
            ],
        }

        with patch.object(main, "get_gpu_snapshot", return_value=snapshot):
            response = main.api_snapshot()

        self.assertFalse(response["ok"])
        self.assertEqual(response["errors"][0]["code"], "nvml_library_missing")

    def test_diagnostics_endpoint_uses_diagnostics_helper(self):
        diagnostics = {
            "ok": True,
            "status": "ok",
            "timestamp": "2026-05-05T00:00:00Z",
            "nvidia_smi": {"available": True, "path": "/usr/bin/nvidia-smi"},
            "nvml": {
                "available": True,
                "driver_version": "570.172.08",
                "nvml_version": "12.570.172.08",
                "gpu_count": 4,
            },
            "errors": [],
        }

        with patch.object(main, "get_diagnostics", return_value=diagnostics):
            self.assertEqual(main.api_diagnostics(), diagnostics)

    def test_diagnostics_endpoint_returns_unavailable_nvml_errors(self):
        diagnostics = {
            "ok": False,
            "status": "pynvml_unavailable",
            "timestamp": "2026-05-05T00:00:00Z",
            "nvidia_smi": {"available": False, "path": None},
            "nvml": {
                "available": False,
                "driver_version": None,
                "nvml_version": None,
                "gpu_count": None,
            },
            "checks": [
                {
                    "label": "NVML",
                    "level": "error",
                    "message": "NVML could not be initialized by the dashboard process.",
                }
            ],
            "errors": [
                {
                    "code": "pynvml_unavailable",
                    "message": "The nvidia-ml-py package could not be imported.",
                }
            ],
        }

        with patch.object(main, "get_diagnostics", return_value=diagnostics):
            response = main.api_diagnostics()

        self.assertFalse(response["ok"])
        self.assertEqual(response["status"], "pynvml_unavailable")
        self.assertEqual(response["errors"][0]["code"], "pynvml_unavailable")


if __name__ == "__main__":
    unittest.main()
