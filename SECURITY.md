# Security Policy

GPU Usage Dashboard is designed for trusted local use and binds to
`127.0.0.1` by default. It does not include authentication.

## Reporting Security Or Privacy Issues

Please report vulnerabilities, privacy leaks, or unsafe defaults through a
private channel when possible, such as a GitHub private vulnerability report.
If private reporting is unavailable, open an issue with a minimal description
and avoid posting sensitive process names, usernames, command lines, hostnames,
tokens, or internal paths.

Useful reports include:

- a clear description of the risk
- affected runtime settings, routes, or API fields
- whether demo mode or real NVML telemetry was used
- steps to reproduce without exposing private machine details

## Sensitive Data

Per-GPU detail views can include process IDs, process names, Linux usernames,
command lines, and GPU memory usage. Use these runtime controls when sharing
screenshots, logs, or reproductions:

```bash
SHOW_PROCESS_DETAILS=0 ./run_dashboard.sh
SHOW_COMMAND_LINES=0 ./run_dashboard.sh
SHOW_USERNAMES=0 ./run_dashboard.sh
```

Do not bind the dashboard to a public or untrusted network without adding your
own access control.
