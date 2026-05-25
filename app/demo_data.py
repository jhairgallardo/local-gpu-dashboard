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
BYTES_PER_GIB = 1024 ** 3


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


def get_demo_system_snapshot(now: Optional[float] = None) -> Dict[str, Any]:
    """Return synthetic host telemetry for the System tab."""

    current_time = time.time() if now is None else float(now)
    cpu_utilization = round(
        _clamp(
            34
            + 12 * math.sin(current_time * 0.045)
            + 7 * math.sin(current_time * 0.17 + 1.3)
            + _jitter(current_time, 31, 3.6),
            8,
            82,
        ),
        1,
    )
    cpu_temperature = round(
        _clamp(
            47
            + cpu_utilization * 0.22
            + 2.8 * math.sin(current_time * 0.025 + 0.6)
            + _jitter(current_time, 43, 1.1),
            35,
            91,
        ),
        1,
    )
    memory_total_gib = 128.0
    memory_used_gib = round(
        _clamp(
            48
            + 6.5 * math.sin(current_time * 0.031 + 0.8)
            + 3.2 * _pulse(_cycle(current_time, 90, 0.18), 0.35, 0.7),
            24,
            96,
        ),
        2,
    )
    swap_total_gib = 16.0
    swap_used_gib = round(
        _clamp(1.2 + 0.4 * math.sin(current_time * 0.019 + 1.7), 0, 4.5),
        2,
    )
    load_one = round(_clamp(cpu_utilization / 10 + 1.2 * math.sin(current_time * 0.06), 0.4, 12), 2)

    return {
        "ok": True,
        "status": "demo",
        "mode": "demo",
        "demo_mode": True,
        "timestamp": _utc_timestamp(current_time),
        "cpu": {
            "utilization_percent": cpu_utilization,
            "per_core_percent": _demo_core_utilization(current_time, cpu_utilization, 16),
            "logical_cores": 16,
            "physical_cores": 8,
            "frequency_mhz": {
                "available": True,
                "current_mhz": round(3150 + cpu_utilization * 10 + _jitter(current_time, 52, 80), 1),
                "min_mhz": 550.0,
                "max_mhz": 5200.0,
            },
            "temperature": {
                "available": True,
                "current_c": cpu_temperature,
                "high_c": 86.0,
                "critical_c": 95.0,
                "sensor": "demo_cpu",
                "label": "Package",
                "reason": None,
            },
        },
        "memory": _system_memory_payload(memory_used_gib, memory_total_gib),
        "swap": _system_memory_payload(swap_used_gib, swap_total_gib),
        "load_average": {
            "available": True,
            "one_min": load_one,
            "five_min": round(_clamp(load_one * 0.88, 0.3, 10), 2),
            "fifteen_min": round(_clamp(load_one * 0.76, 0.2, 9), 2),
        },
        "uptime": {
            "seconds": int(4 * 24 * 60 * 60 + _cycle(current_time, 86400, 0) * 86400),
            "boot_time": _utc_timestamp(current_time - (4 * 24 * 60 * 60)),
        },
        "errors": [],
    }


