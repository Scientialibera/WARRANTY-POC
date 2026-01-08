# Warranty POC Test Suite

All test files have been organized in this folder.

## Running Tests

**IMPORTANT**: All tests must be run from the **project root directory**, not from the tests folder.

### Direct Interactive Test (Recommended)
```powershell
# From project root:
python tests/direct_test.py
```

### Automated Test Scenarios
```powershell
# From project root - run all scenarios:
python tests/test_scenarios.py

# From project root - interactive mode (type responses manually):
python tests/test_scenarios.py --interactive
```

### Quick Test
```powershell
# From project root:
python tests/quick_test.py
```

### Interactive Test
```powershell
# From project root:
python tests/interactive_test.py
```

## Test Cases Reference

See `test_cases.txt` for comprehensive test scenarios with example inputs for each step. Perfect for copy-pasting into `direct_test.py`.

## Why Run From Project Root?

The tests use module imports (`from src.agent import ...`) and spawn MCP server processes (`python -m src.servers.warranty.main` and `python -m src.servers.actions.main`). These only work correctly when executed from the project root where Python can find the `src` package.
