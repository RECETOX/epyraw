# Usage Guide

## Basic Usage

### Opening a File

```python
from epyraw import RawFile, Device

# Using context manager (recommended)
with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    # ... your code here ...
# File is automatically closed
```

### Getting File Information

```python
with RawFile("data.raw") as rf:
    # File header
    print(f"Created: {rf.file_header.creation_date}")
    print(f"Operator: {rf.file_header.who_created_id}")
    
    # Run header
    rh = rf.run_header
    print(f"Scans: {rh.spectra_count}")
    print(f"Duration: {rh.duration:.2f} minutes")
    print(f"Mass range: {rh.low_mass:.2f} - {rh.high_mass:.2f} Da")
    
    # Sample information
    si = rf.sample_information
    print(f"Sample: {si.sample_name}")
```

## Working with Spectra

### Getting a Spectrum

```python
with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    
    # Get centroid spectrum
    spectrum = rf.get_spectrum(scan_number=100, centroid=True)
    
    print(f"Scan: {spectrum.scan_number}")
    print(f"Peaks: {spectrum.num_peaks}")
    print(f"Mass range: {spectrum.mass_range}")
    print(f"Base peak: {spectrum.base_peak}")  # (m/z, intensity)
    print(f"TIC: {spectrum.total_ion_current}")
    
    # Access data arrays
    masses = spectrum.masses      # numpy array
    intensities = spectrum.intensities  # numpy array
```

### Converting to DataFrame

```python
import pandas as pd

with RawFile("data.raw") as rf:
    spectrum = rf.get_spectrum(100)
    df = spectrum.to_pandas()
    
    # Filter peaks above threshold
    high_intensity = df[df['intensity'] > 1e5]
```

## Working with Chromatograms

### Getting Chromatograms

```python
from epyraw import TraceType

with RawFile("data.raw") as rf:
    # Total Ion Chromatogram
    tic = rf.get_chromatogram(trace_type=TraceType.TIC)
    
    # Base Peak Chromatogram
    bpc = rf.get_chromatogram(trace_type=TraceType.BasePeak)
    
    print(f"TIC points: {tic.num_points}")
    print(f"Time range: {tic.time_range}")
    print(f"Base peak time: {bpc.base_peak_time:.2f} min")
```

### Converting to DataFrame

```python
with RawFile("data.raw") as rf:
    tic = rf.get_chromatogram(TraceType.TIC)
    df = tic.to_pandas()
    
    # Plot with matplotlib
    import matplotlib.pyplot as plt
    
    plt.plot(df['time'], df['intensity'])
    plt.xlabel('Retention Time (min)')
    plt.ylabel('Intensity')
    plt.show()
```

## Scan Metadata

### Scan Header

```python
with RawFile("data.raw") as rf:
    header = rf.get_scan_header(scan_number=100)
    
    print(f"MS Level: {header.ms_level}")
    print(f"Scan Type: {header.scan_type}")
    print(f"Ions: {header.number_of_ions}")
    print(f"Trigger Time: {header.trigger_time:.2f} min")
```

### Scan Statistics

```python
with RawFile("data.raw") as rf:
    stats = rf.get_scan_stats(scan_number=100)
    
    print(f"Centroid: {stats.is_centroid_scan}")
    print(f"Peak count: {stats.mass_count}")
    print(f"Max intensity: {stats.max_intensity:.2e}")
```

### Scan Events (MSn)

```python
with RawFile("data.raw") as rf:
    event = rf.get_scan_event(scan_number=150)
    
    for reaction in event.reactions:
        print(f"Precursor: {reaction.precursor_mass:.4f} Da")
        print(f"Collision Energy: {reaction.collision_energy:.1f} eV")
```

## Iterating Over Scans

```python
with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    
    rh = rf.run_header
    
    for scan_num in range(rh.first_spectrum, rh.last_spectrum + 1):
        spectrum = rf.get_spectrum(scan_num)
        
        # Process each spectrum
        if spectrum.num_peaks > 0:
            base_mz = spectrum.base_peak[0]
            print(f"Scan {scan_num}: Base peak at {base_mz:.4f} m/z")
```

## Advanced Features

### Autosampler Information

```python
with RawFile("data.raw") as rf:
    auto_info = rf.auto_sampler_information
    
    print(f"Tray: {auto_info.tray_index}")
    print(f"Vial: {auto_info.vial_index}")
    print(f"Shape: {auto_info.tray_shape}")
```

### Instrument Method

```python
with RawFile("data.raw") as rf:
    if rf.has_instrument_method:
        names = rf.get_all_instrument_friendly_names_from_method()
        print(f"Instruments: {names}")
```

### Trailer Extra Information

```python
with RawFile("data.raw") as rf:
    trailer = rf.get_trailer_extra_information(scan_number=100)
    
    for field, value in trailer.items():
        print(f"{field}: {value}")
```