def _demo_gpu(index: int, now: float) -> Dict[str, Any]:
    profiles = [
        {
            "name": "NVIDIA RTX A5000 Demo 0",
            "uuid": "GPU-DEMO-0000-UTILIZATION",
            "memory_base": 5200,
            "memory_steps": [(0.16, 720), (0.38, 1150), (0.67, -820), (0.82, 540)],
            "memory_period": 84,
            "memory_phase": 0.08,
            "temp_idle": 48,
            "temp_gain": 0.42,
            "power_idle": 43,
            "power_gain": 1.72,
            "fan_base": 64,
            "clock_base": 1530,
            "memory_clock": 8001,
        },
        {
            "name": "NVIDIA RTX A5000 Demo 1",
            "uuid": "GPU-DEMO-0001-RENDERING",
            "memory_base": 7400,
            "memory_steps": [(0.22, 920), (0.48, 470), (0.74, -660), (0.9, 310)],
            "memory_period": 112,
            "memory_phase": 0.31,
            "temp_idle": 43,
            "temp_gain": 0.34,
            "power_idle": 39,
            "power_gain": 1.34,
            "fan_base": 48,
            "clock_base": 1365,
            "memory_clock": 8001,
        },
        {
            "name": "NVIDIA RTX A5000 Demo 2",
            "uuid": "GPU-DEMO-0002-IDLE",
            "memory_base": 2150,
            "memory_steps": [(0.2, 180), (0.43, -90), (0.58, 230), (0.86, -140)],
            "memory_period": 96,
            "memory_phase": 0.58,
            "temp_idle": 38,
            "temp_gain": 0.28,
            "power_idle": 31,
            "power_gain": 0.95,
            "fan_base": None,
            "clock_base": 1050,
            "memory_clock": 7001,
        },
        {
            "name": "NVIDIA RTX A5000 Demo 3",
            "uuid": "GPU-DEMO-0003-HIGH-LOAD",
            "memory_base": 12200,
            "memory_steps": [(0.12, 1450), (0.34, 1320), (0.52, -960), (0.79, 780)],
            "memory_period": 132,
            "memory_phase": 0.17,
            "temp_idle": 51,
            "temp_gain": 0.38,
            "power_idle": 48,
            "power_gain": 1.68,
            "fan_base": 78,
            "clock_base": 1695,
            "memory_clock": 8001,
        },
    ]
    profile = profiles[index]
    utilization = round(_demo_utilization(index, now), 1)
    memory_used_mib = round(
        _clamp(
            _demo_memory_used(now, profile),
            256,
            DEMO_MEMORY_TOTAL_MIB - 512,
        ),
        1,
    )
    temperature = int(round(_demo_temperature(now, profile, utilization)))
    power_draw = round(
        _clamp(
            _demo_power_draw(now, profile, utilization),
            35,
            DEMO_POWER_LIMIT_WATTS,
        ),
        2,
    )
    fan = None
    if profile["fan_base"] is not None:
        fan = int(round(_clamp(_demo_fan_speed(now, profile, temperature), 20, 100)))

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
            "graphics_mhz": None if index == 2 else int(round(_demo_graphics_clock(now, profile, utilization))),
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


def _system_memory_payload(used_gib: float, total_gib: float) -> Dict[str, Any]:
    free_gib = round(max(0, total_gib - used_gib), 2)
    available_gib = round(max(0, free_gib + total_gib * 0.08), 2)
    return {
        "used_bytes": int(used_gib * BYTES_PER_GIB),
        "total_bytes": int(total_gib * BYTES_PER_GIB),
        "free_bytes": int(free_gib * BYTES_PER_GIB),
        "available_bytes": int(available_gib * BYTES_PER_GIB),
        "used_gib": used_gib,
        "total_gib": total_gib,
        "free_gib": free_gib,
        "available_gib": available_gib,
        "percent": round((used_gib / total_gib) * 100, 1) if total_gib else None,
    }


def _demo_core_utilization(now: float, average: float, count: int) -> List[float]:
    values = []
    for index in range(count):
        core_value = average + 11 * math.sin(now * (0.08 + index * 0.003) + index * 0.8)
        core_value += _jitter(now, index + 60, 2.2)
        values.append(round(_clamp(core_value, 2, 99), 1))
    return values


def _demo_utilization(index: int, now: float) -> float:
    """Return deterministic but workload-like utilization for a demo GPU."""

    if index == 0:
        cycle = _cycle(now, 42, 0.03)
        bursts = [
            (0.08, 0.18, 18),
            (0.24, 0.34, 25),
            (0.48, 0.58, 17),
            (0.74, 0.84, 22),
        ]
        validation_dip = -24 if 0.62 <= cycle <= 0.7 else 0
        value = 57 + validation_dip + sum(
            _pulse(cycle, start, end) * amount for start, end, amount in bursts
        )
        value += _jitter(now, index, 5.5)
        return _clamp(value, 38, 96)

    if index == 1:
        ramp = _cycle(now, 26, 0.21)
        tile_load = 22 + 50 * ramp
        reset_dip = -18 if ramp > 0.86 else 0
        value = tile_load + reset_dip + _jitter(now, index, 4.2)
        return _clamp(value, 14, 78)

    if index == 2:
        cycle = _cycle(now, 58, 0.47)
        background_spikes = (
            _pulse(cycle, 0.18, 0.24) * 22
            + _pulse(cycle, 0.53, 0.58) * 14
            + _pulse(cycle, 0.81, 0.86) * 28
        )
        value = 5 + background_spikes + _jitter(now, index, 2.0)
        return _clamp(value, 0, 38)

    cycle = _cycle(now, 50, 0.66)
    batch_wave = 82 + 8 * math.sin(now * 0.31 + 1.1)
    service_dip = -19 * _pulse(cycle, 0.32, 0.43)
    queue_spike = 7 * _pulse(cycle, 0.74, 0.79)
    value = batch_wave + service_dip + queue_spike + _jitter(now, index, 3.8)
    return _clamp(value, 55, 99)


