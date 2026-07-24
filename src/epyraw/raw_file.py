"""Main RawFile class for reading Thermo .raw files."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np

from .download import ensure_runtimes_available, get_default_runtime_path
from .enums import BarcodeStatusType, Device, ScanTypeEnum, SpectrumPacketType, TrayShape, ToleranceUnits, TraceType
from .exceptions import (AssemblyLoadError, InitializationError,
                         InstrumentNotSelectedError, InvalidScanNumberError,
                         RawFileCorruptedError, RawFileNotFoundError,
                         RawFileOpenError)
from .models import (AutoSamplerInformation, Chromatogram, FileHeader, InclusionListItem,
                     InstrumentData, MassOptions, Reaction, RunHeader, SampleInformation, ScanDependentDetail,
                     ScanDependents, ScanEvent, ScanHeader, ScanStats, ScanFilter,
                     Spectrum, StatusLogField)


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
_assembly_path: Path | None = None


def _get_assembly_path() -> Path:
    """Get the path to the .NET assemblies.

    Checks in order:
    1. EPYRAW_RUNTIME_PATH environment variable
    2. ~/.epyraw/runtimes/net8old/
    3. Downloads if not found

    Returns:
        Path to the runtime assemblies

    Raises:
        AssemblyLoadError: If no runtime path found and download fails
    """
    global _assembly_path

    if _assembly_path is not None:
        return _assembly_path

    # Check environment variable first
    env_path = os.environ.get("EPYRAW_RUNTIME_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            _assembly_path = path
            return path

    # Check default user path
    default_path = get_default_runtime_path()
    if default_path.exists():
        _assembly_path = default_path
        return default_path

    # Try to download
    try:
        _assembly_path = ensure_runtimes_available()
        return _assembly_path
    except Exception:
        raise AssemblyLoadError(
            "Runtime DLLs not found. Please run:\n"
            "  epyraw download\n"
            "or set EPYRAW_RUNTIME_PATH environment variable."
        )


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
        >>> from epyraw import set_runtime, RawFile
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
        raise InitializationError(f"Failed to set runtime to '{runtime}': {e}") from e


def _initialize_dotnet(runtime: str | None = None) -> None:
    """Initialize the .NET runtime and load assemblies.

    This function should be called once before using any RawFile functionality.
    It attempts to configure an appropriate .NET runtime, with CoreCLR (.NET 6+)
    preferred for compatibility with the Thermo RawFileReader libraries.

    Args:
        runtime: Optional explicit runtime choice. If None, uses default detection
                 with fallback strategy.
    """
    global _dotnet_initialized, _raw_file_class
    global _centroid_stream_class, _segmented_scan_class
    global _chromatogram_settings_class, _chromatogram_signal_class
    global _scan_class, _filter_class, _device_class, _net_trace_type_class

    if _dotnet_initialized:
        return

    # Check for local .NET installation first
    dotnet_root = os.environ.get("DOTNET_ROOT")
    if not dotnet_root:
        # Try common locations
        possible_dotnet_roots = [
            Path.home() / ".dotnet",
            Path("/usr/share/dotnet"),
            Path("/opt/dotnet"),
        ]
        for p in possible_dotnet_roots:
            if (p / "dotnet").exists():
                dotnet_root = str(p)
                os.environ["DOTNET_ROOT"] = dotnet_root
                break

    # Set runtime BEFORE importing clr
    # Runtime selection strategy:
    # 1. If explicitly specified, use that runtime
    # 2. Otherwise, prefer coreclr for .NET 8 compatibility
    runtime_order = []

    if runtime:
        # Explicit runtime requested
        runtime_order = [runtime]
    else:
        # Default strategy: try coreclr first (for .NET 8 assemblies),
        # then fall back to mono
        runtime_order = ["coreclr", "mono"]

    last_error: Exception | None = None

    for rt in runtime_order:
        try:
            from pythonnet import set_runtime as set_pythonnet_runtime

            set_pythonnet_runtime(rt)
            # Now try to import clr - this will use the configured runtime
            import clr

            # Success! clr imported with the configured runtime
            break
        except Exception as e:
            last_error = e
            continue
    else:
        # All runtime attempts failed
        raise InitializationError(
            f"Failed to initialize .NET runtime. Last error: {last_error}"
        ) from last_error

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
    from ThermoFisher.CommonCore.Data.Business import (
        CentroidStream, ChromatogramSignal, ChromatogramTraceSettings)
    from ThermoFisher.CommonCore.Data.Business import \
        Device as NetDevice  # Use alias to avoid conflict with our Device enum
    from ThermoFisher.CommonCore.Data.Business import Scan, SegmentedScan
    from ThermoFisher.CommonCore.Data.Business import \
        TraceType as NetTraceType  # .NET TraceType enum for chromatograms
    from ThermoFisher.CommonCore.RawFileReader import RawFileReaderAdapter

    _raw_file_class = RawFileReaderAdapter
    _centroid_stream_class = CentroidStream
    _segmented_scan_class = SegmentedScan
    _chromatogram_settings_class = ChromatogramTraceSettings
    _chromatogram_signal_class = ChromatogramSignal
    _scan_class = Scan
    _device_class = NetDevice  # Store .NET Device class
    _net_trace_type_class = NetTraceType  # Store .NET TraceType class

    _dotnet_initialized = True


class RawFile:
    """Wrapper around Thermo RawFileReader's IRawDataPlus interface.

    Provides a Pythonic interface to read Thermo Scientific .raw mass
    spectrometry files.

    Example:
        >>> from epyraw import RawFile, Device
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
            raise RawFileCorruptedError(f"File has errors: {self.file_error}")

        # Check if still in acquisition
        if self.in_acquisition:
            raise RawFileOpenError(f"File is still being acquired: {self._filepath}")

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

        # Helper function to safely convert values with defaults
        def safe_int(val, default=0):
            try:
                return int(val) if val else default
            except (ValueError, TypeError):
                return default

        def safe_float(val, default=0.0):
            try:
                return float(val) if val else default
            except (ValueError, TypeError):
                return default

        return SampleInformation(
            sample_name=str(si.SampleName) if si.SampleName else "",
            sample_id=str(si.SampleId) if si.SampleId else "",
            sample_type=int(si.SampleType),
            comment=str(si.Comment) if si.Comment else "",
            vial=safe_int(si.Vial),
            sample_volume=safe_float(si.SampleVolume),
            injection_volume=safe_float(si.InjectionVolume),
            row_number=safe_int(si.RowNumber),
            dilution_factor=safe_float(si.DilutionFactor),
        )

    @property
    def has_instrument_method(self) -> bool:
        """Check if the file contains an instrument method.

        Returns:
            True if an instrument method is present, False otherwise.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     if rf.has_instrument_method:
            ...         names = rf.get_all_instrument_friendly_names_from_method()
        """
        if self._raw_file is None:
            return False
        return bool(self._raw_file.HasInstrumentMethod)

    @property
    def auto_sampler_information(self) -> AutoSamplerInformation:
        """Get autosampler tray configuration.

        Returns:
            AutoSamplerInformation object with tray and vial details.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     auto_info = rf.auto_sampler_information
            ...     print(f"Tray {auto_info.tray_index}, Vial {auto_info.vial_index}")
        """
        if self._raw_file is None:
            return AutoSamplerInformation()

        asi = self._raw_file.AutoSamplerInformation

        return AutoSamplerInformation._from_raw(
            tray_index=int(asi.TrayIndex),
            vial_index=int(asi.VialIndex),
            vials_per_tray_x=int(asi.VialsPerTrayX),
            vials_per_tray_y=int(asi.VialsPerTrayY),
            tray_shape_int=int(asi.TrayShape),
            tray_name=str(asi.TrayName) if asi.TrayName else "",
        )

    @property
    def user_labels(self) -> list[str]:
        """Get labels for user-configurable sample columns.

        Returns:
            List of label strings.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     labels = rf.user_labels
            ...     print(f"User labels: {labels}")
        """
        if self._raw_file is None:
            return []
        labels = self._raw_file.UserLabel
        return [str(l) if l else "" for l in labels]

    @property
    def include_reference_and_exception_data(self) -> bool:
        """Get/set whether to include reference and exception data.

        Returns:
            Current value of the property.

        Note:
            This property can be set to control inclusion of reference
            and exception data when reading the file.
        """
        if self._raw_file is None:
            return False
        return bool(self._raw_file.IncludeReferenceAndExceptionData)

    @include_reference_and_exception_data.setter
    def include_reference_and_exception_data(self, value: bool) -> None:
        """Set whether to include reference and exception data."""
        if self._raw_file is not None:
            self._raw_file.IncludeReferenceAndExceptionData = bool(value)

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
            # Use the .NET Device class from Business module
            self._raw_file.SelectInstrument(_device_class(device), instance)
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
        # Check for available attributes - DetectorType may not exist in all versions
        detector_type = 0
        if hasattr(sf, "DetectorType"):
            detector_type = int(sf.DetectorType)
        elif hasattr(sf, "DetectorValue"):
            detector_type = int(sf.DetectorValue)

        return ScanFilter(
            filter_string=str(sf.ToString()),
            ms_order=int(sf.MSOrder),
            ionization_mode=int(sf.IonizationMode),
            polarity=int(sf.Polarity),
            mass_analyzer=int(sf.MassAnalyzer),
            detector_type=detector_type,
        )

    def get_scan_header(self, scan_number: int) -> ScanHeader:
        """Get detailed header information for a specific scan.

        Note: This method extracts available information from scan statistics
        since GetScanHeaderInfo may not be available in all library versions.

        Args:
            scan_number: The scan number to get header for.

        Returns:
            ScanHeader object with available scan metadata.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     header = rf.get_scan_header(100)
            ...     print(f"Scan Type: {header.scan_type}")
        """
        if self._raw_file is None:
            return ScanHeader()

        try:
            # Get scan statistics which contains most header info
            stats = self._raw_file.GetScanStatsForScanNumber(scan_number)

            # Parse scan type from the filter string
            scan_type_str = ""
            if hasattr(stats, "ScanType"):
                scan_type_str = str(stats.ScanType) if stats.ScanType else ""

            # Try to get MS level from filter
            ms_level = 1
            try:
                filter_info = self._raw_file.GetFilterForScanNumber(scan_number)
                if hasattr(filter_info, "MSOrder"):
                    ms_level = int(filter_info.MSOrder)
            except Exception:
                pass

            # Get retention time
            trigger_time = 0.0
            try:
                trigger_time = float(self._raw_file.RetentionTimeFromScanNumber(scan_number))
            except Exception:
                pass

            return ScanHeader(
                scan_number=int(scan_number),
                ms_level=ms_level,
                precursor_scan_num=0,  # Not available in all versions
                scan_type=scan_type_str,
                instrument_model="",  # Not directly available
                number_of_ions=int(getattr(stats, "PacketCount", 0)),
                isolation_width=0.0,  # Not available without GetScanHeaderInfo
                collision_energy=0.0,  # Not available without GetScanHeaderInfo
                trigger_time=trigger_time,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get scan header for scan {scan_number}: {e}") from e

    def get_scan_event(self, scan_number: int) -> ScanEvent:
        """Get scan event information including reactions.

        Provides access to scan event data for MSn scans. Note that detailed
        reaction data (precursor mass, collision energy) may not be available
        in all library versions.

        Args:
            scan_number: The scan number to get event for.

        Returns:
            ScanEvent object with mass analyzer info. Reactions list may be empty
            if not supported by the library version.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     event = rf.get_scan_event(150)
            ...     print(f"Mass analyzer: {event.mass_analyzer}")
        """
        if self._raw_file is None:
            return ScanEvent()

        try:
            scan_event = self._raw_file.GetScanEventForScanNumber(scan_number)

            reactions = []
            # Try to get reaction count - may not be available in all versions
            if hasattr(scan_event, "ReactionCount"):
                reaction_count = getattr(scan_event, "ReactionCount", 0)
                if reaction_count and reaction_count > 0:
                    for i in range(reaction_count):
                        try:
                            reaction = scan_event.GetReaction(i)
                            reactions.append(Reaction(
                                precursor_mass=float(getattr(reaction, "PrecursorMass", 0)),
                                collision_energy=float(getattr(reaction, "CollisionEnergy", 0)),
                                isolation_width=float(getattr(reaction, "IsolationWidth", 0)),
                            ))
                        except Exception:
                            break

            # Get mass analyzer - use string name if enum not available
            mass_analyzer = 0
            ma_attr = getattr(scan_event, "MassAnalyzer", None)
            if ma_attr is not None:
                try:
                    mass_analyzer = int(ma_attr)
                except (ValueError, TypeError):
                    # It's a string enum name, just use a hash or 0
                    mass_analyzer = 0

            return ScanEvent(
                mass_analyzer=mass_analyzer,
                reactions=reactions,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get scan event for scan {scan_number}: {e}") from e

    def get_scan_stats(self, scan_number: int) -> ScanStats:
        """Get statistics for a specific scan.

        Args:
            scan_number: The scan number to get stats for.

        Returns:
            ScanStats object with scan quality metrics.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     stats = rf.get_scan_stats(100)
            ...     print(f"Centroid: {stats.is_centroid_scan}, Packets: {stats.mass_count}")
        """
        if self._raw_file is None:
            return ScanStats()

        try:
            stats = self._raw_file.GetScanStatsForScanNumber(scan_number)

            # Note: Attribute names may vary by library version
            # Using getattr with defaults for compatibility
            return ScanStats(
                is_centroid_scan=bool(getattr(stats, "IsCentroidScan", False)),
                spectrum_packet_type=int(getattr(stats, "SpectrumPacketType", 0)),
                mass_count=int(getattr(stats, "PacketCount", 0)),
                total_intensity=float(getattr(stats, "TIC", 0.0)),
                max_intensity=float(getattr(stats, "BasePeakIntensity", 0.0)),
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get scan stats for scan {scan_number}: {e}") from e

    def default_mass_options(self) -> MassOptions:
        """Get default mass options for scan averaging operations.

        Note: This method returns default values since the underlying
        DefaultMassOptions method may not be available in all library versions.

        Returns:
            MassOptions object with default tolerance settings (5 ppm).

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     options = rf.default_mass_options()
            ...     print(f"Tolerance: {options.tolerance} {options.tolerance_units}")
        """
        if self._raw_file is None:
            return MassOptions()

        try:
            # Try to get default options from the raw file
            net_options = self._raw_file.DefaultMassOptions()
            return MassOptions(
                tolerance=float(net_options.Tolerance),
                tolerance_units=int(net_options.ToleranceUnits),
            )
        except Exception:
            # Return sensible defaults if method not available
            return MassOptions(tolerance=5.0, tolerance_units=1)

    def average_scans_in_scan_range(
        self,
        first_scan: int,
        last_scan: int,
        scan_filter: ScanFilter | None = None,
        options: MassOptions | None = None,
    ) -> Spectrum:
        """Average spectra within a scan range.

        Note: This functionality requires the AverageScansInScanRange method
        which may not be available in all library versions. If not available,
        returns an empty spectrum.

        Args:
            first_scan: First scan number to include.
            last_scan: Last scan number to include.
            scan_filter: Optional scan filter to apply. If None, uses default.
            options: Mass tolerance options. If None, uses defaults.

        Returns:
            Averaged Spectrum object, or empty spectrum if feature unavailable.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     rf.select_instrument(Device.MS, 1)
            ...     avg = rf.average_scans_in_scan_range(100, 110)
            ...     print(f"Averaged {last_scan - first_scan + 1} scans")
        """
        if self._raw_file is None:
            raise RuntimeError("No file is open")

        # Check if the method is available
        if not hasattr(self._raw_file, "AverageScansInScanRange"):
            # Feature not available in this library version
            return Spectrum(scan_number=first_scan, is_centroid=True)

        try:
            # Get default options if not provided
            if options is None:
                options = self.default_mass_options()

            # Get scan filter if not provided
            if scan_filter is None:
                scan_filter = self.get_filter_for_scan_number(first_scan)

            # Use AverageScansInScanRange method
            avg_scan = self._raw_file.AverageScansInScanRange(
                first_scan, last_scan, scan_filter.ToString(), options
            )

            # Extract masses and intensities from averaged scan
            masses = self._numpy_array_from_net(avg_scan.Masses)
            intensities = self._numpy_array_from_net(avg_scan.Intensities)

            return Spectrum(
                masses=masses,
                intensities=intensities,
                scan_number=first_scan,  # Use first scan as reference
                is_centroid=True,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to average scans {first_scan}-{last_scan}: {e}") from e

    def average_scans(
        self,
        scan_numbers: list[int],
        options: MassOptions | None = None,
    ) -> Spectrum:
        """Average an arbitrary list of spectra.

        Note: This functionality requires the AverageScans method which may
        not be available in all library versions. If not available, returns
        an empty spectrum.

        Args:
            scan_numbers: List of scan numbers to average.
            options: Mass tolerance options. If None, uses defaults.

        Returns:
            Averaged Spectrum object, or empty spectrum if feature unavailable.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     rf.select_instrument(Device.MS, 1)
            ...     scans = [100, 102, 104, 106]
            ...     avg = rf.average_scans(scans)
        """
        if self._raw_file is None:
            raise RuntimeError("No file is open")

        # Check if the method is available
        if not hasattr(self._raw_file, "AverageScans"):
            # Feature not available in this library version
            return Spectrum(scan_number=0, is_centroid=True)

        try:
            # Get default options if not provided
            if options is None:
                options = self.default_mass_options()

            # Create .NET List<int> for scan numbers
            from System.Collections.Generic import List
            from System import Int32
            scan_list = List[Int32]()
            for num in scan_numbers:
                scan_list.Add(int(num))

            # Use AverageScans method
            avg_scan = self._raw_file.AverageScans(scan_list, options)

            # Extract masses and intensities from averaged scan
            masses = self._numpy_array_from_net(avg_scan.Masses)
            intensities = self._numpy_array_from_net(avg_scan.Intensities)

            return Spectrum(
                masses=masses,
                intensities=intensities,
                scan_number=scan_numbers[0] if scan_numbers else 0,
                is_centroid=True,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to average scans {scan_numbers}: {e}") from e

    def centroid_scan(self, scan_number: int) -> Spectrum:
        """Convert a profile scan to centroid format.

        Applies centroiding algorithm to convert profile data to
        peak lists.

        Args:
            scan_number: The scan number to centroid.

        Returns:
            Centroided Spectrum object.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     centroid = rf.centroid_scan(100)
            ...     print(f"Peaks after centroiding: {centroid.num_peaks}")
        """
        if self._raw_file is None:
            raise RuntimeError("No file is open")

        try:
            # Get the scan as a Scan object
            from ThermoFisher.CommonCore.Data.Business import Scan

            scan = Scan.FromFile(self._raw_file, scan_number)

            # Convert to centroid
            centroid_scan = Scan.ToCentroid(scan)

            # Extract data - use PreferredMasses for centroided data
            # Note: ToCentroid returns mass list without intensities in some versions
            masses = self._numpy_array_from_net(centroid_scan.PreferredMasses)

            # Intensities are not available from ToCentroid, create placeholder zeros
            # This is a limitation of the API - the centroid operation only returns masses
            intensities = np.zeros(len(masses), dtype=np.float64)

            return Spectrum(
                masses=masses,
                intensities=intensities,
                scan_number=scan_number,
                is_centroid=True,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to centroid scan {scan_number}: {e}") from e

    def get_instrument_count_by_type(self, device_type: Device) -> int:
        """Get count of instruments of a specific type.

        Args:
            device_type: The device type to count (Device.MS, Device.Analog, etc.)

        Returns:
            Number of instruments of the specified type.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     ms_count = rf.get_instrument_count_by_type(Device.MS)
            ...     analog_count = rf.get_instrument_count_by_type(Device.Analog)
        """
        if self._raw_file is None:
            return 0

        try:
            # Use the .NET Device enum class for compatibility
            from ThermoFisher.CommonCore.Data.Business import Device as NetDevice

            net_device = NetDevice(device_type.value)
            return int(self._raw_file.GetInstrumentCountOfType(net_device))
        except Exception as e:
            raise RuntimeError(f"Failed to get instrument count for {device_type}: {e}") from e

    def get_scan_dependents(self, scan_number: int, max_dependents: int = 10) -> ScanDependents:
        """Get scans that were triggered by this precursor scan.

        For MSn experiments, returns child scans triggered by
        the specified precursor scan.

        Args:
            scan_number: The precursor scan number.
            max_dependents: Maximum number of dependents to return.

        Returns:
            ScanDependents object with dependent scan details.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     dependents = rf.get_scan_dependents(100)
            ...     for detail in dependents.scan_dependent_details:
            ...         print(f"Child scan: {detail.scan_number}")
        """
        if self._raw_file is None:
            return ScanDependents()

        try:
            dependents = self._raw_file.GetScanDependents(scan_number, max_dependents)

            details = []
            if hasattr(dependents, "ScanDependentDetailArray"):
                for detail in dependents.ScanDependentDetailArray:
                    details.append(ScanDependentDetail(
                        scan_number=int(detail.ScanNumber),
                        scan_type=str(detail.ScanType) if detail.ScanType else "",
                        ms_level=int(detail.MSLevel),
                    ))

            return ScanDependents(
                raw_file_instrument_type=str(dependents.RawFileInstrumentType) if dependents.RawFileInstrumentType else "",
                scan_dependent_details=details,
            )
        except Exception as e:
            raise RuntimeError(f"Failed to get scan dependents for scan {scan_number}: {e}") from e

    def get_all_instrument_friendly_names_from_method(self) -> list[str]:
        """Get display names for all instruments in the acquisition method.

        Returns human-friendly instrument names like "TSQ Quantum Ultra"
        instead of internal identifiers.

        Returns:
            List of instrument name strings.

        Example:
            >>> with RawFile("data.raw") as rf:
            ...     if rf.has_instrument_method:
            ...         names = rf.get_all_instrument_friendly_names_from_method()
            ...         print(f"Instruments: {names}")
        """
        if self._raw_file is None:
            return []

        try:
            names = self._raw_file.GetAllInstrumentFriendlyNamesFromInstrumentMethod()
            return [str(n) if n else "" for n in names]
        except Exception as e:
            raise RuntimeError("Failed to get instrument names from method") from e

    def refresh_view(self) -> None:
        """Refresh the view of a file being acquired in real-time.

        Call this method to update the view when a file is still
        being written during acquisition.

        Example:
            >>> with RawFile("live_acquisition.raw") as rf:
            ...     # Wait for some acquisition...
            ...     rf.refresh_view()
            ...     print(f"Current scan: {rf.run_header.last_spectrum}")
        """
        if self._raw_file is None:
            raise RuntimeError("No file is open")

        try:
            self._raw_file.RefreshViewOfFile()
        except Exception as e:
            raise RuntimeError(f"Failed to refresh view: {e}") from e

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

    def get_spectrum(self, scan_number: int, centroid: bool = True) -> Spectrum:
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
        if (
            scan_number < run_header.first_spectrum
            or scan_number > run_header.last_spectrum
        ):
            raise InvalidScanNumberError(
                f"Scan {scan_number} out of range ({run_header.first_spectrum}-"
                f"{run_header.last_spectrum})"
            )

        try:
            if centroid:
                # Get centroid/label data
                centroid_stream = self._raw_file.GetCentroidStream(scan_number, False)
                # Check length using Length property (.NET style)
                if centroid_stream is None or centroid_stream.Length == 0:
                    # Fall back to segmented scan if no centroid data
                    return self._get_segmented_spectrum(scan_number)

                masses = self._numpy_array_from_net(centroid_stream.Masses)
                intensities = self._numpy_array_from_net(centroid_stream.Intensities)

                charges = None
                if (
                    hasattr(centroid_stream, "Charges")
                    and centroid_stream.Charges is not None
                ):
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
            return np.array([], dtype=np.float64)

        # Use numpy's frombuffer or direct conversion for .NET arrays
        if isinstance(net_array, System.Array):
            # For .NET 8, use a list comprehension approach
            # which works more reliably across versions
            return np.array(
                [float(net_array[i]) for i in range(len(net_array))], dtype=np.float64
            )

        # Fallback: try direct conversion
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
            # Create chromatogram settings using .NET TraceType enum
            # pythonnet 3.0+ requires explicit enum conversion
            net_trace_type = _net_trace_type_class(int(trace_type))
            settings = _chromatogram_settings_class(net_trace_type)

            # Get chromatogram data
            data = self._raw_file.GetChromatogramData(
                [settings], int(start_scan), int(end_scan)
            )

            # Extract signal
            traces = _chromatogram_signal_class.FromChromatogramData(data)

            # Check for empty result - use .Length for .NET arrays
            if traces.Length == 0:
                return Chromatogram(trace_type=int(trace_type))

            trace = traces[0]

            # Check if trace has data - IList uses .Count property
            if trace.Times.Count == 0:
                return Chromatogram(trace_type=int(trace_type))

            # Convert IList to numpy arrays
            times = np.array(
                [float(trace.Times[i]) for i in range(trace.Times.Count)],
                dtype=np.float64,
            )
            intensities = np.array(
                [float(trace.Intensities[i]) for i in range(trace.Intensities.Count)],
                dtype=np.float64,
            )

            return Chromatogram(
                times=times,
                intensities=intensities,
                trace_type=int(trace_type),
            )

        except Exception as e:
            raise RuntimeError(f"Failed to get chromatogram: {e}") from e

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

        except Exception as e:
            raise RuntimeError(f"Failed to get trailer extra information: {e}") from e

    def get_status_log_header_information(self) -> list[StatusLogField]:
        """Get status log field definitions.

        Returns:
            List of StatusLogField objects.
        """
        if self._raw_file is None:
            return []

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

    def close(self) -> None:
        """Close the file and release resources."""
        if self._raw_file is not None:
            rf = self._raw_file
            self._raw_file = None
            try:
                rf.Dispose()
            except BaseException:
                # Ignore all errors during disposal, especially in __del__
                # where the interpreter may be shutting down
                pass

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
