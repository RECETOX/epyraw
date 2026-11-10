"""Download Thermo RawFileReader runtime DLLs.

This module provides functionality to download the required .NET assemblies
from the Thermo Fisher RawFileReader GitHub repository.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import requests
except ImportError:
    # Deliberately not logged: this runs during ``import epyraw``, before the
    # package's NullHandler is attached, so a record here would reach stderr
    # through logging's last-resort handler. The cause is named where it matters,
    # in download_runtimes().
    requests = None  # type: ignore


# GitHub raw content URLs for the DLLs
RAW_FILE_READER_URLS = {
    "base_url": "https://raw.githubusercontent.com/thermofisherlsms/RawFileReader/main/Libs/NetCore/Net8Old/Assemblies/",
    "files": [
        "OpenMcdf.dll",
        "OpenMcdf.Extensions.dll",
        "ThermoFisher.CommonCore.BackgroundSubtraction.dll",
        "ThermoFisher.CommonCore.BackgroundSubtraction.xml",
        "ThermoFisher.CommonCore.Data.dll",
        "ThermoFisher.CommonCore.Data.xml",
        "ThermoFisher.CommonCore.MassPrecisionEstimator.dll",
        "ThermoFisher.CommonCore.MassPrecisionEstimator.xml",
        "ThermoFisher.CommonCore.RawFileReader.dll",
        "ThermoFisher.CommonCore.RawFileReader.xml",
    ],
}


def get_default_runtime_path() -> Path:
    """Get the default path for runtime DLLs.

    Returns:
        Path to ~/.epyraw/runtimes/net8old/
    """
    return Path.home() / ".epyraw" / "runtimes" / "net8old"


def download_runtimes(
    target_path: Path | None = None, force: bool = False, progress: bool = True
) -> Path:
    """Download the Thermo RawFileReader runtime DLLs.

    Args:
        target_path: Optional custom path for DLLs. Defaults to ~/.epyraw/runtimes/net8old/
        force: If True, re-download even if files exist
        progress: If True, print progress messages

    Returns:
        Path to the directory containing the downloaded DLLs

    Raises:
        RuntimeError: If download fails
        ImportError: If requests library is not installed
    """
    if requests is None:
        logger.error("'requests' is not installed; runtime DLLs cannot be downloaded")
        raise ImportError(
            "requests library is required for downloading runtimes. "
            "Install it with: pip install requests"
        )

    if target_path is None:
        target_path = get_default_runtime_path()

    # Create target directory
    target_path.mkdir(parents=True, exist_ok=True)

    base_url = str(RAW_FILE_READER_URLS["base_url"])
    files = RAW_FILE_READER_URLS["files"]

    downloaded = []
    failed = []

    for filename in files:
        file_path = target_path / filename
        if file_path.exists() and not force:
            if progress:
                print(f"  Skipping {filename} (already exists)")
            logger.debug("Skipping %s (already exists)", filename)
            downloaded.append(file_path)
            continue

        url = base_url + filename
        try:
            if progress:
                print(f"  Downloading {filename}...")
            logger.debug("Downloading %s", url)
            response = requests.get(url, timeout=30)
            response.raise_for_status()

            with open(file_path, "wb") as f:
                f.write(response.content)
            downloaded.append(file_path)
        except Exception as e:
            # Clean up partial download
            if file_path.exists():
                file_path.unlink()
            failed.append((filename, str(e)))
            logger.warning("Failed to download %s: %s", filename, e, exc_info=True)

    if failed:
        error_msg = "\n".join(f"  {name}: {err}" for name, err in failed)
        logger.error("Download incomplete: %d succeeded, %d failed", len(downloaded), len(failed))
        raise RuntimeError(
            f"Failed to download {len(failed)} of {len(files)} files "
            f"({len(downloaded)} succeeded):\n{error_msg}"
        )

    if progress:
        print(f"Successfully downloaded {len(downloaded)} files to: {target_path}")
    logger.info("Downloaded %d of %d files to %s", len(downloaded), len(files), target_path)

    return target_path


def check_runtimes_present(path: Path | None = None) -> bool:
    """Check if runtime DLLs are present.

    Args:
        path: Optional custom path. Defaults to ~/.epyraw/runtimes/net8old/

    Returns:
        True if all required DLLs are present
    """
    if path is None:
        path = get_default_runtime_path()

    required_files = [
        "ThermoFisher.CommonCore.RawFileReader.dll",
        "ThermoFisher.CommonCore.Data.dll",
        "ThermoFisher.CommonCore.BackgroundSubtraction.dll",
        "ThermoFisher.CommonCore.MassPrecisionEstimator.dll",
        "OpenMcdf.dll",
    ]

    return all((path / f).exists() for f in required_files)


def ensure_runtimes_available(runtime_path: Path | None = None) -> Path:
    """Ensure runtime DLLs are available, downloading if necessary.

    Args:
        runtime_path: Optional custom path. Checks default location if not provided.

    Returns:
        Path to the runtime directory

    Raises:
        RuntimeError: If runtimes cannot be downloaded
    """
    # Check provided path first
    if runtime_path is not None and Path(runtime_path).exists():
        logger.debug("Using runtime DLLs from the requested path: %s", runtime_path)
        return Path(runtime_path)

    # Check default user path
    default_path = get_default_runtime_path()
    if default_path.exists() and check_runtimes_present(default_path):
        logger.debug("Using runtime DLLs from the default path: %s", default_path)
        return default_path

    # Try to download
    logger.debug("Runtime DLLs not found locally; starting download")
    print("Thermo RawFileReader runtime DLLs not found.")
    print("Downloading from GitHub...")
    return download_runtimes()
