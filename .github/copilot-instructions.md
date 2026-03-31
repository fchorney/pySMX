# General Instructions and Methodology
- This library is a Python port of the StepManiaX SDK which can be found in `smx-sdk/sdk` from this project root.
- The StepManiaX SDK is a C++ library, that provides an interface with the StepManiaX Stage, a physical arcade dance controller that is interfaced over USB.
- The `smx-sdk` directory also contains a C# based configuration user interface that interacts with the SDK, but it is only made for windows. This port will not have a UI, but there may be important code in the C# code that tells us how the SDK works full circle.
- Use the `pystructtype` library for defining data structures that mirror the C++ structs in the SDK. This will allow for easy serialization and deserialization of data when communicating with the Stage.
- The original C++ SDK uses a callback-based approach for handling events from the Stage. In Python, we can use async/await and asyncio for a more modern and efficient way to handle these events.
- The SDK also has a concept of "commands" that can be sent to the Stage. We can implement these as methods on a class that represents the connection to the Stage, and use asyncio
- This project should work on Windows, macOS, and Linux. Make sure to test on all platforms and handle any platform-specific issues that arise, especially with USB communication.

## Best Practices
- Follow the assigned Ruff configuration for code style and formatting. This can be found in the pyproject.toml file.
- Always use type hints in code and tests following the Mypy strict configuration.
- Document functions and classes with docstrings. Update existing docstrings if needed. 
- Do not delete any existing comments. If necessary, update comments to reflect changes in the code, but do not remove them unless they are completely irrelevant or incorrect.
- Write simple, clear code; avoid unnecessary complexity when possible.
- Prefer list comprehensions and generator expressions for concise and efficient code.
- Prefer the walrus operator (:=) for inline assignments when it improves readability.
- Write unit tests for all functions and classes, ensuring good coverage and testing edge cases.
- Avoid global variables to reduce side effects.
- When possible, always apply DRY, KISS, and generally agreed upon Python best practices.

## Stack & Tools
- Python 3.14
- Dependency management: uv
- Linting: Ruff
- Type checking: Mypy
- Testing: pytest
- Documentation: Sphinx
- Packaging: pyproject.toml
- Logging: loguru
- USB Communication: hidapi or pyusb (depending on which is more suitable for the use case)

## Project Structure
- Use subfolders in the ./src/pysmx directory to organize code by functionality or feature.

## Error Handling & Logging
- Implement robust error handling and logging, including context capture.
- Use structured logging with appropriate log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL).
- Avoid try/catch blocks that are too broad; catch specific exceptions and handle them appropriately.
- Use early returns for error conditions; avoid deep nesting.
- Avoid unnecessary else statements; use the if-return pattern.

## Testing
- Use pytest (not unittest) and pytest plugins for all tests.
- Place all tests in ./tests directory, mirroring the structure of the source code.
- All tests must have typing annotations and docstrings.
- For type checking in tests, import the following types individually if needed:
```python
from _pytest.capture import CaptureFixture
from _pytest.fixtures import FixtureRequest
from _pytest.logging import LogCaptureFixture
from _pytest.monkeypatch import MonkeyPatch
```

## Dependencies
- If other dependencies are necessary, they should be minimal and well-maintained. Always prefer standard library modules when possible.
- Use uv for dependency management and ensure that all dependencies are listed in pyproject.toml.