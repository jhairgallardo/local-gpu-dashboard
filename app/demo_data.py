"""Synthetic GPU telemetry for public demo mode."""

from __future__ import annotations

import math
import shutil
import time
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional

from app import runtime_config

BYTES_PER_MIB = 1024 * 1024
DEMO_GPU_COUNT = 4
DEMO_MEMORY_TOTAL_MIB = 24576.0
DEMO_POWER_LIMIT_WATTS = 230.0


def demo_mode_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """Return True when the process should serve synthetic telemetry."""

    return runtime_config.demo_mode_enabled(env=env)


def get_demo_snapshot(now: Optional[float] = None) -> Dict[str, Any]:
    """Return a JSON-friendly synthetic snapshot using the real API contract."""

    current_time = time.time() if now is None else float(now)
    gpus = [_demo_gpu(index, current_time) for index in range(DEMO_GPU_COUNT)]

    return {
        "ok": True,
        "status": "demo",
        "mode": "demo",
        "demo_mode": True,
        "timestamp": _utc_timestamp(current_time),
        "gpu_count": len(gpus),
        "gpus": gpus,
        "errors": [],
        "diagnostics": get_demo_diagnostics(now=current_time),
    }


def get_demo_diagnostics(now: Optional[float] = None) -> Dict[str, Any]:
    """Return diagnostics that clearly identify synthetic demo telemetry."""

    current_time = time.time() if now is None else float(now)
    nvidia_smi_path = shutil.which("nvidia-smi")

    return {
        "ok": True,
        "status": "demo",
        "mode": "demo",
        "demo_mode": True,
        "timestamp": _utc_timestamp(current_time),
        "nvidia_smi_path": nvidia_smi_path,
        "nvidia_smi": {
            "available": nvidia_smi_path is not None,
            "path": nvidia_smi_path,
            "required": False,
        },
        "nvml": {
            "available": True,
            "driver_version": "Demo Driver 555.85",
            "nvml_version": "Demo NVML 12.5",
            "gpu_count": DEMO_GPU_COUNT,
            "demo": True,
        },
        "checks": [
            {
                "label": "Demo mode",
                "level": "warning",
                "message": "DEMO_MODE=1 is active; telemetry is synthetic and real NVML is not queried.",
            },
            {
                "label": "NVML",
                "level": "ok",
                "message": "Synthetic NVML-compatible telemetry is being served.",
            },
            {
                "label": "NVIDIA driver",
                "level": "ok",
                "message": "Demo driver metadata is active for preview mode.",
            },
            {
                "label": "GPU visibility",
                "level": "ok",
                "message": "{} synthetic NVIDIA GPU(s) visible to the dashboard.".format(DEMO_GPU_COUNT),
            },
            {
                "label": "Privacy controls",
                "level": "ok",
                "message": runtime_config.privacy_summary(),
            },
        ],
        "common_issues": [
            "Disable DEMO_MODE to query real NVIDIA hardware through NVML.",
            "Demo values are generated locally and should not be used for capacity planning.",
            "nvidia-smi is not required while demo mode is active.",
        ],
        "runtime_config": runtime_config.get_runtime_config(),
        "errors": [],
    }


def _demo_gpu(index: int, now: float) -> Dict[str, Any]:
    profiles = [
        {
            "name": "NVIDIA RTX A5000 Demo 0",
            "uuid": "GPU-DEMO-0000-UTILIZATION",
            "util_base": 72,
            "util_amp": 18,
            "mem_base": 5400,
            "mem_amp": 850,
            "temp_base": 78,
            "temp_amp": 7,
            "power_base": 178,
            "power_amp": 24,
            "fan_base": 64,
            "clock_base": 1530,
            "memory_clock": 8001,
        },
        {
            "name": "NVIDIA RTX A5000 Demo 1",
            "uuid": "GPU-DEMO-0001-RENDERING",
            "util_base": 48,
            "util_amp": 24,
            "mem_base": 8400,
            "mem_amp": 1250,
            "temp_base": 62,
            "temp_amp": 6,
            "power_base": 132,
            "power_amp": 19,
            "fan_base": 48,
            "clock_base": 1365,
            "memory_clock": 8001,
        },
        {
            "name": "NVIDIA RTX A5000 Demo 2",
            "uuid": "GPU-DEMO-0002-IDLE",
            "util_base": 18,
            "util_amp": 13,
            "mem_base": 2300,
            "mem_amp": 420,
            "temp_base": 49,
            "temp_amp": 4,
            "power_base": 74,
            "power_amp": 14,
            "fan_base": None,
            "clock_base": 1050,
            "memory_clock": 7001,
        },
        {
            "name": "NVIDIA RTX A5000 Demo 3",
            "uuid": "GPU-DEMO-0003-HIGH-LOAD",
            "util_base": 88,
            "util_amp": 9,
            "mem_base": 13300,
            "mem_amp": 1800,
            "temp_base": 84,
            "temp_amp": 6,
            "power_base": 203,
            "power_amp": 16,
            "fan_base": 78,
            "clock_base": 1695,
            "memory_clock": 8001,
        },
    ]
    profile = profiles[index]
    phase = index * 1.13
    utilization = round(
        _clamp(_wave(now, profile["util_base"], profile["util_amp"], 0.25, phase), 0, 100),
        1,
    )
    memory_used_mib = round(
        _clamp(
            _wave(now, profile["mem_base"], profile["mem_amp"], 0.18, phase + 0.7),
            256,
            DEMO_MEMORY_TOTAL_MIB - 512,
        ),
        1,
    )
    temperature = int(round(_wave(now, profile["temp_base"], profile["temp_amp"], 0.16, phase + 1.5)))
    power_draw = round(
        _clamp(
            _wave(now, profile["power_base"], profile["power_amp"], 0.22, phase + 0.2),
            35,
            DEMO_POWER_LIMIT_WATTS,
        ),
        2,
    )
    fan = None
    if profile["fan_base"] is not None:
        fan = int(round(_clamp(_wave(now, profile["fan_base"], 8, 0.2, phase + 1.1), 20, 100)))

    unavailable_metrics: List[Dict[str, str]] = []
    if fan is None:
        unavailable_metrics.append(
            {
                "metric": "fan_speed",
                "reason": "Demo profile marks this fan sensor unavailable.",
            }
        )

    if index == 2:
        unavailable_metrics.append(
            {
                "metric": "graphics_clock",
                "reason": "Demo profile marks graphics clock reporting unavailable.",
            }
        )

    return {
        "index": index,
        "uuid": profile["uuid"],
        "name": profile["name"],
        "utilization": {
            "gpu_percent": utilization,
            "memory_percent": int(round(_clamp(utilization * 0.55 + index * 7, 0, 100))),
        },
        "memory": _memory_payload(memory_used_mib, DEMO_MEMORY_TOTAL_MIB),
        "temperature_c": temperature,
        "power": {
            "draw_watts": power_draw,
            "limit_watts": DEMO_POWER_LIMIT_WATTS,
        },
        "fan_speed_percent": fan,
        "clocks": {
            "graphics_mhz": None if index == 2 else int(round(_wave(now, profile["clock_base"], 110, 0.21, phase))),
            "memory_mhz": profile["memory_clock"],
        },
        "processes": runtime_config.apply_process_privacy(_demo_processes(index)),
        "unavailable_metrics": unavailable_metrics,
    }


