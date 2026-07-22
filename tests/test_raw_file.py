"""Tests for RawFile class."""

import pytest
from thermo_raw_file_reader import (
    Device,
    RawFile,
    RawFileNotFoundError,
    ThermoRawFileError,
)


class TestRawFileInit:
    """Tests for RawFile initialization."""

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        with pytest.raises(RawFileNotFoundError):
            RawFile("/nonexistent/path/file.raw")

    def test_invalid_extension(self, tmp_path):
        """Test that appropriate error is raised for non-RAW files."""
        # Create a dummy file with wrong extension
        dummy_file = tmp_path / "test.txt"
        dummy_file.write_text("not a raw file")

        # Should raise an error when trying to open as RAW file
        with pytest.raises(ThermoRawFileError):
            RawFile(str(dummy_file))


class TestSpectrumMethods:
    """Tests for spectrum-related methods."""

    def test_get_spectrum_centroid(self, raw_file):
        """Test getting centroid spectrum."""
        if raw_file is None:
            pytest.skip("No test file available")

        run_header = raw_file.run_header
        if run_header.spectra_count == 0:
            pytest.skip("No scans in test file")

        scan_num = run_header.first_spectrum
        spectrum = raw_file.get_spectrum(scan_num, centroid=True)

        assert spectrum.scan_number == scan_num
        assert spectrum.is_centroid is True
        assert hasattr(spectrum, 'num_peaks')

    def test_get_spectrum_profile(self, raw_file):
        """Test getting profile (segmented) spectrum."""
        if raw_file is None:
            pytest.skip("No test file available")

        run_header = raw_file.run_header
        if run_header.spectra_count == 0:
            pytest.skip("No scans in test file")

        scan_num = run_header.first_spectrum
        spectrum = raw_file.get_spectrum(scan_num, centroid=False)

        assert spectrum.scan_number == scan_num
        assert spectrum.is_centroid is False

    def test_invalid_scan_number(self, raw_file):
        """Test that InvalidScanNumberError is raised for invalid scan."""
        if raw_file is None:
            pytest.skip("No test file available")

        from thermo_raw_file_reader import InvalidScanNumberError

        with pytest.raises(InvalidScanNumberError):
            raw_file.get_spectrum(999999)


class TestChromatogramMethods:
    """Tests for chromatogram-related methods."""

    def test_get_chromatogram_basepeak(self, raw_file):
        """Test getting base peak chromatogram."""
        if raw_file is None:
            pytest.skip("No test file available")

        from thermo_raw_file_reader import TraceType

        chrom = raw_file.get_chromatogram(TraceType.BasePeak)

        assert chrom.trace_type == int(TraceType.BasePeak)
        # Chromatogram may be empty if no data available

    def test_get_chromatogram_tic(self, raw_file):
        """Test getting TIC chromatogram."""
        if raw_file is None:
            pytest.skip("No test file available")

        from thermo_raw_file_reader import TraceType

        chrom = raw_file.get_chromatogram(TraceType.TIC)

        assert chrom.trace_type == int(TraceType.TIC)


class TestHeaderProperties:
    """Tests for header property access."""

    def test_file_header(self, raw_file):
        """Test file header access."""
        if raw_file is None:
            pytest.skip("No test file available")

        fh = raw_file.file_header
        assert fh.revision is not None
        assert fh.creation_date is not None

    def test_run_header(self, raw_file):
        """Test run header access."""
        if raw_file is None:
            pytest.skip("No test file available")

        rh = raw_file.run_header
        assert rh.first_spectrum >= 1
        assert rh.last_spectrum >= rh.first_spectrum
        assert rh.spectra_count > 0

    def test_sample_information(self, raw_file):
        """Test sample information access."""
        if raw_file is None:
            pytest.skip("No test file available")

        si = raw_file.sample_information
        assert si is not None


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_retention_time_conversion(self, raw_file):
        """Test scan number to retention time conversion."""
        if raw_file is None:
            pytest.skip("No test file available")

        run_header = raw_file.run_header
        if run_header.spectra_count == 0:
            pytest.skip("No scans in test file")

        rt = raw_file.retention_time_from_scan_number(run_header.first_spectrum)
        assert rt >= 0.0

    def test_get_filters(self, raw_file):
        """Test getting filter list."""
        if raw_file is None:
            pytest.skip("No test file available")

        filters = raw_file.get_filters()
        assert isinstance(filters, list)

    def test_get_trailer_extra(self, raw_file):
        """Test getting trailer extra information."""
        if raw_file is None:
            pytest.skip("No test file available")

        run_header = raw_file.run_header
        if run_header.spectra_count == 0:
            pytest.skip("No scans in test file")

        trailer = raw_file.get_trailer_extra_information(run_header.first_spectrum)
        assert isinstance(trailer, dict)


class TestContextManager:
    """Tests for context manager functionality."""

    def test_context_manager(self, sample_raw_file):
        """Test using RawFile as context manager."""
        if sample_raw_file is None:
            pytest.skip("No test file available")

        from thermo_raw_file_reader import Device

        with RawFile(str(sample_raw_file)) as rf:
            rf.select_instrument(Device.MS, 1)
            assert rf.is_open

        # File should be closed after context
        assert not rf.is_open
