"""
Pytest configuration.

Setup import paths and common fixtures for tests.
"""

import sys
from pathlib import Path

# Add src to sys.path for correct imports
project_root = Path(__file__).parent.parent
src_path = project_root / "src"

if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pytest


@pytest.fixture(autouse=True)
def clean_state():
    """
    Automatic state cleanup between tests.

    Cleans bot global state for test isolation.
    """
    # Clean state before test
    yield

    # Clean state after test
    try:
        from assign_bot.bot import CHAT_STATE, PENDING, EXPECT_CONFIG

        CHAT_STATE.clear()
        PENDING.clear()
        EXPECT_CONFIG.clear()
    except ImportError:
        # If modules not loaded, ignore
        pass
