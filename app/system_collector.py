"""psutil-backed system resource telemetry."""

from __future__ import annotations

import math
import time
from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import psutil

from app import demo_data

BYTES_PER_GIB = 1024 ** 3

CPU_SENSOR_NAMES = {
    "coretemp",
    "k10temp",
    "cpu_thermal",
    "cpu-thermal",
    "x86_pkg_temp",
    "zenpower",
}
NON_CPU_SENSOR_HINTS = (
    "acpitz",
    "amdgpu",
    "ath",
    "battery",
    "drivetemp",
    "enp",
    "eth",
    "gpu",
    "iwlwifi",
    "mlx",
    "nouveau",
    "nvme",
    "nvidia",
    "pch",
    "phy",
    "radeon",
    "wifi",
    "wlan",
)
PREFERRED_LABELS = (
    ("tdie", 70),
    ("package id", 65),
    ("package", 62),
    ("tctl", 55),
    ("cpu", 45),
    ("core", 28),
)


def get_system_snapshot(now: Optional[float] = None) -> Dict[str, Any]:
    """Return JSON-friendly whole-machine resource telemetry."""

    if demo_data.demo_mode_enabled():
        return demo_data.get_demo_system_snapshot(now=now)

    current_time = time.time() if now is None else float(now)
    errors: List[Dict[str, str]] = []

    cpu_temperature = _cpu_temperature_payload(errors)

    return {
        "ok": True,
        "status": "ok" if cpu_temperature["available"] else "partial",
        "mode": "real",
        "demo_mode": False,
        "timestamp": _utc_timestamp(current_time),
        "cpu": {
            "utilization_percent": _safe_percent(lambda: psutil.cpu_percent(interval=None)),
            "per_core_percent": _safe_percent_list(lambda: psutil.cpu_percent(interval=None, percpu=True)),
            "logical_cores": psutil.cpu_count(logical=True),
            "physical_cores": psutil.cpu_count(logical=False),
            "frequency_mhz": _cpu_frequency_payload(),
            "temperature": cpu_temperature,
        },
        "memory": _memory_payload(psutil.virtual_memory()),
        "swap": _memory_payload(psutil.swap_memory()),
        "load_average": _load_average_payload(),
        "uptime": _uptime_payload(current_time),
        "errors": errors,
    }


def _cpu_temperature_payload(errors: List[Dict[str, str]]) -> Dict[str, Any]:
    try:
        sensors = psutil.sensors_temperatures(fahrenheit=False)
    except Exception as exc:
        errors.append(
            {
                "code": "cpu_temperature_error",
                "message": "CPU temperature could not be read from psutil.",
                "detail": str(exc) or type(exc).__name__,
            }
        )
        return _unavailable_temperature("psutil could not read Linux thermal sensors.")

    selected = _select_cpu_temperature(sensors)
    if selected is None:
        return _unavailable_temperature("No CPU-specific thermal sensor was exposed by Linux.")

    sensor_name, entry = selected
    return {
        "available": True,
        "current_c": _rounded_float(getattr(entry, "current", None), 1),
        "high_c": _rounded_float(getattr(entry, "high", None), 1),
        "critical_c": _rounded_float(getattr(entry, "critical", None), 1),
        "sensor": sensor_name,
        "label": getattr(entry, "label", None) or None,
        "reason": None,
    }


def _select_cpu_temperature(
    sensors: Mapping[str, Sequence[Any]],
) -> Optional[Tuple[str, Any]]:
    best_score = -1
    best_entry: Optional[Tuple[str, Any]] = None

    for sensor_name, entries in sensors.items():
        normalized_name = str(sensor_name).strip().lower()
        if not entries or _looks_non_cpu_sensor(normalized_name):
            continue

        for entry in entries:
            current = _to_finite_number(getattr(entry, "current", None))
            if current is None or current < -40 or current > 150:
                continue

            label = str(getattr(entry, "label", "") or "").strip().lower()
            score = _sensor_score(normalized_name, label)
            if score > best_score:
                best_score = score
                best_entry = (sensor_name, entry)

    return best_entry


