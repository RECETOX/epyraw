"""Pytest fixtures for tests."""

from pathlib import Path

import pytest

from epyraw import Device, RawFile

# Path to the test data file
TEST_DATA_DIR = Path(__file__).parent / "testdata"
SAMPLE_RAW_FILE = TEST_DATA_DIR / "sample.raw"


@pytest.fixture
def sample_raw_file() -> Path:
    """Path to the sample .raw file for testing.

    Returns the path to tests/testdata/sample.raw.
    Raises FileNotFoundError if the test file doesn't exist.
    """
    if not SAMPLE_RAW_FILE.exists():
        raise FileNotFoundError(
            f"Test data file not found: {SAMPLE_RAW_FILE}. "
            "Please ensure the test data is available."
        )
    return SAMPLE_RAW_FILE


@pytest.fixture
def raw_file(sample_raw_file):
    """Opened RawFile fixture.

    Opens the sample RAW file and selects the MS instrument.
    Uses context manager for proper cleanup.
    """
    with RawFile(str(sample_raw_file)) as rf:
        rf.select_instrument(Device.MS, 1)
        yield rf
