#!/usr/bin/env python3
"""Run the test file to verify integration test."""

import subprocess
import sys

result = subprocess.run(
    [sys.executable, "-m", "pytest", "tests/integration/test_market_data_satisfaction.py", "-v"],
    cwd="/home/memento/PycharmProjects/Hummingbot/hummingbot/sub-packages/strategy-framework",
)
sys.exit(result.returncode)
