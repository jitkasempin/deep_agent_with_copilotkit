"""Run offline contract tests using the real installed SDK/framework packages.

Unlike the original script, this does NOT replace SDK modules or constructors
with permissive fake objects. Pytest mocks cloud transport/operation boundaries
and scripts LLM decisions; it does not claim live GCP/Gemini verification.
"""
from pathlib import Path

import pytest


if __name__ == "__main__":
    raise SystemExit(pytest.main([str(Path(__file__).with_name("test_integration.py")), "-q"]))
