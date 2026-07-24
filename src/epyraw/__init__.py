"""Epyraw - Python wrapper for Thermo Fisher RawFileReader library.

This package provides a Pythonic interface to read Thermo Scientific .raw
mass spectrometry files using the official RawFileReader .NET library.

Example:
    >>> from epyraw import RawFile, Device
    >>> with RawFile("data.raw") as rf:
    ...     rf.select_instrument(Device.MS, 1)
    ...     print(f"Scans: {rf.run_header.spectra_count}")
    ...     spectrum = rf.get_spectrum(100)
    ...     print(f"Peaks: {spectrum.num_peaks}")
"""

from .download import check_runtimes_present, download_runtimes, get_default_runtime_path
from .enums import (BarcodeStatusType, DetectorType, Device, IonizationMode,
                    MassAnalyzerType, MSOrderType, PolarityType, SampleType,
                    ScanTypeEnum, SpectrumPacketType, TrayShape, ToleranceUnits,
                    TraceType)
from .exceptions import (AssemblyLoadError, InitializationError,
                         InstrumentNotSelectedError, InvalidScanNumberError,
                         RawFileCorruptedError, RawFileNotFoundError,
                         RawFileOpenError, ThermoRawFileError)
from .models import (AutoSamplerInformation, Chromatogram, FileHeader,
                    InclusionListItem, InstrumentData, MassOptions, Reaction,
                    RunHeader, SampleInformation, ScanDependentDetail,
                    ScanDependents, ScanEvent, ScanHeader, ScanStats, ScanFilter,
                    Spectrum, StatusLogField)
from .raw_file import RawFile, set_runtime

__version__ = "0.1.0"

__all__ = [
    # Main class
    "RawFile",
    "set_runtime",
    # Download functions
    "download_runtimes",
    "check_runtimes_present",
    "get_default_runtime_path",
    # Enums
    "Device",
    "DetectorType",
    "IonizationMode",
    "MSOrderType",
    "MassAnalyzerType",
    "PolarityType",
    "SampleType",
    "ToleranceUnits",
    "TraceType",
    "SpectrumPacketType",
    "ScanTypeEnum",
    "TrayShape",
    "BarcodeStatusType",
    # Data models
    "Chromatogram",
    "FileHeader",
    "InclusionListItem",
    "InstrumentData",
    "RunHeader",
    "SampleInformation",
    "ScanFilter",
    "Spectrum",
    "StatusLogField",
    "ScanHeader",
    "ScanEvent",
    "Reaction",
    "MassOptions",
    "ScanStats",
    "ScanDependents",
    "ScanDependentDetail",
    "AutoSamplerInformation",
    # Exceptions
    "AssemblyLoadError",
    "InitializationError",
    "InstrumentNotSelectedError",
    "InvalidScanNumberError",
    "RawFileCorruptedError",
    "RawFileNotFoundError",
    "RawFileOpenError",
    "ThermoRawFileError",
]
