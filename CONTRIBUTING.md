# Contributing

Thanks for helping improve GPU Usage Dashboard. The project is intentionally
small and local-first: a FastAPI backend, vanilla HTML/CSS/JavaScript frontend,
and NVML-based GPU telemetry.

## Local Setup

Clone the repo and start the app:

```bash
git clone https://github.com/jhairgallardo/gpu_usage_dashboard.git
cd gpu_usage_dashboard
chmod +x run_dashboard.sh
./run_dashboard.sh
```

The script creates `.venv`, installs `requirements.txt`, and serves the
dashboard at `http://127.0.0.1:8080`.

Use demo mode when you do not have NVIDIA hardware available:

```bash
DEMO_MODE=1 ./run_dashboard.sh
```

## Checks

Run the same core checks used by CI:

```bash
. .venv/bin/activate
python -m pytest
node --check static/app.js
git diff --check
```

Tests should not require real NVIDIA GPUs. Use mocks or demo telemetry for
collector, API, and frontend-facing behavior.

## Runtime Privacy

The dashboard is local-only by default, but GPU process metadata can still be
sensitive. Verify privacy-related changes with the runtime controls:

```bash
SHOW_PROCESS_DETAILS=0 ./run_dashboard.sh
SHOW_COMMAND_LINES=0 ./run_dashboard.sh
SHOW_USERNAMES=0 ./run_dashboard.sh
```

Keep redacted fields explicit in API responses and readable in the frontend.

## Workflow

Keep changes focused and easy to review. Prefer small pull requests with clear
motivation, matching tests, and notes about any manual dashboard checks you ran.

## Issues

When opening a bug report, include:

- operating system and Python version
- GPU model, driver version, and whether `nvidia-smi` works
- whether the app was run in demo mode
- the route or API endpoint involved
- a short reproduction or screenshot when useful

For feature requests, describe the monitoring workflow you are trying to improve
and whether the change affects real NVML data, demo mode, privacy controls, or
frontend layout.

## Pull Requests

Keep pull requests focused and small enough to review. Include:

- what changed and why
- commands you ran locally
- any NVIDIA, Linux, browser, or privacy behavior to pay attention to
- screenshots only when the visual behavior changed

Avoid adding frontend build tooling, external CDNs, authentication, or network
exposure unless the implementation guide or a maintainer asks for it directly.
