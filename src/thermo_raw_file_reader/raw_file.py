"""Main RawFile class for reading Thermo .raw files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

from .enums import Device, ToleranceUnits, TraceType
from .exceptions import (
    AssemblyLoadError,
    InitializationError,
    InstrumentNotSelectedError,
    InvalidScanNumberError,
    RawFileCorruptedError,
    RawFileNotFoundError,
    RawFileOpenError,
)
from .models import (
    Chromatogram,
    FileHeader,
    InclusionListItem,
    InstrumentData,
    RunHeader,
    SampleInformation,
    ScanFilter,
    Spectrum,
    StatusLogField,
)

if TYPE_CHECKING:
    import numpy as np


# Module-level state for .NET initialization
_dotnet_initialized: bool = False
_raw_file_class: Any = None
_centroid_stream_class: Any = None
_segmented_scan_class: Any = None
_chromatogram_settings_class: Any = None
_chromatogram_signal_class: Any = None
_scan_class: Any = None
_filter_class: Any = None
_device_class: Any = None


def _get_assembly_path() -> Path:
    """Get the path to the .NET assemblies."""
    package_dir = Path(__file__).parent
    return package_dir / "runtimes" / "net8old"


def set_runtime(runtime: str) -> None:
    """Configure the .NET runtime to use.

    This function must be called before opening any RawFile instances.
    Once a RawFile is opened, changing the runtime has no effect.

    Args:
        runtime: The runtime to use. Options are:
            - "mono": Use Mono runtime (default on Linux/macOS)
            - "coreclr": Use .NET Core/.NET 5+ runtime
            - "netfx": Use .NET Framework (Windows only)
            - "default": Use pythonnet's default runtime detection

    Example:
        >>> from thermo_raw_file_reader import set_runtime, RawFile
        >>> set_runtime("mono")  # or "coreclr"
        >>> with RawFile("data.raw") as rf:
        ...     pass
    """
    global _dotnet_initialized

    if _dotnet_initialized:
        raise InitializationError(
            "Runtime cannot be changed after RawFile has been initialized. "
            "Call set_runtime() before opening any files."
        )

    try:
        from pythonnet import set_runtime as set_pythonnet_runtime
        set_pythonnet_runtime(runtime)
    except ImportError as e:
        raise InitializationError(
            "pythonnet not found. Install it with: pip install pythonnet"
        ) from e
    except Exception as e:
        raise InitializationError(
            f"Failed to set runtime to '{runtime}': {e}"
        ) from e


def _initialize_dotnet(runtime: str | None = None) -> None:
    """Initialize the .NET runtime and load assemblies.

    This function should be called once before using any RawFile functionality.
    It attempts to configure an appropriate .NET runtime, with Mono as the
    default on Linux/macOS systems and CoreCLR as an alternative.

    Args:
        runtime: Optional explicit runtime choice. If None, uses default detection
                 with fallback strategy.
    """
    global _dotnet_initialized, _raw_file_class
    global _centroid_stream_class, _segmented_scan_class
    global _chromatogram_settings_class, _chromatogram_signal_class
    global _scan_class, _filter_class, _device_class

    if _dotnet_initialized:
        return

    try:
        import clr
    except ImportError as e:
        raise InitializationError(
            "pythonnet not found. Install it with: pip install pythonnet"
        ) from e

    # Runtime selection strategy:
    # 1. If explicitly specified, use that runtime
    # 2. Otherwise, try the configured/default runtime first
    # 3. Fall back to alternatives if needed
    runtime_order = []

    if runtime:
        # Explicit runtime requested
        runtime_order = [runtime]
    else:
        # Default strategy: try mono first (pre-installed on many Linux systems),
        # then fall back to coreclr
        runtime_order = ["mono", "coreclr", "default"]

    last_error: Exception | None = None

    for rt in runtime_order:
        try:
            if rt != "default":
                from pythonnet import set_runtime as set_pythonnet_runtime
                set_pythonnet_runtime(rt)
            # Attempt to trigger runtime loading
            import sys
            if 'clr' in sys.modules:
                break
        except Exception as e:
            last_error = e
            continue

    if last_error and 'clr' not in sys.modules:
        # If all attempts failed, try one more time without explicit setting
        # to let pythonnet use its built-in detection
        try:
            import sys
            if 'clr' not in sys.modules:
                # Force reload to trigger default detection
                pass
        except Exception:
            pass

    # Get assembly path - check both package location and runtimes directory
    assembly_path = _get_assembly_path()

    # If not found in package, check relative to this file's parent
    if not assembly_path.exists():
        # Try alternative locations
        alt_paths = [
            Path(__file__).parent.parent / "runtimes" / "net8old",
            Path("/usr/share/thermo-raw-file-reader/runtimes/net8old"),
        ]
        for alt_path in alt_paths:
            if alt_path.exists():
                assembly_path = alt_path
                break

    if not assembly_path.exists():
        raise AssemblyLoadError(
            f"Assemblies not found at {assembly_path}. "
            "Please ensure the DLL files are installed with the package."
        )

    # Required assemblies (loaded in dependency order)
    assemblies = [
        "OpenMcdf.dll",
        "ThermoFisher.CommonCore.Data.dll",
        "ThermoFisher.CommonCore.RawFileReader.dll",
        "ThermoFisher.CommonCore.BackgroundSubtraction.dll",
        "ThermoFisher.CommonCore.MassPrecisionEstimator.dll",
    ]

    for assembly_name in assemblies:
        assembly_file = assembly_path / assembly_name
        if not assembly_file.exists():
            raise AssemblyLoadError(f"Assembly not found: {assembly_file}")
        clr.AddReference(str(assembly_file))

    # Import the main classes
    from System import String
    from ThermoFisher.CommonCore.RawFileReader import RawFileReaderAdapter
    from ThermoFisher.CommonCore.Data.Business import (
        CentroidStream,
        SegmentedScan,
        ChromatogramTraceSettings,
        ChromatogramSignal,
        Scan,
    )
    from ThermoFisher.CommonCore.Data.FilterEnums import ScanFilter as FilterEnum
    from ThermoFisher.CommonCore.Data.Interfaces import IScanFilter

    _raw_file_class = RawFileReaderAdapter
    _centroid_stream_class = CentroidStream
    _segmented_scan_class = SegmentedScan
    _chromatogram_settings_class = ChromatogramTraceSettings
    _chromatogram_signal_class = ChromatogramSignal
    _scan_class = Scan
    _filter_class = FilterEnum
    _device_class = Device

    _dotnet_initialized = True


class RawFile:
    """Wrapper around Thermo RawFileReader's IRawDataPlus interface.

    Provides a Pythonic interface to read Thermo Scientific .raw mass
    spectrometry files.

    Example:
        >>> from thermo_raw_file_reader import RawFile, Device
        >>> with RawFile("data.raw") as rf:
        ...     rf.select_instrument(Device.MS, 1)
        ...     print(f"Scans: {rf.run_header.spectra_count}")
        ...     spectrum = rf.get_spectrum(100)
        ...     print(f"Peaks: {spectrum.num_peaks}")
    """

    def __init__(self, filepath: str | Path):
        """Open a RAW file for reading.

        Args:
            filepath: Path to the .raw file

        Raises:
            FileNotFoundError: If file doesn't exist
            RuntimeError: If file cannot be opened or has errors
            InitializationError: If .NET runtime fails to initialize
        """
        self._filepath = str(filepath)
        self._raw_file = None
        self._selected_device: Device | None = None
        self._selected_instance: int = 0

        # Initialize .NET runtime
        _initialize_dotnet()

        # Check file exists
        if not os.path.exists(self._filepath):
            raise RawFileNotFoundError(f"File not found: {self._filepath}")

        # Open the file using RawFileReaderAdapter.FileFactory
        try:
            from System import String
            filepath_str = String(self._filepath)
            self._raw_file = _raw_file_class.FileFactory(filepath_str)
        except Exception as e:
            raise RawFileOpenError(f"Failed to open file: {self._filepath}") from e

        # Check if file opened successfully
        if not self.is_open:
            raise RawFileOpenError(f"Unable to open file: {self._filepath}")

        # Check for file errors
        if self.is_error:
            raise RawFileCorruptedError(
                f"File has errors: {self.file_error}"
            )

        # Check if still in acquisition
        if self.in_acquisition:
            raise RawFileOpenError(
                f"File is still being acquired: {self._filepath}"
            )

    @property
    def filepath(self) -> str:
        """Get the file path."""
        return self._filepath

    @property
    def filename(self) -> str:
        """Get the file name."""
        return os.path.basename(self._filepath)

    @property
    def is_open(self) -> bool:
        """Check if file is open."""
        if self._raw_file is None:
            return False
        return bool(self._raw_file.IsOpen)

    @property
    def is_error(self) -> bool:
        """Check if there are file errors."""
        if self._raw_file is None:
            return True
        return bool(self._raw_file.IsError)

    @property
    def file_error(self) -> str:
        """Get error message if file has errors."""
        if self._raw_file is None:
            return "No file open"
        error = self._raw_file.FileError
        if error is None:
            return ""
        return str(error)

    @property
    def in_acquisition(self) -> bool:
        """Check if file is still being acquired."""
        if self._raw_file is None:
            return False
        return bool(self._raw_file.InAcquisition)

    @property
    def instrument_count(self) -> int:
        """Get number of instruments in the file."""
        if self._raw_file is None:
            return 0
        return int(self._raw_file.InstrumentCount)

    @property
    def file_header(self) -> FileHeader:
        """Get file header information."""
        if self._raw_file is None:
            return FileHeader()

        fh = self._raw_file.FileHeader
        return FileHeader(
            revision=str(fh.Revision),
            creation_date=str(fh.CreationDate),
            who_created_id=str(fh.WhoCreatedId),
            file_description=str(fh.FileDescription),
        )

    @property
    def run_header(self) -> RunHeader:
        """Get run header information."""
        if self._raw_file is None:
            return RunHeader()

        rh = self._raw_file.RunHeaderEx
        return RunHeader(
            first_spectrum=int(rh.FirstSpectrum),
            last_spectrum=int(rh.LastSpectrum),
            start_time=float(rh.StartTime),
            end_time=float(rh.EndTime),
            low_mass=float(rh.LowMass),
            high_mass=float(rh.HighMass),
            mass_resolution=float(rh.MassResolution),
            spectra_count=int(rh.SpectraCount),
            max_intensity=float(rh.MaxIntensity),
            max_integrated_intensity=float(rh.MaxIntegratedIntensity),
            comment1=str(rh.Comment1) if rh.Comment1 else "",
            comment2=str(rh.Comment2) if rh.Comment2 else "",
        )

    @property
    def sample_information(self) -> SampleInformation:
        """Get sample information."""
        if self._raw_file is None:
            return SampleInformation()

        si = self._raw_file.SampleInformation
        return SampleInformation(
            sample_name=str(si.SampleName) if si.SampleName else "",
            sample_id=str(si.SampleId) if si.SampleId else "",
            sample_type=int(si.SampleType),
            comment=str(si.Comment) if si.Comment else "",
            vial=int(si.Vial),
            sample_volume=float(si.SampleVolume),
            injection_volume=float(si.InjectionVolume),
            row_number=int(si.RowNumber),
            dilution_factor=float(si.DilutionFactor),
        )

    def select_instrument(self, device: Device, instance: int) -> None:
        """Select an instrument for subsequent operations.

        Args:
            device: Instrument type (Device.MS, Device.Analog, etc.)
            instance: Instance number (1-based)

        Raises:
            InstrumentNotSelectedError: If selection fails
        """
        if self._raw_file is None:
            raise InstrumentNotSelectedError("No file is open")

        try:
            # Convert Python Device enum to .NET Device
            from ThermoFisher.CommonCore.Data.Interfaces import Device as NetDevice

            self._raw_file.SelectInstrument(NetDevice(device), instance)
            self._selected_device = device
            self._selected_instance = instance
        except Exception as e:
            raise InstrumentNotSelectedError(
                f"Failed to select instrument {device}/{instance}"
            ) from e

    def get_instrument_data(self) -> InstrumentData:
        """Get current instrument data.

        Returns:
            InstrumentData object with instrument details.
        """
        if self._raw_file is None:
            return InstrumentData()

        inst = self._raw_file.GetInstrumentData()
        return InstrumentData(
            model=str(inst.Model) if inst.Model else "",
            name=str(inst.Name) if inst.Name else "",
            serial_number=str(inst.SerialNumber) if inst.SerialNumber else "",
            software_version=str(inst.SoftwareVersion) if inst.SoftwareVersion else "",
            hardware_version=str(inst.HardwareVersion) if inst.HardwareVersion else "",
            units=str(inst.Units) if inst.Units else "",
        )

    def get_filters(self) -> list[str]:
        """Get all unique filter strings in the file.

        Returns:
            List of unique filter strings.
        """
        if self._raw_file is None:
            return []

        filters = self._raw_file.GetFilters()
        return [str(f) for f in filters]

    def get_filter_for_scan_number(self, scan_number: int) -> ScanFilter:
        """Get the filter for a specific scan.

        Args:
            scan_number: The scan number to get filter for.

        Returns:
            ScanFilter object with filter details.
        """
        if self._raw_file is None:
            return ScanFilter()

        sf = self._raw_file.GetFilterForScanNumber(scan_number)
        return ScanFilter(
            filter_string=str(sf.ToString()),
            ms_order=int(sf.MSOrder),
            ionization_mode=int(sf.IonizationMode),
            polarity=int(sf.Polarity),
            mass_analyzer=int(sf.MassAnalyzer),
            detector_type=int(sf.DetectorType),
        )

    def retention_time_from_scan_number(self, scan_number: int) -> float:
        """Convert scan number to retention time (minutes).

        Args:
            scan_number: The scan number to convert.

        Returns:
            Retention time in minutes.
        """
        if self._raw_file is None:
            return 0.0
        return float(self._raw_file.RetentionTimeFromScanNumber(scan_number))

    def scan_number_from_retention_time(self, retention_time: float) -> int:
        """Convert retention time to closest scan number.

        Args:
            retention_time: Retention time in minutes.

        Returns:
            Closest scan number.
        """
        if self._raw_file is None:
            return 0
        return int(self._raw_file.ScanNumberFromRetentionTime(retention_time))

    def get_spectrum(
        self, scan_number: int, centroid: bool = True
    ) -> Spectrum:
        """Get spectrum data for a scan.

        Args:
            scan_number: The scan number to retrieve.
            centroid: If True, return centroid data; otherwise profile data.

        Returns:
            Spectrum object with masses and intensities.

        Raises:
            InvalidScanNumberError: If scan number is out of range.
            InstrumentNotSelectedError: If no instrument is selected.
        """
        if self._raw_file is None:
            raise InstrumentNotSelectedError("No file is open")

        # Validate scan number
        run_header = self.run_header
        if scan_number < run_header.first_spectrum or scan_number > run_header.last_spectrum:
            raise InvalidScanNumberError(
                f"Scan {scan_number} out of range ({run_header.first_spectrum}-"
                f"{run_header.last_spectrum})"
            )

        try:
            if centroid:
                # Get centroid/label data
                centroid_stream = self._raw_file.GetCentroidStream(scan_number, False)
                if centroid_stream is None or len(centroid_stream) == 0:
                    # Fall back to segmented scan if no centroid data
                    return self._get_segmented_spectrum(scan_number)

                masses = self._numpy_array_from_net(centroid_stream.Masses)
                intensities = self._numpy_array_from_net(centroid_stream.Intensities)

                charges = None
                if hasattr(centroid_stream, 'Charges') and centroid_stream.Charges is not None:
                    charges = self._numpy_array_from_net(centroid_stream.Charges)

                return Spectrum(
                    masses=masses,
                    intensities=intensities,
                    charges=charges,
                    scan_number=scan_number,
                    is_centroid=True,
                )
            else:
                return self._get_segmented_spectrum(scan_number)

        except Exception as e:
            raise InvalidScanNumberError(
                f"Failed to get spectrum for scan {scan_number}: {e}"
            ) from e

    def _get_segmented_spectrum(self, scan_number: int) -> Spectrum:
        """Get segmented (profile) spectrum data.

        Args:
            scan_number: The scan number to retrieve.

        Returns:
            Spectrum object with profile data.
        """
        stats = self._raw_file.GetScanStatsForScanNumber(scan_number)
        segmented = self._raw_file.GetSegmentedScanFromScanNumber(scan_number, stats)

        masses = self._numpy_array_from_net(segmented.Positions)
        intensities = self._numpy_array_from_net(segmented.Intensities)

        return Spectrum(
            masses=masses,
            intensities=intensities,
            scan_number=scan_number,
            is_centroid=False,
        )

    def _numpy_array_from_net(self, net_array: Any) -> np.ndarray:
        """Convert a .NET array to NumPy array.

        Args:
            net_array: .NET array to convert.

        Returns:
            NumPy array.
        """
        import System

        # Handle different .NET array types
        if net_array is None:
            import numpy as np

            return np.array([], dtype=np.float64)

        # Use System.Array.CopyTo for conversion
        if isinstance(net_array, System.Array):
            import numpy as np

            result = np.empty(len(net_array), dtype=np.float64)
            net_array.CopyTo(result, 0)
            return result

        # Fallback: try direct conversion
        import numpy as np

        return np.array(net_array, dtype=np.float64)

    def get_chromatogram(
        self,
        trace_type: TraceType = TraceType.BasePeak,
        start_scan: int | None = None,
        end_scan: int | None = None,
    ) -> Chromatogram:
        """Get chromatogram data.

        Args:
            trace_type: Type of chromatogram (BasePeak, TIC, etc.).
            start_scan: Starting scan number (default: first scan).
            end_scan: Ending scan number (default: last scan).

        Returns:
            Chromatogram object with times and intensities.
        """
        if self._raw_file is None:
            return Chromatogram()

        # Set defaults
        if start_scan is None:
            start_scan = self.run_header.first_spectrum
        if end_scan is None:
            end_scan = self.run_header.last_spectrum

        try:
            # Create chromatogram settings
            settings = _chromatogram_settings_class(int(trace_type))

            # Get chromatogram data
            data = self._raw_file.GetChromatogramData(
                [settings], int(start_scan), int(end_scan)
            )

            # Extract signal
            traces = _chromatogram_signal_class.FromChromatogramData(data)

            if len(traces) == 0 or len(traces[0]) == 0:
                return Chromatogram(trace_type=int(trace_type))

            # Get the first trace
            trace = traces[0]
            times = self._numpy_array_from_net(trace.Times)
            intensities = self._numpy_array_from_net(trace.Intensities)

            return Chromatogram(
                times=times,
                intensities=intensities,
                trace_type=int(trace_type),
            )

        except Exception as e:
            # Return empty chromatogram on error
            return Chromatogram(trace_type=int(trace_type))

    def average_scans(
        self,
        scan_range: tuple[int, int],
        tolerance: float = 5.0,
        tolerance_units: ToleranceUnits = ToleranceUnits.ppm,
    ) -> Spectrum:
        """Average spectra within a scan range.

        Args:
            scan_range: Tuple of (first_scan, last_scan).
            tolerance: Mass tolerance for aligning peaks.
            tolerance_units: Units for tolerance (ppm or Da).

        Returns:
            Averaged Spectrum object.
        """
        if self._raw_file is None:
            return Spectrum()

        first_scan, last_scan = scan_range

        try:
            # Get default mass options and configure
            options = self._raw_file.DefaultMassOptions()
            options.ToleranceUnits = int(tolerance_units)
            options.Tolerance = float(tolerance)

            # Get filter for the first scan
            scan_filter = self._raw_file.GetFilterForScanNumber(first_scan)

            # Get average spectrum
            avg_scan = self._raw_file.AverageScansInScanRange(
                first_scan, last_scan, scan_filter, options
            )

            if avg_scan is None or not hasattr(avg_scan, 'CentroidScan'):
                return Spectrum()

            centroid = avg_scan.CentroidScan
            if centroid is None or len(centroid) == 0:
                return Spectrum()

            masses = self._numpy_array_from_net(centroid.Masses)
            intensities = self._numpy_array_from_net(centroid.Intensities)

            return Spectrum(
                masses=masses,
                intensities=intensities,
                scan_number=first_scan,
                is_centroid=True,
            )

        except Exception as e:
            return Spectrum()

    def get_trailer_extra_information(self, scan_number: int) -> dict[str, str]:
        """Get trailer extra data fields for a scan.

        Args:
            scan_number: The scan number to get data for.

        Returns:
            Dictionary mapping field names to values.
        """
        if self._raw_file is None:
            return {}

        try:
            log_entry = self._raw_file.GetTrailerExtraInformation(scan_number)
            if log_entry is None:
                return {}

            labels = log_entry.Labels
            values = log_entry.Values

            result = {}
            for i in range(min(len(labels), len(values))):
                label = str(labels[i]) if labels[i] else ""
                value = str(values[i]) if values[i] else ""
                if label:
                    result[label] = value

            return result

        except Exception:
            return {}

    def get_status_log_header_information(self) -> list[StatusLogField]:
        """Get status log field definitions.

        Returns:
            List of StatusLogField objects.
        """
        if self._raw_file is None:
            return []

        try:
            fields = self._raw_file.GetStatusLogHeaderInformation()
            result = []
            for field in fields:
                result.append(
                    StatusLogField(
                        label=str(field.Label) if field.Label else "",
                        data_type=int(field.DataType),
                    )
                )
            return result
        except Exception:
            return []

    def get_inclusion_exclusion_list(
        self, mass_tolerance: float = 1e-5
    ) -> list[InclusionListItem]:
        """Get inclusion/exclusion list from instrument method.

        Note: This is a simplified implementation that parses the
        instrument method text for mass list tables.

        Args:
            mass_tolerance: Mass tolerance for associating items with scans.

        Returns:
            List of InclusionListItem objects.
        """
        if self._raw_file is None:
            return []

        try:
            result = []

            # Look for "Mass List Table" in instrument methods
            inclusion_strings = []
            for i in range(self._raw_file.InstrumentMethodsCount):
                method_text = str(self._raw_file.GetInstrumentMethod(i))
                if "Mass List Table" in method_text:
                    lines = method_text.split("\n")
                    save_line = False
                    for line in lines:
                        if "Mass List Table" in line:
                            save_line = True
                            continue
                        if "End Mass List Table" in line:
                            save_line = False
                            continue
                        if save_line and line.strip():
                            inclusion_strings.append(line)

            # Parse inclusion list items
            for line in inclusion_strings:
                if "CompoundName" in line:
                    continue  # Skip header

                parts = line.split("|")
                if len(parts) >= 3:
                    try:
                        item = InclusionListItem(
                            descriptor=parts[0].strip(),
                            mass=float(parts[1].strip()),
                            threshold=float(parts[2].strip()),
                        )
                        result.append(item)
                    except ValueError:
                        continue

            return result

        except Exception:
            return []

    def close(self) -> None:
        """Close the file and release resources."""
        if self._raw_file is not None:
            try:
                self._raw_file.Dispose()
            except Exception:
                pass
            self._raw_file = None

    def __enter__(self) -> RawFile:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - ensures file is closed."""
        self.close()

    def __del__(self) -> None:
        """Destructor - ensure file is closed."""
        self.close()

    def __repr__(self) -> str:
        """Return a string representation."""
        if self._raw_file is None:
            return "RawFile(closed)"

        return (
            f"RawFile(filename={self.filename}, "
            f"scans={self.run_header.first_spectrum}-{self.run_header.last_spectrum}, "
            f"open={self.is_open})"
        )
