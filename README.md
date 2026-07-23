# thermo-raw-file-reader

Python wrapper for Thermo Fisher Scientific RawFileReader library, enabling reading of `.raw` mass spectrometry files in Python on Windows, Linux, and MacOS.

## Overview

This package provides a Pythonic interface to the official [Thermo RawFileReader](https://github.com/thermofisherlsms/RawFileReader) .NET library. It allows you to:

- Read Thermo Scientific `.raw` mass spectrometry files
- Extract spectra (centroid and profile data)
- Extract chromatograms (TIC, Base Peak, EIC/XIC)
- Access file metadata (sample info, instrument details, run headers)
- Get scan filters and trailer extra data
- Average scans across a range

## Installation

### Requirements

- Python 3.12+
- UV package manager ([install instructions](https://docs.astral.sh/uv/getting-started/installation/))
- .NET runtime:
  - **Linux/macOS**: Mono runtime OR .NET 8 SDK/Runtime
    - Mono: `sudo apt-get install mono-runtime` (Ubuntu/Debian)
    - .NET 8: Download from [Microsoft](https://dotnet.microsoft.com/download)
  - **Windows**: .NET 8 Runtime

### Quick Install (Users)

```bash
pip install thermo-raw-file-reader
```

### Developer Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/epyraw.git
cd epyraw

# Create virtual environment with UV
uv venv

# Activate the virtual environment
# Linux/macOS:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# Install in editable mode with development dependencies
uv pip install -e ".[dev]"

# Verify installation
pytest
```

### Development Dependencies

The `[dev]` extra includes:
- `pytest>=7.0.0` - Testing framework
- `pytest-cov>=4.0.0` - Test coverage reporting
- `mypy>=1.0.0` - Static type checking

## Quick Start

```python
from thermo_raw_file_reader import RawFile, Device

# Open a RAW file using context manager
with RawFile("data.raw") as rf:
    # Select the MS instrument
    rf.select_instrument(Device.MS, 1)

    # Get file information
    print(f"File: {rf.filename}")
    print(f"Scans: {rf.run_header.spectra_count}")
    print(f"Time range: {rf.run_header.time_range}")

    # Get a spectrum
    spectrum = rf.get_spectrum(100, centroid=True)
    print(f"Peaks: {spectrum.num_peaks}")
    print(f"Base peak: {spectrum.base_peak}")

    # Get base peak chromatogram
    chrom = rf.get_chromatogram()
    print(f"Chromatogram points: {chrom.num_points}")
```

## API Reference

### RawFile Class

The main class for reading RAW files.

#### Constructor

```python
RawFile(filepath: str | Path)
```

Opens a RAW file for reading. Uses context manager pattern for automatic resource cleanup.

#### Properties

| Property | Type | Description |
|----------|------|-------------|
| `filepath` | str | Full path to the file |
| `filename` | str | File name only |
| `is_open` | bool | Whether file is open |
| `is_error` | bool | Whether file has errors |
| `file_error` | str | Error message if any |
| `instrument_count` | int | Number of instruments |
| `file_header` | FileHeader | File header information |
| `run_header` | RunHeader | Run header information |
| `sample_information` | SampleInformation | Sample metadata |

#### Methods

| Method | Description |
|--------|-------------|
| `select_instrument(device, instance)` | Select an instrument for operations |
| `get_instrument_data()` | Get current instrument details |
| `get_filters()` | List all unique filter strings |
| `get_filter_for_scan_number(scan)` | Get filter for a specific scan |
| `retention_time_from_scan_number(scan)` | Convert scan to retention time |
| `scan_number_from_retention_time(rt)` | Convert retention time to scan |
| `get_spectrum(scan, centroid=True)` | Get spectrum data |
| `get_chromatogram(trace_type, start, end)` | Get chromatogram data |
| `average_scans(range, tolerance, units)` | Average spectra in a range |
| `get_trailer_extra_information(scan)` | Get trailer extra fields |
| `get_status_log_header_information()` | Get status log field definitions |
| `get_inclusion_exclusion_list()` | Get inclusion/exclusion list |
| `close()` | Close the file |

### Data Models

#### Spectrum

```python
@dataclass
class Spectrum:
    masses: np.ndarray       # m/z values
    intensities: np.ndarray  # intensity values
    charges: np.ndarray | None  # charge states (centroid only)
    scan_number: int
    is_centroid: bool
    
    # Properties
    num_peaks: int
    mass_range: tuple[float, float]
    intensity_range: tuple[float, float]
    base_peak: tuple[float, float]  # (m/z, intensity)
    total_ion_current: float
```

#### Chromatogram

```python
@dataclass
class Chromatogram:
    times: np.ndarray        # retention times (minutes)
    intensities: np.ndarray  # intensity values
    trace_type: int
    mass_range: tuple | None
    
    # Properties
    num_points: int
    time_range: tuple[float, float]
    base_peak_time: float
    base_peak_intensity: float
    total_ion_current: float
```

#### RunHeader

```python
@dataclass
class RunHeader:
    first_spectrum: int
    last_spectrum: int
    start_time: float
    end_time: float
    low_mass: float
    high_mass: float
    mass_resolution: float
    spectra_count: int
    max_intensity: float
    # ... and more
```

### Enums

Common enum types for filtering and selection:

- `Device`: Instrument types (MS, Analog, PDA, UV, etc.)
- `TraceType`: Chromatogram types (BasePeak, TIC, A2DChannel, etc.)
- `ToleranceUnits`: Mass tolerance units (Daltons, ppm)
- `MSOrderType`: MS order (MS, MS2, MS3, etc.)
- `IonizationMode`: Ionization mode (Positive, Negative)
- `PolarityType`: Polarity (Positive, Negative)
- `MassAnalyzerType`: Analyzer type (Orbitrap, TOF, IonTrap, etc.)

### Runtime Configuration

By default, the package attempts to use Mono runtime on Linux/macOS. You can explicitly configure the runtime:

```python
from thermo_raw_file_reader import set_runtime, RawFile

# Use Mono runtime (default on Linux/macOS)
set_runtime("mono")

# Or use .NET Core/.NET 5+ runtime
set_runtime("coreclr")

# Or let pythonnet detect automatically
set_runtime("default")

# Now open files normally
with RawFile("data.raw") as rf:
    pass
```

**Note:** `set_runtime()` must be called before opening any files.

## Examples

See the `examples/` directory for more usage examples:

- `basic_usage.py`: Basic file reading operations
- `extract_spectra.py`: Extract all spectra to NumPy arrays

Run examples:

```bash
python examples/basic_usage.py path/to/file.raw
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=thermo_raw_file_reader --cov-report=html

# Run specific test file
pytest tests/test_models.py -v

# Run specific test
pytest tests/test_raw_file.py::TestSpectrumMethods::test_get_spectrum_centroid -v
```

### Type Checking

```bash
# Run mypy for static type checking
mypy src/thermo_raw_file_reader
```

### Project Structure

```
epyraw/
├── pyproject.toml              # UV build configuration
├── README.md                   # This file
├── src/thermo_raw_file_reader/
│   ├── __init__.py             # Public API exports
│   ├── enums.py                # Enum types (Device, TraceType, etc.)
│   ├── exceptions.py           # Custom exceptions
│   ├── models.py               # Data models (Spectrum, Chromatogram, etc.)
│   ├── raw_file.py             # Main RawFile class
│   └── runtimes/net8old/       # Bundled .NET DLL assemblies
├── tests/
│   ├── conftest.py             # Pytest fixtures
│   ├── test_models.py          # Unit tests for data models
│   └── test_raw_file.py        # Integration tests
└── examples/
    ├── basic_usage.py          # Basic usage demonstration
    └── extract_spectra.py      # Extract all spectra example
```

## Limitations

- **Writing support**: This package currently only supports reading RAW files
- **Platform features**: Some Microsoft-specific features may not work on Linux/macOS due to unported dependencies
- **Mono compatibility**: For best results on Linux/macOS, consider using .NET Core runtime instead of Mono

## License

This wrapper is provided under an MIT license. The Thermo RawFileReader libraries are subject to Thermo Fisher's terms of use.

## Acknowledgments

- [Thermo Fisher Scientific](https://www.thermofisher.com) for providing the RawFileReader library
- [pythonnet](https://pythonnet.github.io/) for the Python-.NET integration

## References

- [RawFileReader GitHub](https://github.com/thermofisherlsms/RawFileReader)
- [RawFileReader NuGet Packages](https://www.nuget.org/packages?q=ThermoFisher.CommonCore.RawFileReader)
