import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app import gpu_collector


class NvmlNotSupported(Exception):
    pass


class NvmlDriverNotLoaded(Exception):
    pass


class NvmlLibraryNotFound(Exception):
    pass


class FakeNvml:
    NVML_TEMPERATURE_GPU = 0
    NVML_CLOCK_GRAPHICS = 1
    NVML_CLOCK_MEM = 2
    NVML_VALUE_NOT_AVAILABLE = 18446744073709551615

    def __init__(
        self,
        gpu_count=1,
        fail_init=None,
        unsupported=None,
        compute_processes=None,
        graphics_processes=None,
    ):
        self.gpu_count = gpu_count
        self.fail_init = fail_init
        self.unsupported = set(unsupported or [])
        self.compute_processes = compute_processes or []
        self.graphics_processes = graphics_processes or []
        self.shutdown_called = False

    def nvmlInit(self):
        if self.fail_init:
            raise self.fail_init

    def nvmlShutdown(self):
        self.shutdown_called = True

    def nvmlDeviceGetCount(self):
        return self.gpu_count

    def nvmlDeviceGetHandleByIndex(self, index):
        return "gpu-{}".format(index)

    def nvmlDeviceGetUUID(self, handle):
        return b"GPU-fake-uuid"

    def nvmlDeviceGetName(self, handle):
        return b"NVIDIA Test GPU"

    def nvmlDeviceGetUtilizationRates(self, handle):
        if "utilization" in self.unsupported:
            raise NvmlNotSupported("Not Supported")
        return SimpleNamespace(gpu=72, memory=31)

    def nvmlDeviceGetMemoryInfo(self, handle):
        if "memory" in self.unsupported:
            raise NvmlNotSupported("Not Supported")
        return SimpleNamespace(
            used=4 * gpu_collector.BYTES_PER_MIB,
            total=16 * gpu_collector.BYTES_PER_MIB,
            free=12 * gpu_collector.BYTES_PER_MIB,
        )

    def nvmlDeviceGetTemperature(self, handle, sensor):
        if "temperature" in self.unsupported:
            raise NvmlNotSupported("Not Supported")
        return 64

    def nvmlDeviceGetPowerUsage(self, handle):
        if "power_draw" in self.unsupported:
            raise NvmlNotSupported("Not Supported")
        return 125500

    def nvmlDeviceGetPowerManagementLimit(self, handle):
        if "power_limit" in self.unsupported:
            raise NvmlNotSupported("Not Supported")
        return 250000

    def nvmlDeviceGetFanSpeed(self, handle):
        if "fan_speed" in self.unsupported:
            raise NvmlNotSupported("Not Supported")
        return 45

    def nvmlDeviceGetClockInfo(self, handle, clock_type):
        if (
            clock_type == self.NVML_CLOCK_GRAPHICS
            and "graphics_clock" in self.unsupported
        ):
            raise NvmlNotSupported("Not Supported")
        if (
            clock_type == self.NVML_CLOCK_MEM
            and "memory_clock" in self.unsupported
        ):
            raise NvmlNotSupported("Not Supported")
        if clock_type == self.NVML_CLOCK_GRAPHICS:
            return 1800
        return 9501

    def nvmlDeviceGetComputeRunningProcesses(self, handle):
        if "compute_processes" in self.unsupported:
            raise NvmlNotSupported("Not Supported")
        return self.compute_processes

    def nvmlDeviceGetGraphicsRunningProcesses(self, handle):
        if "graphics_processes" in self.unsupported:
            raise NvmlNotSupported("Not Supported")
        return self.graphics_processes

    def nvmlSystemGetDriverVersion(self):
        return b"555.55"

    def nvmlSystemGetNVMLVersion(self):
        return b"12.555"


