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

`get_trailer_extra_information(scan)` returns the trailer-extra fields of a
scan as display strings — exactly the text the instrument software would
show (`'55.000'`, `'On'`, ...). It needs a selected mass-spectrometer
instrument; without one it raises `RuntimeError` (the typed accessors below
raise `InstrumentNotSelectedError` instead).

```python
with RawFile("data.raw") as rf:
    trailer = rf.get_trailer_extra_information(scan_number=100)
    
    for field, value in trailer.items():
        print(f"{field}: {value}")
```

### Typed Trailer Extra Values

`trailer_extra_fields` describes the trailer-extra columns of the file, and
`get_trailer_extra_values(scan)` returns one scan's values as Python objects
whose types come from the file's own data-type descriptions — full stored
precision, not display text:

```python
from epyraw import RawFile, Device

with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)

    fields = rf.trailer_extra_fields            # one HeaderField per column
    values = rf.get_trailer_extra_values(100)   # labels -> typed values

    print(values["Ion Injection Time (ms):"])  # 54.999999701976776
    print(values["AGC:"])                      # True — a bool, not 'On'
```

- Numbers arrive at stored precision: `54.999999701976776` where the string
  accessor shows `'55.000'`, `1.399999976158142` where it shows `'1.40'`. Much of
  this reaches Python through single precision, so compare with a tolerance —
  `values['MS2 Isolation Width:'] == 1.4` is `False`.
- Types follow each field's own data type in the file, never its text. On the
  bundled `sample.raw`: `'FT Resolution:'` and `'Charge State:'` are stored as
  integers (`LONG`) and arrive widened to `float` (`30000.0`, `2.0`);
  `'HCD Energy:'` is `CHAR_STRING` and stays the string `'28.00'` even though
  it looks numeric; `'AGC:'` is `ONOFF` and arrives as the bool `True`, while
  `get_trailer_extra_information()` renders the same field as `'On'`.
- Real zeros survive: `0`, `0.0` and `False` are kept (no truthiness filtering),
  and text values are verbatim — `'IT=55 '` keeps its trailing space.
- Section-header rows such as `'=== Mass Calibration: ===:'` are included with
  value `None`; they are structure, not channels. Filter
  `rf.trailer_extra_fields` on `is_numeric` to iterate only numeric channels.
- `HeaderField.unit` is text parsed from the label (`'Ion Injection Time
  (ms):'` → `'ms'`); the raw file format stores no machine-readable unit, so
  labels without a parenthetical report `''`.
- The number and order of columns is instrument-specific — 62 fields were
  measured on the Q Exactive HF-X fixture, 68 on an Orbitrap Exploris, 58 on
  the Zenodo QC file — so identify fields by `label`, never by position.
- `get_trailer_extra_values` raises `InvalidScanNumberError` for a scan outside
  the run and `InstrumentNotSelectedError` when no file is open or no
  instrument is selected. `get_trailer_extra_information()` is unchanged and
  remains the way to get the display strings.
