"""Data models for Thermo RawFile Reader.

These classes provide Pythonic data structures for representing
spectrum, chromatogram, and other mass spectrometry data.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Spectrum:
    """Mass spectrum data.

    Represents a single mass spectrum with mass-to-charge ratios
    and corresponding intensities.
    """

    masses: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    """Array of m/z values."""

    intensities: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=np.float64)
    )
    """Array of intensity values."""

    charges: np.ndarray | None = None
    """Array of charge states (only for centroid/label data)."""

    scan_number: int = 0
    """The scan number this spectrum corresponds to."""

    is_centroid: bool = True
    """Whether this is centroid (peak list) or profile data."""

    @property
    def num_peaks(self) -> int:
        """Number of peaks in the spectrum."""
        return len(self.masses)

    @property
    def mass_range(self) -> tuple[float, float]:
        """Return the mass range (min, max)."""
        if self.num_peaks == 0:
            return (0.0, 0.0)
        return (float(self.masses.min()), float(self.masses.max()))

    @property
    def intensity_range(self) -> tuple[float, float]:
        """Return the intensity range (min, max)."""
        if self.num_peaks == 0:
            return (0.0, 0.0)
        return (float(self.intensities.min()), float(self.intensities.max()))

    @property
    def base_peak(self) -> tuple[float, float]:
        """Return the base peak as (m/z, intensity)."""
        if self.num_peaks == 0:
            return (0.0, 0.0)
        idx = int(np.argmax(self.intensities))
        return (float(self.masses[idx]), float(self.intensities[idx]))

    @property
    def total_ion_current(self) -> float:
        """Return the total ion current (sum of all intensities)."""
        return float(np.sum(self.intensities))

    def to_pandas(self) -> pd.DataFrame:
        """Convert to pandas DataFrame.

        Returns:
            DataFrame with columns 'mass', 'intensity', and optionally 'charge'.
        """
        data = {"mass": self.masses, "intensity": self.intensities}
        if self.charges is not None:
            data["charge"] = self.charges

        df = pd.DataFrame(data)
        if self.scan_number > 0:
            df["scan_number"] = self.scan_number

        return df

    def __len__(self) -> int:
        """Return the number of peaks."""
        return self.num_peaks

    def __repr__(self) -> str:
        """Return a string representation."""
        return (
            f"Spectrum(scan={self.scan_number}, peaks={self.num_peaks}, "
            f"m/z={self.mass_range[0]:.2f}-{self.mass_range[1]:.2f}, "
            f"centroid={self.is_centroid})"
        )


@dataclass
class Chromatogram:
    """Chromatogram data.

    Represents a chromatographic trace with retention times
    and corresponding intensities.
    """

    times: np.ndarray = field(default_factory=lambda: np.array([], dtype=np.float64))
    """Array of retention times (in minutes)."""

    intensities: np.ndarray = field(
        default_factory=lambda: np.array([], dtype=np.float64)
    )
    """Array of intensity values."""

    trace_type: int = 0
    """Type of chromatogram (TraceType enum value)."""

    mass_range: tuple[float, float] | None = None
    """Mass range used for extracted ion chromatograms."""

    @property
    def num_points(self) -> int:
        """Number of points in the chromatogram."""
        return len(self.times)

    @property
    def time_range(self) -> tuple[float, float]:
        """Return the time range (start, end) in minutes."""
        if self.num_points == 0:
            return (0.0, 0.0)
        return (float(self.times.min()), float(self.times.max()))

    @property
    def intensity_range(self) -> tuple[float, float]:
        """Return the intensity range (min, max)."""
        if self.num_points == 0:
            return (0.0, 0.0)
        return (float(self.intensities.min()), float(self.intensities.max()))

    @property
    def base_peak_time(self) -> float:
        """Return the retention time of the base peak."""
        if self.num_points == 0:
            return 0.0
        idx = int(np.argmax(self.intensities))
        return float(self.times[idx])

    @property
    def base_peak_intensity(self) -> float:
        """Return the intensity of the base peak."""
        if self.num_points == 0:
            return 0.0
        return float(np.max(self.intensities))

    @property
    def total_ion_current(self) -> float:
        """Return the total ion current (integral of intensities)."""
        if self.num_points < 2:
            return 0.0
        # Simple trapezoidal integration
        return float(np.trapz(self.intensities, self.times))

    def to_pandas(self) -> pd.DataFrame:
        """Convert to pandas DataFrame.

        Returns:
            DataFrame with columns 'time' and 'intensity'.
        """
        return pd.DataFrame({"time": self.times, "intensity": self.intensities})

    def __len__(self) -> int:
        """Return the number of points."""
        return self.num_points

    def __repr__(self) -> str:
        """Return a string representation."""
        mass_range_str = ""
        if self.mass_range is not None:
            mass_range_str = f", m/z={self.mass_range[0]:.2f}-{self.mass_range[1]:.2f}"

        return (
            f"Chromatogram(points={self.num_points}, time={self.time_range[0]:.2f}-"
            f"{self.time_range[1]:.2f} min{mass_range_str})"
        )


@dataclass
class ScanFilter:
    """Scan filter information.

    Contains metadata about how a scan was acquired.
    """

    filter_string: str = ""
    """Raw filter string from the file."""

    ms_order: int = 0
    """MS order (MSOrderType enum value)."""

    ionization_mode: int = 0
    """Ionization mode (IonizationMode enum value)."""

    polarity: int = 0
    """Polarity (PolarityType enum value)."""

    mass_analyzer: int = 0
    """Mass analyzer type (MassAnalyzerType enum value)."""

    detector_type: int = 0
    """Detector type (DetectorType enum value)."""

    precursor_mass: float | None = None
    """Precursor mass for MS/MS scans."""

    collision_energy: float | None = None
    """Collision energy for MS/MS scans."""

    isolation_width: float | None = None
    """Isolation width for MS/MS scans."""

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"ScanFilter({self.filter_string})"


@dataclass
class FileHeader:
    """File header information."""

    revision: str = ""
    """File format revision."""

    creation_date: str = ""
    """File creation date/time."""

    who_created_id: str = ""
    """Operator/user who created the file."""

    file_description: str = ""
    """File description."""

    def __repr__(self) -> str:
        """Return a string representation."""
        return (
            f"FileHeader(created={self.creation_date}, operator={self.who_created_id})"
        )


@dataclass
class RunHeader:
    """Run header information."""

    first_spectrum: int = 0
    """First scan number (typically 1)."""

    last_spectrum: int = 0
    """Last scan number."""

    start_time: float = 0.0
    """Start time in minutes."""

    end_time: float = 0.0
    """End time in minutes."""

    low_mass: float = 0.0
    """Lowest recorded mass."""

    high_mass: float = 0.0
    """Highest recorded mass."""

    mass_resolution: float = 0.0
    """Instrument mass resolution."""

    spectra_count: int = 0
    """Total number of spectra/scans."""

    max_intensity: float = 0.0
    """Maximum intensity across all scans."""

    max_integrated_intensity: float = 0.0
    """Maximum integrated intensity."""

    comment1: str = ""
    """First comment field."""

    comment2: str = ""
    """Second comment field."""

    @property
    def scan_range(self) -> tuple[int, int]:
        """Return the scan range."""
        return (self.first_spectrum, self.last_spectrum)

    @property
    def time_range(self) -> tuple[float, float]:
        """Return the time range in minutes."""
        return (self.start_time, self.end_time)

    @property
    def duration(self) -> float:
        """Return the run duration in minutes."""
        return self.end_time - self.start_time

    def __repr__(self) -> str:
        """Return a string representation."""
        return (
            f"RunHeader(scans={self.first_spectrum}-{self.last_spectrum}, "
            f"time={self.start_time:.2f}-{self.end_time:.2f} min, "
            f"count={self.spectra_count})"
        )


@dataclass
class SampleInformation:
    """Sample metadata."""

    sample_name: str = ""
    """Sample name."""

    sample_id: str = ""
    """Sample ID."""

    sample_type: int = 0
    """Sample type (SampleType enum value)."""

    comment: str = ""
    """Sample comment."""

    vial: int = 0
    """Vial position."""

    sample_volume: float = 0.0
    """Sample volume."""

    injection_volume: float = 0.0
    """Injection volume."""

    row_number: int = 0
    """Row number in sequence."""

    dilution_factor: float = 0.0
    """Dilution factor."""

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"SampleInformation(name={self.sample_name}, id={self.sample_id})"


@dataclass
class InstrumentData:
    """Instrument identification data."""

    model: str = ""
    """Instrument model."""

    name: str = ""
    """Instrument name."""

    serial_number: str = ""
    """Instrument serial number."""

    software_version: str = ""
    """Software version."""

    hardware_version: str = ""
    """Firmware/hardware version."""

    units: str = ""
    """Units setting."""

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"InstrumentData(model={self.model}, serial={self.serial_number})"


@dataclass
class InclusionListItem:
    """Inclusion/exclusion list item."""

    mass: float = 0.0
    """Mass value."""

    threshold: float = 0.0
    """Threshold value (intensity or other)."""

    scan_number: int = 0
    """Associated scan number."""

    descriptor: str = ""
    """Compound name or descriptor."""

    is_exclusion: bool = False
    """Whether this is an exclusion item."""

    def __repr__(self) -> str:
        """Return a string representation."""
        type_str = "exclusion" if self.is_exclusion else "inclusion"
        return f"InclusionItem({type_str}: {self.descriptor} @ {self.mass:.4f} Da)"


@dataclass
class StatusLogField:
    """Status log field definition."""

    label: str = ""
    """Field label/name."""

    data_type: int = 0
    """Data type (GenericDataTypes enum value)."""

    def __repr__(self) -> str:
        """Return a string representation."""
        return f"StatusLogField({self.label})"
