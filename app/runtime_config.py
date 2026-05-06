"""Runtime configuration helpers for local dashboard privacy controls."""

from __future__ import annotations

import os
from typing import Any, Dict, Iterable, Mapping, Optional

TRUTHY_VALUES = {"1", "true", "yes", "on", "enable", "enabled", "show", "visible", "demo"}
FALSY_VALUES = {"0", "false", "no", "off", "disable", "disabled", "hide", "hidden"}


def bool_env(name: str, default: bool, env: Optional[Mapping[str, str]] = None) -> bool:
    """Return a boolean environment setting with predictable local defaults."""

    source = os.environ if env is None else env
    raw_value = source.get(name)
    if raw_value is None:
        return default

    value = str(raw_value).strip().lower()
    if value in TRUTHY_VALUES:
        return True
    if value in FALSY_VALUES:
        return False
    return default


def demo_mode_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    """Return True when synthetic demo telemetry should be served."""

    return bool_env("DEMO_MODE", False, env=env)


def get_privacy_config(env: Optional[Mapping[str, str]] = None) -> Dict[str, bool]:
    """Return process-field visibility settings."""

    return {
        "show_process_details": bool_env("SHOW_PROCESS_DETAILS", True, env=env),
        "show_command_lines": bool_env("SHOW_COMMAND_LINES", True, env=env),
        "show_usernames": bool_env("SHOW_USERNAMES", True, env=env),
    }


def get_runtime_config(env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """Return documented runtime settings that are useful for diagnostics."""

    source = os.environ if env is None else env
    return {
        "host": str(source.get("HOST", "127.0.0.1")),
        "port": str(source.get("PORT", "8080")),
        "demo_mode": demo_mode_enabled(env=source),
        "privacy": get_privacy_config(env=source),
    }


def apply_process_privacy(
    process_payload: Optional[Dict[str, Any]],
    privacy_config: Optional[Dict[str, bool]] = None,
) -> Dict[str, Any]:
    """Redact GPU process payloads according to runtime privacy settings."""

    payload = dict(process_payload or {})
    items = list(payload.get("items") or [])
    count = payload.get("count")
    if not isinstance(count, int):
        count = len(items)

    config = get_privacy_config() if privacy_config is None else privacy_config

    if not config.get("show_process_details", True):
        return {
            **payload,
            "count": count,
            "items": [],
            "redacted": True,
            "redacted_fields": ["processes"],
            "redaction_reason": "Process details are hidden by SHOW_PROCESS_DETAILS=0.",
        }

    redacted_items = []
    redacted_fields = set()
    for item in items:
        process = dict(item)
        detail_unavailable = list(process.get("detail_unavailable") or [])
        process_redactions = set(process.get("redacted_fields") or [])

        if not config.get("show_usernames", True):
            process["username"] = None
            process_redactions.add("username")
            redacted_fields.add("username")
            _append_redaction_notice(
                detail_unavailable,
                "username",
                "Redacted by SHOW_USERNAMES=0.",
            )

        if not config.get("show_command_lines", True):
            process["command_line"] = None
            process_redactions.add("command_line")
            redacted_fields.add("command_line")
            _append_redaction_notice(
                detail_unavailable,
                "command_line",
                "Redacted by SHOW_COMMAND_LINES=0.",
            )

        process["detail_unavailable"] = detail_unavailable
        if process_redactions:
            process["redacted_fields"] = sorted(process_redactions)
        redacted_items.append(process)

    return {
        **payload,
        "count": count,
        "items": redacted_items,
        "redacted": bool(redacted_fields),
        "redacted_fields": sorted(redacted_fields),
    }


def privacy_summary(config: Optional[Dict[str, bool]] = None) -> str:
    """Return a short human-readable privacy summary for diagnostics."""

    settings = get_privacy_config() if config is None else config
    hidden = []
    if not settings.get("show_process_details", True):
        hidden.append("process details")
    else:
        if not settings.get("show_command_lines", True):
            hidden.append("command lines")
        if not settings.get("show_usernames", True):
            hidden.append("usernames")

    if not hidden:
        return "Default visibility; process fields are shown when Linux permissions allow."
    return "Runtime privacy redaction active for {}.".format(_join_words(hidden))


def _append_redaction_notice(
    detail_unavailable: list,
    field: str,
    reason: str,
) -> None:
    detail_unavailable.append({"field": field, "reason": reason})


def _join_words(values: Iterable[str]) -> str:
    items = list(values)
    if len(items) <= 1:
        return "".join(items)
    if len(items) == 2:
        return " and ".join(items)
    return "{}, and {}".format(", ".join(items[:-1]), items[-1])