def _demo_processes(index: int) -> Dict[str, Any]:
    process_sets = [
        [
            _process(
                4210,
                ["compute"],
                4096.0,
                "python",
                "researcher",
                "running",
                "python train_resnet.py --epochs 90",
            ),
            _process(
                4275,
                ["compute"],
                1024.0,
                "python",
                "researcher",
                "sleeping",
                "python dataloader.py --workers 8",
            ),
        ],
        [
            _process(
                5102,
                ["graphics"],
                2560.0,
                "blender",
                "artist",
                "running",
                "blender --background scene.blend",
            ),
            _process(
                5168,
                ["compute"],
                1536.0,
                "python",
                "artist",
                "running",
                "python render_queue.py",
            ),
        ],
        [],
        [
            _process(
                6400,
                ["compute"],
                8192.0,
                "python",
                "mlops",
                "running",
                "python inference_server.py --model vision",
            ),
            _process(
                6488,
                ["graphics"],
                None,
                "Xorg",
                None,
                "sleeping",
                None,
                [
                    {
                        "field": "username",
                        "reason": "Demo profile simulates a permission-limited process owner.",
                    },
                    {
                        "field": "command_line",
                        "reason": "Demo profile simulates a hidden command line.",
                    },
                ],
            ),
        ],
    ]
    unavailable_sources: List[Dict[str, str]] = []
    if index == 2:
        unavailable_sources.append(
            {
                "metric": "graphics_processes",
                "reason": "Demo profile marks graphics process queries unavailable for this GPU.",
            }
        )

    items = process_sets[index]
    return {
        "count": len(items),
        "items": items,
        "unavailable_sources": unavailable_sources,
    }


def _process(
    pid: int,
    types: List[str],
    gpu_memory_mib: Optional[float],
    name: str,
    username: Optional[str],
    status: str,
    command_line: Optional[str],
    detail_unavailable: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    gpu_memory_bytes = (
        int(gpu_memory_mib * BYTES_PER_MIB)
        if gpu_memory_mib is not None
        else None
    )
    return {
        "pid": pid,
        "types": types,
        "gpu_memory_bytes": gpu_memory_bytes,
        "gpu_memory_mib": gpu_memory_mib,
        "gpu_instance_id": None,
        "compute_instance_id": None,
        "name": name,
        "username": username,
        "status": status,
        "command_line": command_line,
        "detail_unavailable": detail_unavailable or [],
    }


def _memory_payload(used_mib: float, total_mib: float) -> Dict[str, Any]:
    free_mib = round(total_mib - used_mib, 1)
    used_bytes = int(used_mib * BYTES_PER_MIB)
    total_bytes = int(total_mib * BYTES_PER_MIB)
    free_bytes = int(free_mib * BYTES_PER_MIB)
    return {
        "used_bytes": used_bytes,
        "total_bytes": total_bytes,
        "free_bytes": free_bytes,
        "used_mib": used_mib,
        "total_mib": total_mib,
        "free_mib": free_mib,
        "percent": round((used_mib / total_mib) * 100, 1) if total_mib else None,
    }


def _wave(now: float, base: float, amplitude: float, speed: float, phase: float) -> float:
    return base + amplitude * math.sin(now * speed + phase)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _utc_timestamp(now: float) -> str:
    return datetime.utcfromtimestamp(now).replace(microsecond=0).isoformat() + "Z"
