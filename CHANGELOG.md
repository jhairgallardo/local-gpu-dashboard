# Changelog

All notable changes to GPU Usage Dashboard will be documented in this file.

The format is inspired by Keep a Changelog, and this project uses semantic
versioning for public releases.

## [1.0.0] - 2026-05-06

Initial public release readiness.

### Added

- Local FastAPI dashboard for NVIDIA GPU monitoring through NVML.
- No-build HTML, CSS, and JavaScript frontend with overview, per-GPU detail, and
  diagnostics views.
- Real-time polling with short in-browser histories and chart interactions.
- Demo mode for previewing the dashboard without NVIDIA hardware.
- Runtime privacy controls for process rows, command lines, and usernames.
- Public README with demo screenshots, troubleshooting, privacy notes, and local
  launch instructions.
- GitHub Actions CI, contribution guide, security policy, and issue templates.

### Notes

- The dashboard binds to `127.0.0.1` by default and does not include
  authentication.
- NVIDIA driver, NVML, permissions, WSL, containers, and MIG configuration can
  affect which GPU fields are available.
