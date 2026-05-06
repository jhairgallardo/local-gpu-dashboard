"""NVIDIA and NVML diagnostics helpers."""

from __future__ import annotations

import shutil
from datetime import datetime
from typing import Any, Dict, Optional

from app import demo_data
from app import gpu_collector
from app import runtime_config


def get_diagnostics(nvml: Optional[Any] = None) -> Dict[str, Any]:
    """Return lightweight NVIDIA/NVML availability information."""

    if nvml is None and demo_data.demo_mode_enabled():
        return demo_data.get_demo_diagnostics()

    nvml_module = gpu_collector.pynvml if nvml is None else nvml
    timestamp = _utc_timestamp()
    nvidia_smi_path = shutil.which("nvidia-smi")

    if nvml_module is None:
        return {
            "ok": False,
            "status": "pynvml_unavailable",
            "timestamp": timestamp,
            "nvidia_smi": {
                "available": nvidia_smi_path is not None,
                "path": nvidia_smi_path,
            },
            "nvml": {
                "available": False,
                "driver_version": None,
                "nvml_version": None,
                "gpu_count": None,
            },
            "checks": _diagnostic_checks(
                nvml_available=False,
                driver_version=None,
                nvidia_smi_path=nvidia_smi_path,
                gpu_count=None,
            ),
            "common_issues": _common_issues(),
            "runtime_config": runtime_config.get_runtime_config(),
            "errors": [
                {
                    "code": "pynvml_unavailable",
                    "message": "The nvidia-ml-py package could not be imported.",
                    "hint": "Run ./run_dashboard.sh to install dependencies, then try again.",
                }
            ],
        }

    initialized = False
    try:
        nvml_module.nvmlInit()
        initialized = True
        gpu_count = int(nvml_module.nvmlDeviceGetCount())
        status = "ok" if gpu_count > 0 else "no_gpus"
        driver_version = _decode_text(
            _safe_system_value(nvml_module, "nvmlSystemGetDriverVersion")
        )
        nvml_version = _decode_text(
            _safe_system_value(nvml_module, "nvmlSystemGetNVMLVersion")
        )

        errors = []
        if gpu_count == 0:
            errors.append(
                {
                    "code": "no_nvidia_gpus",
                    "message": "NVML initialized, but no NVIDIA GPUs were detected.",
                    "hint": "Confirm the machine has NVIDIA GPUs visible to the current user.",
                }
            )

        return {
            "ok": gpu_count > 0,
            "status": status,
            "timestamp": timestamp,
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
            "errors": errors,
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "nvml_error",
            "timestamp": timestamp,
            "nvidia_smi": {
                "available": nvidia_smi_path is not None,
                "path": nvidia_smi_path,
            },
            "nvml": {
                "available": False,
                "driver_version": None,
                "nvml_version": None,
                "gpu_count": None,
            },
            "checks": _diagnostic_checks(
                nvml_available=False,
                driver_version=None,
                nvidia_smi_path=nvidia_smi_path,
                gpu_count=None,
            ),
            "common_issues": _common_issues(),
            "runtime_config": runtime_config.get_runtime_config(),
            "errors": [_error_from_exception(exc)],
        }
    finally:
        if initialized:
            try:
                nvml_module.nvmlShutdown()
            except Exception:
                pass


def _safe_system_value(nvml_module: Any, function_name: str) -> Optional[Any]:
    function = getattr(nvml_module, function_name, None)
    if function is None:
        return None
    try:
        return function()
    except Exception:
        return None


def _diagnostic_checks(
    nvml_available: bool,
    driver_version: Optional[str],
    nvidia_smi_path: Optional[str],
    gpu_count: Optional[int],
) -> list:
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


def _common_issues() -> list:
    return [
        "NVIDIA driver is not installed, not loaded, or incompatible with the running kernel.",
        "The current user or container does not have permission to access NVIDIA device files.",
        "nvidia-smi is missing from PATH even though NVML may be installed.",
        "GPU process command lines can be hidden by Linux permissions for other users.",
    ]


def _error_from_exception(exc: Exception) -> Dict[str, str]:
    exception_name = type(exc).__name__
    exception_text = str(exc) or exception_name
    lowered = "{} {}".format(exception_name, exception_text).lower()

    if "librarynotfound" in lowered or "shared library" in lowered:
        return {
            "code": "nvml_library_missing",
            "message": "The NVIDIA Management Library could not be loaded.",
            "detail": exception_text,
            "hint": "Install or repair the NVIDIA driver so libnvidia-ml is available.",
        }

    if "drivernotloaded" in lowered or "driver not loaded" in lowered:
        return {
            "code": "nvidia_driver_unavailable",
            "message": "The NVIDIA driver is not loaded or is unavailable to this process.",
            "detail": exception_text,
            "hint": "Check the NVIDIA driver installation and confirm nvidia-smi works.",
        }

    if "nopermission" in lowered or "permission" in lowered:
        return {
            "code": "nvml_permission_denied",
            "message": "NVML denied access to GPU information.",
            "detail": exception_text,
            "hint": "Run the dashboard as a user with permission to query NVIDIA GPU state.",
        }

    return {
        "code": "nvml_error",
        "message": "NVML failed while checking NVIDIA availability.",
        "detail": exception_text,
        "hint": "Run nvidia-smi to compare driver and GPU availability.",
    }


def _decode_text(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _utc_timestamp() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
