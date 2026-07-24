# epyraw

Python wrapper for Thermo Fisher RawFileReader library - read .raw mass spectrometry files in Python.

## Features

- Read Thermo Scientific .raw mass spectrometry files
- Access spectrum and chromatogram data
- Extract scan metadata and statistics
- Support for MS1 and MSn scans
- Cross-platform (Windows, Linux, macOS)

## Quick Start

```python
from epyraw import RawFile, Device

with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    
    # Get run information
    print(f"Scans: {rf.run_header.spectra_count}")
    
    # Get a spectrum
    spectrum = rf.get_spectrum(100)
    print(f"Peaks: {spectrum.num_peaks}")
    
    # Get chromatogram
    tic = rf.get_chromatogram()
    print(f"Time range: {tic.time_range}")
```

## Installation

```bash
pip install epyraw
```

See [Installation](installation.md) for detailed instructions.

## Documentation

- [Installation Guide](installation.md)
- [Usage Examples](usage.md)
- [API Reference](api/raw_file.md)
- [Examples](examples.md)

## License

MIT License - see [LICENSE](https://github.com/hechth/epyraw/blob/main/LICENSE) for details.
