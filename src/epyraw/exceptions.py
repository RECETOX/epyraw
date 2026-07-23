"""Custom exceptions for Thermo RawFile Reader."""


class ThermoRawFileError(Exception):
    """Base exception for Thermo RawFile Reader errors."""

    pass


class RawFileNotFoundError(ThermoRawFileError):
    """Raised when the RAW file cannot be found."""

    pass


class RawFileOpenError(ThermoRawFileError):
    """Raised when the RAW file cannot be opened."""

    pass


class RawFileCorruptedError(ThermoRawFileError):
    """Raised when the RAW file is corrupted or has read errors."""

    pass


class InvalidScanNumberError(ThermoRawFileError):
    """Raised when an invalid scan number is requested."""

    pass


class InstrumentNotSelectedError(ThermoRawFileError):
    """Raised when an operation requires instrument selection."""

    pass


class AssemblyLoadError(ThermoRawFileError):
    """Raised when a .NET assembly fails to load."""

    pass


class InitializationError(ThermoRawFileError):
    """Raised when the .NET runtime fails to initialize."""

    pass