def _sensor_score(sensor_name: str, label: str) -> int:
    score = 0
    if sensor_name in CPU_SENSOR_NAMES:
        score += 100
    elif "cpu" in sensor_name:
        score += 60
    elif "temp" in sensor_name:
        score += 20

    for label_hint, label_score in PREFERRED_LABELS:
        if label_hint in label:
            score += label_score
            break

    if not label:
        score += 5

    return score


def _looks_non_cpu_sensor(sensor_name: str) -> bool:
    if sensor_name in CPU_SENSOR_NAMES:
        return False
    return any(hint in sensor_name for hint in NON_CPU_SENSOR_HINTS)


def _unavailable_temperature(reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "current_c": None,
        "high_c": None,
        "critical_c": None,
        "sensor": None,
        "label": None,
        "reason": reason,
    }


def _cpu_frequency_payload() -> Dict[str, Any]:
    try:
        frequency = psutil.cpu_freq()
    except Exception:
        frequency = None

    if frequency is None:
        return {
            "available": False,
            "current_mhz": None,
            "min_mhz": None,
            "max_mhz": None,
        }

    return {
        "available": True,
        "current_mhz": _rounded_float(getattr(frequency, "current", None), 1),
        "min_mhz": _rounded_float(getattr(frequency, "min", None), 1),
        "max_mhz": _rounded_float(getattr(frequency, "max", None), 1),
    }


def _load_average_payload() -> Dict[str, Any]:
    try:
        one_min, five_min, fifteen_min = psutil.getloadavg()
    except (AttributeError, OSError):
        return {
            "available": False,
            "one_min": None,
            "five_min": None,
            "fifteen_min": None,
        }

    return {
        "available": True,
        "one_min": _rounded_float(one_min, 2),
        "five_min": _rounded_float(five_min, 2),
        "fifteen_min": _rounded_float(fifteen_min, 2),
    }


def _uptime_payload(now: float) -> Dict[str, Any]:
    boot_time = psutil.boot_time()
    uptime_seconds = max(0, now - boot_time)
    return {
        "seconds": round(uptime_seconds),
        "boot_time": _utc_timestamp(boot_time),
    }


def _memory_payload(memory: Any) -> Dict[str, Any]:
    total = int(getattr(memory, "total", 0) or 0)
    used = int(getattr(memory, "used", 0) or 0)
    free = int(getattr(memory, "free", 0) or 0)
    available = getattr(memory, "available", None)

    return {
        "total_bytes": total,
        "used_bytes": used,
        "free_bytes": free,
        "available_bytes": int(available) if available is not None else None,
        "percent": _rounded_float(getattr(memory, "percent", None), 1),
        "total_gib": _bytes_to_gib(total),
        "used_gib": _bytes_to_gib(used),
        "free_gib": _bytes_to_gib(free),
        "available_gib": _bytes_to_gib(available) if available is not None else None,
    }


def _safe_percent(callback: Any) -> Optional[float]:
    try:
        return _rounded_float(callback(), 1)
    except Exception:
        return None


def _safe_percent_list(callback: Any) -> List[Optional[float]]:
    try:
        return [_rounded_float(value, 1) for value in callback()]
    except Exception:
        return []


def _bytes_to_gib(value: Optional[float]) -> Optional[float]:
    number = _to_finite_number(value)
    return round(number / BYTES_PER_GIB, 2) if number is not None else None


def _rounded_float(value: Optional[float], digits: int) -> Optional[float]:
    number = _to_finite_number(value)
    return round(number, digits) if number is not None else None


def _to_finite_number(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _utc_timestamp(now: float) -> str:
    return datetime.utcfromtimestamp(now).replace(microsecond=0).isoformat() + "Z"