class GpuCollectorTests(unittest.TestCase):
    def test_collects_gpu_snapshot(self):
        nvml = FakeNvml()

        snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        self.assertTrue(snapshot["ok"])
        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["gpu_count"], 1)
        self.assertEqual(snapshot["errors"], [])
        self.assertTrue(nvml.shutdown_called)

        gpu = snapshot["gpus"][0]
        self.assertEqual(gpu["index"], 0)
        self.assertEqual(gpu["uuid"], "GPU-fake-uuid")
        self.assertEqual(gpu["name"], "NVIDIA Test GPU")
        self.assertEqual(gpu["utilization"]["gpu_percent"], 72)
        self.assertEqual(gpu["memory"]["used_mib"], 4.0)
        self.assertEqual(gpu["memory"]["total_mib"], 16.0)
        self.assertEqual(gpu["memory"]["percent"], 25.0)
        self.assertEqual(gpu["temperature_c"], 64)
        self.assertEqual(gpu["power"]["draw_watts"], 125.5)
        self.assertEqual(gpu["power"]["limit_watts"], 250.0)
        self.assertEqual(gpu["fan_speed_percent"], 45)
        self.assertEqual(gpu["clocks"]["graphics_mhz"], 1800)
        self.assertEqual(gpu["clocks"]["memory_mhz"], 9501)
        self.assertEqual(gpu["processes"]["count"], 0)

    def test_collects_gpu_processes_with_psutil_details(self):
        nvml = FakeNvml(
            compute_processes=[
                SimpleNamespace(
                    pid=123,
                    usedGpuMemory=3 * gpu_collector.BYTES_PER_MIB,
                )
            ],
            graphics_processes=[
                SimpleNamespace(
                    pid=456,
                    usedGpuMemory=FakeNvml.NVML_VALUE_NOT_AVAILABLE,
                )
            ],
        )

        class FakeProcess:
            def __init__(self, pid):
                self.pid = pid

            def name(self):
                return "python" if self.pid == 123 else "Xorg"

            def username(self):
                return "jhair"

            def status(self):
                return "running"

            def cmdline(self):
                return ["python", "train.py"] if self.pid == 123 else ["Xorg"]

        with patch.object(gpu_collector.psutil, "Process", side_effect=FakeProcess):
            snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        processes = snapshot["gpus"][0]["processes"]
        self.assertEqual(processes["count"], 2)
        self.assertEqual(processes["unavailable_sources"], [])

        first = processes["items"][0]
        self.assertEqual(first["pid"], 123)
        self.assertEqual(first["types"], ["compute"])
        self.assertEqual(first["gpu_memory_mib"], 3.0)
        self.assertEqual(first["name"], "python")
        self.assertEqual(first["username"], "jhair")
        self.assertEqual(first["status"], "running")
        self.assertEqual(first["command_line"], "python train.py")

        second = processes["items"][1]
        self.assertEqual(second["pid"], 456)
        self.assertEqual(second["types"], ["graphics"])
        self.assertIsNone(second["gpu_memory_mib"])

    def test_process_command_lines_and_usernames_can_be_redacted(self):
        nvml = FakeNvml(
            compute_processes=[
                SimpleNamespace(
                    pid=123,
                    usedGpuMemory=3 * gpu_collector.BYTES_PER_MIB,
                )
            ],
        )

        class FakeProcess:
            def __init__(self, pid):
                self.pid = pid

            def name(self):
                return "python"

            def username(self):
                return "jhair"

            def status(self):
                return "running"

            def cmdline(self):
                return ["python", "train.py"]

        env = {
            "SHOW_PROCESS_DETAILS": "1",
            "SHOW_COMMAND_LINES": "0",
            "SHOW_USERNAMES": "0",
        }
        with patch.dict(os.environ, env), patch.object(
            gpu_collector.psutil,
            "Process",
            side_effect=FakeProcess,
        ):
            snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        processes = snapshot["gpus"][0]["processes"]
        process = processes["items"][0]
        self.assertTrue(processes["redacted"])
        self.assertEqual(processes["redacted_fields"], ["command_line", "username"])
        self.assertIsNone(process["command_line"])
        self.assertIsNone(process["username"])
        self.assertEqual(process["redacted_fields"], ["command_line", "username"])

    def test_process_detail_permission_errors_do_not_crash(self):
        nvml = FakeNvml(
            compute_processes=[
                SimpleNamespace(pid=123, usedGpuMemory=gpu_collector.BYTES_PER_MIB)
            ]
        )

        class RestrictedProcess:
            def __init__(self, pid):
                self.pid = pid

            def name(self):
                return "python"

            def username(self):
                raise gpu_collector.psutil.AccessDenied(pid=self.pid)

            def status(self):
                return "running"

            def cmdline(self):
                raise gpu_collector.psutil.AccessDenied(pid=self.pid)

        with patch.object(
            gpu_collector.psutil,
            "Process",
            side_effect=RestrictedProcess,
        ):
            snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        process = snapshot["gpus"][0]["processes"]["items"][0]
        self.assertEqual(process["name"], "python")
        self.assertIsNone(process["username"])
        self.assertIsNone(process["command_line"])
        unavailable_fields = {
            detail["field"] for detail in process["detail_unavailable"]
        }
        self.assertEqual(unavailable_fields, {"username", "command_line"})

    def test_disappearing_process_is_marked_unavailable(self):
        nvml = FakeNvml(
            compute_processes=[
                SimpleNamespace(pid=123, usedGpuMemory=gpu_collector.BYTES_PER_MIB)
            ]
        )

        with patch.object(
            gpu_collector.psutil,
            "Process",
            side_effect=gpu_collector.psutil.NoSuchProcess(pid=123),
        ):
            snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        process = snapshot["gpus"][0]["processes"]["items"][0]
        self.assertEqual(process["pid"], 123)
        self.assertIsNone(process["name"])
        self.assertEqual(
            process["detail_unavailable"],
            [
                {
                    "field": "process",
                    "reason": "Process exited before details could be read.",
                }
            ],
        )

    def test_unsupported_process_queries_are_reported(self):
        nvml = FakeNvml(unsupported={"graphics_processes"})

        snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        processes = snapshot["gpus"][0]["processes"]
        self.assertEqual(processes["count"], 0)
        self.assertEqual(
            processes["unavailable_sources"][0]["metric"],
            "graphics_processes",
        )

    def test_unsupported_optional_metric_returns_none(self):
        nvml = FakeNvml(
            unsupported={
                "fan_speed",
                "graphics_clock",
                "memory",
                "memory_clock",
                "power_draw",
                "power_limit",
                "temperature",
                "utilization",
            }
        )

        snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        self.assertTrue(snapshot["ok"])
        gpu = snapshot["gpus"][0]
        self.assertIsNone(gpu["memory"]["used_mib"])
        self.assertIsNone(gpu["utilization"]["gpu_percent"])
        self.assertIsNone(gpu["temperature_c"])
        self.assertIsNone(gpu["power"]["draw_watts"])
        self.assertIsNone(gpu["power"]["limit_watts"])
        self.assertIsNone(gpu["fan_speed_percent"])
        self.assertIsNone(gpu["clocks"]["graphics_mhz"])
        self.assertIsNone(gpu["clocks"]["memory_mhz"])
        unavailable_metrics = {
            metric["metric"] for metric in gpu["unavailable_metrics"]
        }
        self.assertEqual(
            unavailable_metrics,
            {
                "fan_speed",
                "graphics_clock",
                "memory",
                "memory_clock",
                "power_draw",
                "power_limit",
                "temperature",
                "utilization",
            },
        )

    def test_no_gpus_returns_diagnostic_error(self):
        nvml = FakeNvml(gpu_count=0)

        snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        self.assertFalse(snapshot["ok"])
        self.assertEqual(snapshot["status"], "no_gpus")
        self.assertEqual(snapshot["gpu_count"], 0)
        self.assertEqual(snapshot["errors"][0]["code"], "no_nvidia_gpus")
        self.assertTrue(nvml.shutdown_called)

    def test_driver_not_loaded_returns_clear_error(self):
        nvml = FakeNvml(fail_init=NvmlDriverNotLoaded("Driver Not Loaded"))

        snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        self.assertFalse(snapshot["ok"])
        self.assertEqual(snapshot["errors"][0]["code"], "nvidia_driver_unavailable")
        self.assertFalse(nvml.shutdown_called)

    def test_missing_nvml_library_returns_clear_error(self):
        nvml = FakeNvml(fail_init=NvmlLibraryNotFound("NVML Shared Library Not Found"))

        snapshot = gpu_collector.get_gpu_snapshot(nvml=nvml)

        self.assertFalse(snapshot["ok"])
        self.assertEqual(snapshot["errors"][0]["code"], "nvml_library_missing")
        self.assertFalse(nvml.shutdown_called)

    def test_missing_pynvml_package_returns_clear_error(self):
        with patch.dict(os.environ, {"DEMO_MODE": ""}), patch.object(
            gpu_collector,
            "pynvml",
            None,
        ):
            snapshot = gpu_collector.get_gpu_snapshot()

        self.assertFalse(snapshot["ok"])
        self.assertEqual(snapshot["errors"][0]["code"], "pynvml_unavailable")


if __name__ == "__main__":
    unittest.main()