def _demo_memory_used(now: float, profile: Mapping[str, Any]) -> float:
    """Return memory as plateaus and steps, closer to real allocations."""

    cycle = _cycle(now, profile["memory_period"], profile["memory_phase"])
    used_mib = float(profile["memory_base"])
    for threshold, delta_mib in profile["memory_steps"]:
        if cycle >= threshold:
            used_mib += float(delta_mib)

    drift = 90 * math.sin(now * 0.035 + profile["memory_phase"] * 9)
    small_reclaim = -140 * _pulse(cycle, 0.93, 0.98)
    return used_mib + drift + small_reclaim


def _demo_temperature(now: float, profile: Mapping[str, Any], utilization: float) -> float:
    """Return slower temperature movement that lags utilization changes."""

    delayed_utilization = 0.72 * utilization + 0.28 * (
        utilization + 13 * math.sin((now - 18) * 0.07 + profile["memory_phase"] * 4)
    )
    value = profile["temp_idle"] + profile["temp_gain"] * delayed_utilization
    value += 1.8 * math.sin(now * 0.026 + profile["memory_phase"] * 6)
    value += _jitter(now, int(profile["memory_phase"] * 100), 0.7)
    return _clamp(value, 34, 92)


def _demo_power_draw(now: float, profile: Mapping[str, Any], utilization: float) -> float:
    value = profile["power_idle"] + profile["power_gain"] * utilization
    value += 4.5 * math.sin(now * 0.19 + profile["memory_phase"] * 5)
    value += _jitter(now, int(profile["power_idle"]), 3.0)
    return value


def _demo_fan_speed(now: float, profile: Mapping[str, Any], temperature: float) -> float:
    thermal_target = profile["fan_base"] + max(0, temperature - 65) * 0.9
    return thermal_target + 2.4 * math.sin(now * 0.05 + profile["memory_phase"] * 8)


def _demo_graphics_clock(now: float, profile: Mapping[str, Any], utilization: float) -> float:
    boost = 1 if utilization >= 45 else 0.55
    value = profile["clock_base"] * boost
    value += 75 * math.sin(now * 0.13 + profile["memory_phase"] * 7)
    value += _jitter(now, int(profile["clock_base"]), 24)
    return _clamp(value, 420, 1845)


def _cycle(now: float, period: float, phase: float) -> float:
    return ((now / period) + phase) % 1.0


def _pulse(position: float, start: float, end: float) -> float:
    if position < start or position > end:
        return 0.0

    midpoint = start + (end - start) / 2
    if position <= midpoint:
        return _smoothstep((position - start) / max(midpoint - start, 0.001))

    return _smoothstep((end - position) / max(end - midpoint, 0.001))


def _smoothstep(value: float) -> float:
    amount = _clamp(value, 0, 1)
    return amount * amount * (3 - 2 * amount)


def _jitter(now: float, seed: int, amplitude: float) -> float:
    return amplitude * (
        0.58 * math.sin(now * (0.91 + seed * 0.011) + seed * 1.7)
        + 0.29 * math.sin(now * (1.73 + seed * 0.007) + seed * 0.41)
        + 0.13 * math.sin(now * (3.27 + seed * 0.003) + seed * 2.3)
    )


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _utc_timestamp(now: float) -> str:
    return datetime.utcfromtimestamp(now).replace(microsecond=0).isoformat() + "Z"
