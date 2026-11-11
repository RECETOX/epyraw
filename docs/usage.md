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

## Instrument Status Log

The status log is what the instrument reported about *itself* while the file was
acquired: temperatures, spray voltage and current, gas flows, vacuum pressures,
turbo-pump speeds. It is not per-scan data. Rows are written on their own cadence
and are sparse - `tests/testdata/sample.raw` has 5 status-log rows against 574
scans - so joining status-log values to scans is a nearest-in-time operation that
you perform yourself.

### Field Definitions

```python
with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)

    fields = rf.status_log_fields
    print(f"{len(fields)} fields, {rf.status_log_count} logged entries")

    for field in fields:
        if field.is_numeric:
            print(f"{field.label} [{field.unit}]")
```

`status_log_fields` describes the columns. `is_numeric` separates the measured
channels from the rows that only structure the log - section titles such as
`'======  Ion Source:  ======:'` and text such as `'Status:'` - which stay on
`fields` but are not channels.

`unit` is parsed from the **text of the label**, because the format stores no
machine-readable unit: `'Capillary Temperature (°C)'` gives `'°C'`, while a channel
whose label states nothing, such as `'Sheath gas flow rate'`, gives `''`. Only a
parenthetical at the very end of a label is read as a unit.

### The Whole Log as a Table

```python
with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)

    log = rf.get_status_log()
    print(len(log.channels), "channels:", log.channels[:3])

    frame = log.to_pandas()
    print(frame.shape)
    print(frame[["time", "Capillary Temperature (°C)"]])
```

`to_pandas()` returns `time` (minutes) as a column followed by one column per
numeric channel, in file order - the same shape `Chromatogram.to_pandas()` uses, so
time is *not* the index. Rows are neither sorted nor deduplicated, so an unfiltered
read always returns `status_log_count` rows. Values the file left empty become
`NaN`.

Pass a time window to read part of the log; both bounds are inclusive and either
one is optional:

```python
with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)

    window = rf.get_status_log(start_time=0.1, end_time=0.51)
    print(len(window), "of", rf.status_log_count, "rows")
```

### Single Entries and Single Channels

```python
with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)

    entry = rf.get_status_log_entry(0)
    print(entry.time, entry.values["Spray Voltage (V)"])

    # Nearest entry to a retention time (in minutes)
    nearest = rf.get_status_log_at_time(0.62)
    print(nearest.time)

    # One channel over the whole log
    times, spray = rf.get_status_log_channel("Spray Voltage (V)")
    print(times[-1], spray[-1])
```

`get_status_log_at_time()` clamps to the first or last row when the time is outside
the logged range instead of raising, so check `entry.time` if you need to know.

### Which Instrument Stream

The status log belongs to one instrument stream. Every accessor needs a selected
instrument and raises `InstrumentNotSelectedError` without one; if the stream you
selected has no status log, the other streams are searched for you, and your own
selection is restored afterwards. To see where the log actually lives:

```python
with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)

    print(rf.status_log_streams())
```

`get_status_log()` describes one stream - one set of field definitions is one
rectangular table - so streams are never merged into a single frame.

### Things to Know

- **Look channels up by label, never by position.** Which labels exist, in which
  order and how many there are depends on the instrument model, its firmware and
  its instrument method. `tests/testdata/sample.raw` (Q Exactive HF-X) has 46
  numeric channels including `'Capillary Temperature (°C)'`; the QC sample of
  [Zenodo record 6878356](https://zenodo.org/records/6878356) (Q Exactive GC) has
  54, has `'MS transfer line temp (°C)'` and no `'Capillary Temperature (°C)'`.
- **Labels are verbatim file text** and may contain `°` and `µ`
  (`'Spray Current (µA)'`). They are the key for `entry.values` and
  `get_status_log_channel()`; nothing is normalised.
- **Times are in minutes**, like retention times elsewhere in the library, and the
  log stores them in single precision.
- **Values keep the precision the file stores.** The upstream single-channel API
  (`StatusLogPlottableData` with `GetStatusLogAtPosition`) hands back
  display-formatted strings - `'2515.9'` where the value is
  `2515.897091586047` - so `epyraw` does not use it.
- **A row's text fields are strings, structure rows are `None`:**
  `entry.values['Status:']` is e.g. `'Instrument status Ok'` and
  `entry.values['======  Ion Source:  ======:']` is `None`.

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
