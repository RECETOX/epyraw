# Examples

## Basic Spectrum Analysis

```python
from epyraw import RawFile, Device
import matplotlib.pyplot as plt

with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    
    # Get a spectrum
    spectrum = rf.get_spectrum(100)
    
    # Plot the spectrum
    plt.figure(figsize=(10, 6))
    plt.plot(spectrum.masses, spectrum.intensities, 'b-')
    plt.xlabel('m/z')
    plt.ylabel('Intensity')
    plt.title(f'Scan {spectrum.scan_number}')
    plt.show()
```

## Total Ion Chromatogram

```python
from epyraw import RawFile, Device, TraceType
import matplotlib.pyplot as plt

with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    
    # Get TIC
    tic = rf.get_chromatogram(TraceType.TIC)
    
    # Plot
    plt.figure(figsize=(12, 5))
    plt.plot(tic.times, tic.intensities, 'g-')
    plt.xlabel('Retention Time (min)')
    plt.ylabel('Total Ion Current')
    plt.title('Total Ion Chromatogram')
    plt.tight_layout()
    plt.show()
```

## Extracting All Spectra

```python
from epyraw import RawFile, Device
import pandas as pd

all_spectra = []

with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    
    rh = rf.run_header
    
    for scan_num in range(rh.first_spectrum, rh.last_spectrum + 1):
        spectrum = rf.get_spectrum(scan_num)
        
        all_spectra.append({
            'scan': scan_num,
            'peaks': spectrum.num_peaks,
            'tic': spectrum.total_ion_current,
            'base_mz': spectrum.base_peak[0],
            'base_intensity': spectrum.base_peak[1]
        })

# Convert to DataFrame
df = pd.DataFrame(all_spectra)
df.to_csv("spectrum_summary.csv", index=False)
```

## Finding Base Peak Across Run

```python
from epyraw import RawFile, Device

with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    
    rh = rf.run_header
    max_intensity = 0
    base_peak_info = None
    
    for scan_num in range(rh.first_spectrum, rh.last_spectrum + 1):
        spectrum = rf.get_spectrum(scan_num)
        
        if spectrum.num_peaks > 0:
            mz, intensity = spectrum.base_peak
            if intensity > max_intensity:
                max_intensity = intensity
                base_peak_info = (scan_num, mz, intensity)
    
    if base_peak_info:
        scan, mz, intensity = base_peak_info
        print(f"Global base peak:")
        print(f"  Scan: {scan}")
        print(f"  m/z: {mz:.4f}")
        print(f"  Intensity: {intensity:.2e}")
```

## MS2 Scan Analysis

```python
from epyraw import RawFile, Device

with RawFile("data.raw") as rf:
    rf.select_instrument(Device.MS, 1)
    
    rh = rf.run_header
    ms2_scans = []
    
    for scan_num in range(rh.first_spectrum, rh.last_spectrum + 1):
        header = rf.get_scan_header(scan_num)
        
        if header.ms_level >= 2:
            event = rf.get_scan_event(scan_num)
            
            for reaction in event.reactions:
                ms2_scans.append({
                    'scan': scan_num,
                    'precursor_mz': reaction.precursor_mass,
                    'collision_energy': reaction.collision_energy
                })

print(f"Found {len(ms2_scans)} MS2 scans")
```

## Comparing Multiple Files

```python
from epyraw import RawFile, Device
import pandas as pd

files = ["sample1.raw", "sample2.raw", "sample3.raw"]
results = []

for filepath in files:
    with RawFile(filepath) as rf:
        rf.select_instrument(Device.MS, 1)
        
        rh = rf.run_header
        si = rf.sample_information
        
        results.append({
            'file': filepath,
            'sample': si.sample_name,
            'scans': rh.spectra_count,
            'duration': rh.duration,
            'max_intensity': rh.max_intensity
        })

df = pd.DataFrame(results)
print(df)
```
