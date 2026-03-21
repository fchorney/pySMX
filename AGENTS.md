# AGENTS.md

## Project Overview

pySMX is a Python port of the StepManiaX SDK, enabling communication with StepManiaX arcade dance stages over USB. The project mirrors the C++ SDK (see `smx-sdk/sdk`) and adapts its callback/event model to Python's async/await and asyncio paradigms. Data structures are ported using `pystructtype` for binary compatibility.

## Architecture & Key Components

- **src/pysmx/sdk/**: Core SDK logic. Major modules:
  - `api.py`: Main API surface. Handles device discovery, command dispatch, configuration, and sensor data. Entry point: `SMXAPI` class.
  - `config.py`: Stage configuration structures and serialization logic. See `SMXStageConfig` and `PackedSensorSettings`.
  - `device_info.py`, `inputs.py`, `packets.py`, `sensors.py`: Device metadata, input/state, packet formats, and sensor data handling.
- **src/pysmx/utils.py**: Shared helpers (e.g., enums, byte manipulation).
- **src/pysmx/exceptions.py**: Custom error types for robust error handling.
- **set_stage_configs.py**: Example script for configuring stages without Windows.
- **smx-sdk/**: Reference C++ and C# SDKs. Use for protocol/struct reference only.

## Developer Workflows

- **Install dependencies**: Use [uv](https://github.com/astral-sh/uv) for dependency management. Example:
  ```sh
  uv pip install -e .
  ```
- **Build/test**: Activate a Python 3.14+ venv. Run tests with:
  ```sh
  pytest
  ```
- **Lint/typecheck**: Use Ruff and Mypy (see `pyproject.toml` for config):
  ```sh
  ruff check src/
  mypy src/
  ```
- **Run example**: See `README.md` for usage. E.g.,
  ```sh
  python set_stage_configs.py
  ```

## Project-Specific Patterns & Conventions

- **Data Structures**: Use `pystructtype` for C++ struct compatibility. See `config.py` for packing/unpacking patterns.
- **Async/await**: Prefer asyncio for event-driven code (future-proofing, not yet fully implemented).
- **Error Handling**: Raise custom exceptions from `exceptions.py` (e.g., `SMXRateLimitError`, `SMXStageNotFoundError`). Log with `loguru`.
- **Testing**: Place all tests in `tests/`, mirroring `src/pysmx/`. Use pytest with type annotations and docstrings.
- **No UI**: This port is headless; ignore C# UI code except for protocol reference.
- **Platform Support**: Code must run on Windows, macOS, and Linux. Handle USB library/platform quirks explicitly.

## Integration Points

- **USB Communication**: Uses `hidapi` (see `pyproject.toml`). Ensure `libusb` is installed (see `README.md` for platform-specific setup).
- **Logging**: All logs via `loguru`.
- **CLI**: Entry point in `src/pysmx/cli.py` (see `[project.scripts]` in `pyproject.toml`).

## References

- See `README.md` for setup, usage, and porting status.
- See `.github/copilot-instructions.md` for detailed coding standards and rationale.
- For protocol/struct details, cross-reference `smx-sdk/sdk/` C++ headers.

