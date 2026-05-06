"""NVML-backed NVIDIA GPU data collection."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import psutil

from app import demo_data
from app import runtime_config

try:
    import pynvml
except Exception as exc:  # pragma: no cover - exercised by injecting None in tests
    pynvml = None
    _PYNVML_IMPORT_ERROR = exc
else:
    _PYNVML_IMPORT_ERROR = None

BYTES_PER_MIB = 1024 * 1024
MILLIWATTS_PER_WATT = 1000.0


def get_gpu_snapshot(nvml: Optional[Any] = None) -> Dict[str, Any]:
    """Return a JSON-friendly snapshot of all NVIDIA GPUs visible to NVML."""

    if nvml is None and demo_data.demo_mode_enabled():
        return demo_data.get_demo_snapshot()

    nvml_module = pynvml if nvml is None else nvml
    timestamp = _utc_timestamp()

    if nvml_module is None:
        return _error_snapshot(
            timestamp,
            _make_error(
                "pynvml_unavailable",
                "The nvidia-ml-py package could not be imported.",
                detail=str(_PYNVML_IMPORT_ERROR) if _PYNVML_IMPORT_ERROR else None,
                hint="Run ./run_dashboard.sh to install dependencies, then try again.",
            ),
        )

    initialized = False
    try:
        nvml_module.nvmlInit()
        initialized = True
        gpu_count = int(nvml_module.nvmlDeviceGetCount())

        if gpu_count == 0:
            return {
                "ok": False,
                "status": "no_gpus",
                "timestamp": timestamp,
                "gpu_count": 0,
                "gpus": [],
                "errors": [
                    _make_error(
                        "no_nvidia_gpus",
                        "NVML initialized, but no NVIDIA GPUs were detected.",
                        hint="Confirm the machine has NVIDIA GPUs visible to the current user.",
                    )
                ],
                "diagnostics": _diagnostics(nvml_module, 0),
            }

        privacy_config = runtime_config.get_privacy_config()
        gpus = [
            _collect_gpu(nvml_module, index, privacy_config)
            for index in range(gpu_count)
        ]

        return {
            "ok": True,
            "status": "ok",
            "timestamp": timestamp,
            "gpu_count": gpu_count,
            "gpus": gpus,
            "errors": [],
            "diagnostics": _diagnostics(nvml_module, gpu_count),
        }
    except Exception as exc:
        return _error_snapshot(
            timestamp,
            _error_from_exception(exc),
        )
    finally:
        if initialized:
            try:
                nvml_module.nvmlShutdown()
            except Exception:
                pass


def _collect_gpu(
    nvml_module: Any,
    index: int,
    privacy_config: Optional[Dict[str, bool]],
) -> Dict[str, Any]:
    handle = nvml_module.nvmlDeviceGetHandleByIndex(index)
    unavailable: List[Dict[str, str]] = []

    memory_info = _optional(
        lambda: nvml_module.nvmlDeviceGetMemoryInfo(handle),
        "memory",
        unavailable,
    )
    utilization = _optional(
        lambda: nvml_module.nvmlDeviceGetUtilizationRates(handle),
        "utilization",
        unavailable,
    )
    power_draw_mw = _optional(
        lambda: nvml_module.nvmlDeviceGetPowerUsage(handle),
        "power_draw",
        unavailable,
    )
    power_limit_mw = _optional(
        lambda: nvml_module.nvmlDeviceGetPowerManagementLimit(handle),
        "power_limit",
        unavailable,
    )

    return {
        "index": index,
        "uuid": _optional_text(
            lambda: nvml_module.nvmlDeviceGetUUID(handle),
            "uuid",
            unavailable,
        ),
        "name": _optional_text(
            lambda: nvml_module.nvmlDeviceGetName(handle),
            "name",
            unavailable,
        ),
        "utilization": {
            "gpu_percent": _attr_or_none(utilization, "gpu"),
            "memory_percent": _attr_or_none(utilization, "memory"),
        },
        "memory": _memory_payload(memory_info),
        "temperature_c": _optional(
            lambda: nvml_module.nvmlDeviceGetTemperature(
                handle,
                nvml_module.NVML_TEMPERATURE_GPU,
            ),
            "temperature",
            unavailable,
        ),
        "power": {
            "draw_watts": _milliwatts_to_watts(power_draw_mw),
            "limit_watts": _milliwatts_to_watts(power_limit_mw),
        },
        "fan_speed_percent": _optional(
            lambda: nvml_module.nvmlDeviceGetFanSpeed(handle),
            "fan_speed",
            unavailable,
        ),
        "clocks": {
            "graphics_mhz": _optional(
                lambda: nvml_module.nvmlDeviceGetClockInfo(
                    handle,
                    nvml_module.NVML_CLOCK_GRAPHICS,
                ),
                "graphics_clock",
                unavailable,
            ),
            "memory_mhz": _optional(
                lambda: nvml_module.nvmlDeviceGetClockInfo(
                    handle,
                    nvml_module.NVML_CLOCK_MEM,
                ),
                "memory_clock",
                unavailable,
            ),
        },
        "processes": runtime_config.apply_process_privacy(
            _process_payload(nvml_module, handle),
            privacy_config,
        ),
        "unavailable_metrics": unavailable,
    }


def _process_payload(nvml_module: Any, handle: Any) -> Dict[str, Any]:
    unavailable_sources: List[Dict[str, str]] = []
    records: Dict[int, Dict[str, Any]] = {}

    for process_type, function_name, metric in (
        ("compute", "nvmlDeviceGetComputeRunningProcesses", "compute_processes"),
        ("graphics", "nvmlDeviceGetGraphicsRunningProcesses", "graphics_processes"),
    ):
        for process_info in _process_infos(
            nvml_module,
            handle,
            function_name,
            metric,
            unavailable_sources,
        ):
            pid = _attr_or_none(process_info, "pid")
            if pid is None:
                continue

            record = records.setdefault(
                pid,
                {
                    "pid": pid,
                    "types": [],
                    "gpu_memory_bytes": None,
                    "gpu_memory_mib": None,
                    "gpu_instance_id": _attr_or_none(process_info, "gpuInstanceId"),
                    "compute_instance_id": _attr_or_none(
                        process_info,
                        "computeInstanceId",
                    ),
                    "name": None,
                    "username": None,
                    "status": None,
                    "command_line": None,
                    "detail_unavailable": [],
                },
            )

            if process_type not in record["types"]:
                record["types"].append(process_type)

            used_memory = _gpu_process_memory_bytes(
                nvml_module,
                getattr(process_info, "usedGpuMemory", None),
            )
            if used_memory is not None and (
                record["gpu_memory_bytes"] is None
                or used_memory > record["gpu_memory_bytes"]
            ):
                record["gpu_memory_bytes"] = used_memory
                record["gpu_memory_mib"] = _bytes_to_mib(used_memory)

    items = [_enrich_process_record(record) for record in records.values()]
    items.sort(key=lambda process: process["pid"])

    return {
        "count": len(items),
        "items": items,
        "unavailable_sources": unavailable_sources,
    }


def _process_infos(
    nvml_module: Any,
    handle: Any,
    function_name: str,
    metric: str,
    unavailable_sources: List[Dict[str, str]],
) -> List[Any]:
    function = getattr(nvml_module, function_name, None)
    if function is None:
        unavailable_sources.append(
            {
                "metric": metric,
                "reason": "NVML process query is unavailable in this environment.",
            }
        )
        return []

    try:
        return list(function(handle) or [])
    except Exception as exc:
        unavailable_sources.append(
            {
                "metric": metric,
                "reason": _exception_summary(exc),
            }
        )
        return []


def _enrich_process_record(record: Dict[str, Any]) -> Dict[str, Any]:
    pid = record["pid"]

    try:
        process = psutil.Process(pid)
    except (psutil.NoSuchProcess, psutil.ZombieProcess) as exc:
        record["detail_unavailable"].append(
            {
                "field": "process",
                "reason": _process_exception_reason(exc),
            }
        )
        return record
    except psutil.AccessDenied as exc:
        record["detail_unavailable"].append(
            {
                "field": "process",
                "reason": _process_exception_reason(exc),
            }
        )
        return record

    record["name"] = _process_field(
        lambda: process.name(),
        "name",
        record["detail_unavailable"],
    )
    record["username"] = _process_field(
        lambda: process.username(),
        "username",
        record["detail_unavailable"],
    )
    record["status"] = _process_field(
        lambda: process.status(),
        "status",
        record["detail_unavailable"],
    )

    cmdline = _process_field(
        lambda: process.cmdline(),
        "command_line",
        record["detail_unavailable"],
    )
    if cmdline:
        record["command_line"] = " ".join(str(part) for part in cmdline)

    return record


def _process_field(
    getter: Callable[[], Any],
    field: str,
    detail_unavailable: List[Dict[str, str]],
) -> Optional[Any]:
    try:
        return getter()
    except (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied) as exc:
        detail_unavailable.append(
            {
                "field": field,
                "reason": _process_exception_reason(exc),
            }
        )
        return None


def _process_exception_reason(exc: Exception) -> str:
    if isinstance(exc, psutil.AccessDenied):
        return "Permission denied while reading process details."
    if isinstance(exc, (psutil.NoSuchProcess, psutil.ZombieProcess)):
        return "Process exited before details could be read."
    return _exception_summary(exc)


def _gpu_process_memory_bytes(nvml_module: Any, value: Optional[Any]) -> Optional[int]:
    if value is None:
        return None

    try:
        used = int(value)
    except (TypeError, ValueError):
        return None

    unavailable_value = getattr(nvml_module, "NVML_VALUE_NOT_AVAILABLE", None)
    if unavailable_value is not None:
        try:
            if used == int(unavailable_value):
                return None
        except (TypeError, ValueError):
            pass

    return used if used >= 0 else None


def _memory_payload(memory_info: Optional[Any]) -> Dict[str, Optional[float]]:
    if memory_info is None:
        return {
            "used_bytes": None,
            "total_bytes": None,
            "free_bytes": None,
            "used_mib": None,
            "total_mib": None,
            "free_mib": None,
            "percent": None,
        }

    used = int(memory_info.used)
    total = int(memory_info.total)
    free = int(memory_info.free)

    return {
        "used_bytes": used,
        "total_bytes": total,
        "free_bytes": free,
        "used_mib": _bytes_to_mib(used),
        "total_mib": _bytes_to_mib(total),
        "free_mib": _bytes_to_mib(free),
        "percent": round((used / total) * 100, 1) if total else None,
    }


def _optional(
    getter: Callable[[], Any],
    metric: str,
    unavailable: List[Dict[str, str]],
) -> Optional[Any]:
    try:
        return getter()
    except Exception as exc:
        unavailable.append(
            {
                "metric": metric,
                "reason": _exception_summary(exc),
            }
        )
        return None


def _optional_text(
    getter: Callable[[], Any],
    metric: str,
    unavailable: List[Dict[str, str]],
) -> Optional[str]:
    value = _optional(getter, metric, unavailable)
    if value is None:
        return None
    return _decode_text(value)


def _diagnostics(nvml_module: Any, gpu_count: int) -> Dict[str, Any]:
    driver_version = _decode_text(
        _safe_system_value(nvml_module, "nvmlSystemGetDriverVersion")
    )
    nvml_version = _decode_text(
        _safe_system_value(nvml_module, "nvmlSystemGetNVMLVersion")
    )
    nvidia_smi_path = shutil.which("nvidia-smi")

    return {
        "driver_version": driver_version,
        "nvml_version": nvml_version,
        "nvidia_smi_path": nvidia_smi_path,
        "nvidia_smi": {
            "available": nvidia_smi_path is not None,
            "path": nvidia_smi_path,
        },
        "nvml": {
            "available": True,
            "driver_version": driver_version,
            "nvml_version": nvml_version,
            "gpu_count": gpu_count,
        },
        "checks": _diagnostic_checks(
            nvml_available=True,
            driver_version=driver_version,
            nvidia_smi_path=nvidia_smi_path,
            gpu_count=gpu_count,
        ),
        "common_issues": _common_issues(),
        "runtime_config": runtime_config.get_runtime_config(),
    }


def _safe_system_value(nvml_module: Any, function_name: str) -> Optional[Any]:
    function = getattr(nvml_module, function_name, None)
    if function is None:
        return None
    try:
        return function()
    except Exception:
        return None


def _error_snapshot(
    timestamp: str,
    error: Dict[str, Any],
    gpu_count: int = 0,
    status: str = "error",
) -> Dict[str, Any]:
    nvidia_smi_path = shutil.which("nvidia-smi")

    return {
        "ok": False,
        "status": status,
        "timestamp": timestamp,
        "gpu_count": gpu_count,
        "gpus": [],
        "errors": [error],
        "diagnostics": {
            "nvidia_smi_path": nvidia_smi_path,
            "nvidia_smi": {
                "available": nvidia_smi_path is not None,
                "path": nvidia_smi_path,
            },
            "nvml": {
                "available": False,
                "driver_version": None,
                "nvml_version": None,
                "gpu_count": gpu_count,
            },
            "checks": _diagnostic_checks(
                nvml_available=False,
                driver_version=None,
                nvidia_smi_path=nvidia_smi_path,
                gpu_count=gpu_count,
            ),
            "common_issues": _common_issues(),
            "runtime_config": runtime_config.get_runtime_config(),
        },
    }


def _diagnostic_checks(
    nvml_available: bool,
    driver_version: Optional[str],
    nvidia_smi_path: Optional[str],
    gpu_count: Optional[int],
) -> List[Dict[str, str]]:
    checks = [
        {
            "label": "NVML",
            "level": "ok" if nvml_available else "error",
            "message": (
                "NVML initialized successfully."
                if nvml_available
                else "NVML could not be initialized by the dashboard process."
            ),
        },
        {
            "label": "NVIDIA driver",
            "level": "ok" if driver_version else "warning",
            "message": (
                "Driver version {} detected.".format(driver_version)
                if driver_version
                else "Driver version could not be read from NVML."
            ),
        },
        {
            "label": "nvidia-smi",
            "level": "ok" if nvidia_smi_path else "warning",
            "message": (
                "nvidia-smi found at {}.".format(nvidia_smi_path)
                if nvidia_smi_path
                else "nvidia-smi was not found on PATH; NVML data may still work."
            ),
        },
    ]

    if nvml_available and gpu_count == 0:
        checks.append(
            {
                "label": "GPU visibility",
                "level": "warning",
                "message": "NVML is available, but no NVIDIA GPUs were detected.",
            }
        )
    elif nvml_available and gpu_count is not None:
        checks.append(
            {
                "label": "GPU visibility",
                "level": "ok",
                "message": "{} NVIDIA GPU(s) visible to NVML.".format(gpu_count),
            }
        )

    checks.append(
        {
            "label": "Privacy controls",
            "level": "ok",
            "message": runtime_config.privacy_summary(),
        }
    )

    return checks


def _common_issues() -> List[str]:
    return [
        "NVIDIA driver is not installed, not loaded, or incompatible with the running kernel.",
        "The current user or container does not have permission to access NVIDIA device files.",
        "nvidia-smi is missing from PATH even though NVML may be installed.",
        "GPU process command lines can be hidden by Linux permissions for other users.",
    ]


def _error_from_exception(exc: Exception) -> Dict[str, Any]:
    exception_name = type(exc).__name__
    exception_text = _exception_summary(exc)
    lowered = "{} {}".format(exception_name, exception_text).lower()

    if "librarynotfound" in lowered or "shared library" in lowered:
        return _make_error(
            "nvml_library_missing",
            "The NVIDIA Management Library could not be loaded.",
            detail=exception_text,
            hint="Install or repair the NVIDIA driver so libnvidia-ml is available.",
        )

    if "drivernotloaded" in lowered or "driver not loaded" in lowered:
        return _make_error(
            "nvidia_driver_unavailable",
            "The NVIDIA driver is not loaded or is unavailable to this process.",
            detail=exception_text,
            hint="Check the NVIDIA driver installation and confirm nvidia-smi works.",
        )

    if "nopermission" in lowered or "permission" in lowered:
        return _make_error(
            "nvml_permission_denied",
            "NVML denied access to GPU information.",
            detail=exception_text,
            hint="Run the dashboard as a user with permission to query NVIDIA GPU state.",
        )

    return _make_error(
        "nvml_error",
        "NVML failed while collecting GPU information.",
        detail=exception_text,
        hint="Run nvidia-smi to compare driver and GPU availability.",
    )


def _make_error(
    code: str,
    message: str,
    detail: Optional[str] = None,
    hint: Optional[str] = None,
) -> Dict[str, Any]:
    error: Dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if detail:
        error["detail"] = detail
    if hint:
        error["hint"] = hint
    return error


def _attr_or_none(value: Optional[Any], attr_name: str) -> Optional[int]:
    if value is None:
        return None
    attr_value = getattr(value, attr_name, None)
    return int(attr_value) if attr_value is not None else None


def _milliwatts_to_watts(value: Optional[Any]) -> Optional[float]:
    if value is None:
        return None
    return round(float(value) / MILLIWATTS_PER_WATT, 2)


def _bytes_to_mib(value: int) -> float:
    return round(float(value) / BYTES_PER_MIB, 1)


def _decode_text(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _exception_summary(exc: Exception) -> str:
    text = str(exc)
    return text if text else type(exc).__name__


def _utc_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def main() -> int:
    print(json.dumps(get_gpu_snapshot(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
