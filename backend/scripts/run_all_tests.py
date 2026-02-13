#!/usr/bin/env python3
"""
Run the full backend test suite and report success or failure.

Use this after cleanups or changes to ensure nothing is broken.

Usage (from project root):
  python backend/scripts/run_all_tests.py

Or from backend/:
  python scripts/run_all_tests.py

Requires: pytest (pip install pytest)

Exit code: 0 if all tests pass, 1 otherwise.
"""

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    # Run from backend/ so `app` is importable
    backend_dir = Path(__file__).resolve().parent.parent
    os.chdir(backend_dir)

    tests_dir = backend_dir / "tests"
    if not tests_dir.is_dir():
        print(f"ERROR: Tests directory not found: {tests_dir}")
        return 1

    print("=" * 60)
    print("NEC Backend – Full test suite")
    print("=" * 60)
    print(f"Working directory: {backend_dir}")
    print(f"Tests directory:   {tests_dir}")
    print()

    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(tests_dir),
        "-v",
        "--tb=short",
        "-q",  # less per-test noise, summary at end
    ]

    try:
        result = subprocess.run(cmd, cwd=str(backend_dir))
    except FileNotFoundError:
        print("ERROR: pytest not found. Install with: pip install pytest")
        return 1

    print()
    if result.returncode == 0:
        print("=" * 60)
        print("All tests passed.")
        print("=" * 60)
    else:
        print("=" * 60)
        print("Some tests failed. See output above.")
        print("=" * 60)

    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
