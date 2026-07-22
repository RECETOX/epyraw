"""Enum types for Thermo RawFile Reader.

These enums mirror the .NET enum types from the RawFileReader library,
providing a Pythonic interface to filter and select data.
"""

from enum import IntEnum, Enum


class Device(IntEnum):
    """Instrument device types."""

    Analog = 0
    MS = 1
    MSAnalog = 2
    Other = 3
    Pda = 4
    UV = 5


class MSOrderType(IntEnum):
    """Mass spectrometry order."""

    Unknown = 0
    Ms = 1
    Ms2 = 2
    Ms3 = 3
    MsN = 4


class IonizationMode(IntEnum):
    """Ionization mode."""

    Unknown = 0
    Positive = 1
    Negative = 2


class PolarityType(IntEnum):
    """Polarity type."""

    Unknown = 0
    Positive = 1
    Negative = 2


class MassAnalyzerType(IntEnum):
    """Mass analyzer types."""

    Unknown = 0
    Quadrupole = 1
    IonTrap = 2
    TOF = 3
    Orbitrap = 4
    FTICR = 5
    Sector = 6


class DetectorType(IntEnum):
    """Detector types."""

    Unknown = 0
    ElectronMultiplier = 1
    FaradayCup = 2
    PhotodiodeArray = 3
    CCD = 4


class TraceType(IntEnum):
    """Chromatogram trace types."""

    BasePeak = 0
    TIC = 1
    A2DChannel1 = 2
    A2DChannel2 = 3
    A2DChannel3 = 4
    A2DChannel4 = 5
    Analog1 = 6
    Analog2 = 7
    Analog3 = 8
    Analog4 = 9
    UV1 = 10
    UV2 = 11
    UV3 = 12
    PDA1 = 13
    PDA2 = 14
    PDA3 = 15


class ToleranceUnits(IntEnum):
    """Mass tolerance units."""

    Daltons = 0
    ppm = 1


class SampleType(IntEnum):
    """Sample types."""

    Unknown = 0
    Blank = 1
    Standard = 2
    QualityControl = 3
    Sample = 4
    CalibrationStandard = 5
    SystemSuitability = 6


class GenericDataTypes(IntEnum):
    """Generic data types for status log and trailer extra fields."""

    NULL = 0
    Double = 1
    String = 2
    DateTime = 3
    Int32 = 4
    Int64 = 5


# Type aliases for clarity
TraceTypeName = str
"""Type alias for trace type names."""
