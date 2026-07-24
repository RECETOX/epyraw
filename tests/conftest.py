"""Pytest fixtures for tests."""

import os
import tempfile
from pathlib import Path

import pytest

from epyraw import Device, RawFile

# Path to the test data file
TEST_DATA_DIR = Path(__file__).parent / "testdata"
SAMPLE_RAW_FILE = TEST_DATA_DIR / "sample.raw"

# Zenodo test file configuration
ZENODO_URL = "https://zenodo.org/records/6878356/files/8_qc_no_dil_milliq.raw?download=1"
ZENODO_FILENAME = "8_qc_no_dil_milliq.raw"


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="session")
def zenodo_raw_file() -> Path:
    """Path to the Zenodo QC sample .raw file.

    Downloads the file from Zenodo to a temporary session-scoped location
    if not already present. The file is reused across all tests in the session.

    Returns:
        Path to the downloaded .raw file.

    Note:
        This is a large file (~2.4GB). The download happens once per session.
        Set ZENODO_TEST_FILE environment variable to use a local copy.
    """
    # Check if user has provided a local file
    env_file = os.environ.get("ZENODO_TEST_FILE")
    if env_file and Path(env_file).exists():
        return Path(env_file)

    # Use temp directory for session-scoped file
    temp_dir = Path(tempfile.gettempdir()) / "epyraw_test_data"
    temp_dir.mkdir(exist_ok=True)

    zenodo_file = temp_dir / ZENODO_FILENAME

    # Skip download if file exists and is non-empty
    if zenodo_file.exists() and zenodo_file.stat().st_size > 0:
        return zenodo_file

    # Download the file
    print(f"\nDownloading test file from Zenodo ({ZENODO_URL})...")
    print(f"This is a large file (~2.4GB). This will only happen once per session.")

    import urllib.request

    try:
        # Use reporthook to show progress
        def report(block_num, block_size, total_size):
            current = block_num * block_size
            percent = min(current * 100 / total_size, 100)
            print(f"\r  Progress: {percent:.1f}%", end="", flush=True)

        urllib.request.urlretrieve(ZENODO_URL, zenodo_file, reporthook=report)
        print("\n  Download complete.")

        # Verify file size (should be ~2.4GB)
        size_gb = zenodo_file.stat().st_size / (1024**3)
        print(f"  File size: {size_gb:.2f} GB")

        return zenodo_file
    except Exception as e:
        pytest.skip(f"Could not download Zenodo test file: {e}")


@pytest.fixture(scope="session")
def zenodo_raw_file_fixture(zenodo_raw_file):
    """Opened RawFile fixture for Zenodo QC file.

    Opens the downloaded QC sample and selects the MS instrument.
    Session-scoped to avoid repeated file opening overhead.
    """
    with RawFile(str(zenodo_raw_file)) as rf:
        rf.select_instrument(Device.MS, 1)
        yield rf


@pytest.fixture
def raw_file(sample_raw_file):
    """Opened RawFile fixture for small sample file.

    Opens the sample RAW file and selects the MS instrument.
    Uses context manager for proper cleanup.
    """
    with RawFile(str(sample_raw_file)) as rf:
        rf.select_instrument(Device.MS, 1)
        yield rf
