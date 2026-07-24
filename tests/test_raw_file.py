"""Tests for RawFile class using real test data."""

import pytest

from epyraw import Device, InvalidScanNumberError, RawFile, RawFileNotFoundError, TraceType


class TestRawFileInit:
    """Tests for RawFile initialization."""

    def test_file_not_found(self):
        """Test that FileNotFoundError is raised for missing files."""
        with pytest.raises(RawFileNotFoundError):
            RawFile("/nonexistent/path/file.raw")

    def test_open_valid_file(self, sample_raw_file):
        """Test that a valid RAW file can be opened."""
        with RawFile(str(sample_raw_file)) as rf:
            assert rf.is_open
            assert not rf.is_error

    def test_context_manager_closes_file(self, sample_raw_file):
        """Test that context manager properly closes the file."""
        with RawFile(str(sample_raw_file)) as rf:
            rf.select_instrument(Device.MS, 1)
            assert rf.is_open

        # File should be closed after context
        assert not rf.is_open

    def test_explicit_close(self, sample_raw_file):
        """Test explicit close method."""
        rf = RawFile(str(sample_raw_file))
        rf.select_instrument(Device.MS, 1)
        assert rf.is_open

        rf.close()
        assert not rf.is_open


class TestInstrumentSelection:
    """Tests for instrument selection."""

    def test_select_ms_instrument(self, raw_file):
        """Test selecting MS instrument."""
        # Instrument should already be selected by fixture
        inst_data = raw_file.get_instrument_data()
        assert inst_data.model is not None

    def test_get_instrument_count(self, raw_file):
        """Test getting instrument count."""
        count = raw_file.instrument_count
        assert count >= 1


class TestHeaderProperties:
    """Tests for header property access."""

    def test_filename(self, raw_file, sample_raw_file):
        """Test filename property."""
        assert raw_file.filename == "sample.raw"
        assert raw_file.filepath == str(sample_raw_file)

    def test_file_header(self, raw_file):
        """Test file header access."""
        fh = raw_file.file_header
        assert fh.revision is not None
        assert fh.creation_date is not None
        assert fh.who_created_id is not None

    def test_run_header(self, raw_file):
        """Test run header access."""
        rh = raw_file.run_header
        assert rh.first_spectrum >= 1
        assert rh.last_spectrum >= rh.first_spectrum
        assert rh.spectra_count > 0
        assert rh.start_time >= 0
        assert rh.end_time >= rh.start_time
        assert rh.duration > 0

    def test_run_header_scan_range(self, raw_file):
        """Test run header scan range property."""
        rh = raw_file.run_header
        assert rh.scan_range == (rh.first_spectrum, rh.last_spectrum)

    def test_run_header_time_range(self, raw_file):
        """Test run header time range property."""
        rh = raw_file.run_header
        assert rh.time_range == (rh.start_time, rh.end_time)

    def test_sample_information(self, raw_file):
        """Test sample information access."""
        si = raw_file.sample_information
        assert si is not None
        # Sample name might be empty but object should exist

    def test_instrument_data(self, raw_file):
        """Test instrument data access."""
        inst = raw_file.get_instrument_data()
        assert inst is not None


class TestSpectrumMethods:
    """Tests for spectrum-related methods."""

    def test_get_spectrum_centroid(self, raw_file):
        """Test getting centroid spectrum."""
        run_header = raw_file.run_header
        scan_num = run_header.first_spectrum

        spectrum = raw_file.get_spectrum(scan_num, centroid=True)

        assert spectrum.scan_number == scan_num
        assert spectrum.is_centroid is True
        assert spectrum.num_peaks >= 0

    def test_get_spectrum_profile(self, raw_file):
        """Test getting profile (segmented) spectrum."""
        run_header = raw_file.run_header
        scan_num = run_header.first_spectrum

        spectrum = raw_file.get_spectrum(scan_num, centroid=False)

        assert spectrum.scan_number == scan_num
        assert spectrum.is_centroid is False

    def test_spectrum_mass_range(self, raw_file):
        """Test spectrum mass range property."""
        spectrum = raw_file.get_spectrum(1, centroid=True)

        assert spectrum.num_peaks > 0
        assert spectrum.mass_range[0] < spectrum.mass_range[1]
        assert spectrum.mass_range[0] > 0

    def test_spectrum_base_peak(self, raw_file):
        """Test spectrum base peak property."""
        spectrum = raw_file.get_spectrum(1, centroid=True)

        assert spectrum.num_peaks > 0
        mz, intensity = spectrum.base_peak
        assert mz > 0
        assert intensity > 0

    def test_spectrum_total_ion_current(self, raw_file):
        """Test spectrum total ion current property."""
        spectrum = raw_file.get_spectrum(1, centroid=True)

        assert spectrum.num_peaks > 0
        assert spectrum.total_ion_current > 0

    def test_spectrum_to_pandas(self, raw_file):
        """Test converting spectrum to pandas DataFrame."""
        spectrum = raw_file.get_spectrum(1, centroid=True)

        df = spectrum.to_pandas()
        assert "mass" in df.columns
        assert "intensity" in df.columns

    def test_invalid_scan_number_high(self, raw_file):
        """Test that InvalidScanNumberError is raised for scan too high."""
        run_header = raw_file.run_header
        with pytest.raises(InvalidScanNumberError):
            raw_file.get_spectrum(run_header.last_spectrum + 1000)

    def test_invalid_scan_number_low(self, raw_file):
        """Test that InvalidScanNumberError is raised for scan too low."""
        run_header = raw_file.run_header
        with pytest.raises(InvalidScanNumberError):
            raw_file.get_spectrum(run_header.first_spectrum - 100)

    def test_get_last_spectrum(self, raw_file):
        """Test getting the last spectrum."""
        run_header = raw_file.run_header
        spectrum = raw_file.get_spectrum(run_header.last_spectrum, centroid=True)

        assert spectrum.scan_number == run_header.last_spectrum


class TestChromatogramMethods:
    """Tests for chromatogram-related methods."""

    def test_get_chromatogram_basepeak(self, raw_file):
        """Test getting base peak chromatogram."""
        chrom = raw_file.get_chromatogram(TraceType.BasePeak)

        assert chrom.trace_type == int(TraceType.BasePeak)
        assert chrom.num_points > 0

    def test_get_chromatogram_tic(self, raw_file):
        """Test getting TIC chromatogram."""
        chrom = raw_file.get_chromatogram(TraceType.TIC)

        assert chrom.trace_type == int(TraceType.TIC)
        assert chrom.num_points > 0

    def test_chromatogram_time_range(self, raw_file):
        """Test chromatogram time range matches run header."""
        chrom = raw_file.get_chromatogram(TraceType.BasePeak)
        run_header = raw_file.run_header

        assert chrom.time_range[0] >= run_header.start_time - 0.1
        assert chrom.time_range[1] <= run_header.end_time + 0.1

    def test_chromatogram_to_pandas(self, raw_file):
        """Test converting chromatogram to pandas DataFrame."""
        chrom = raw_file.get_chromatogram(TraceType.BasePeak)

        df = chrom.to_pandas()
        assert "time" in df.columns
        assert "intensity" in df.columns

    def test_chromatogram_with_scan_range(self, raw_file):
        """Test getting chromatogram with specific scan range."""
        run_header = raw_file.run_header
        mid_point = (run_header.first_spectrum + run_header.last_spectrum) // 2

        chrom = raw_file.get_chromatogram(
            TraceType.BasePeak, start_scan=run_header.first_spectrum, end_scan=mid_point
        )

        assert chrom.trace_type == int(TraceType.BasePeak)


class TestUtilityMethods:
    """Tests for utility methods."""

    def test_retention_time_from_scan_number(self, raw_file):
        """Test scan number to retention time conversion."""
        run_header = raw_file.run_header
        rt = raw_file.retention_time_from_scan_number(run_header.first_spectrum)
        assert rt > 0.0

        rt_last = raw_file.retention_time_from_scan_number(run_header.last_spectrum)
        assert rt_last > rt

    def test_scan_number_from_retention_time(self, raw_file):
        """Test retention time to scan number conversion."""
        run_header = raw_file.run_header

        # Get retention time of first scan
        rt = raw_file.retention_time_from_scan_number(run_header.first_spectrum)

        # Convert back to scan number
        scan_num = raw_file.scan_number_from_retention_time(rt)
        assert scan_num == run_header.first_spectrum

    def test_get_filters(self, raw_file):
        """Test getting filter list."""
        filters = raw_file.get_filters()
        assert isinstance(filters, list)
        assert len(filters) > 0

    def test_get_filter_for_scan_number(self, raw_file):
        """Test getting filter for a specific scan."""
        run_header = raw_file.run_header
        sf = raw_file.get_filter_for_scan_number(run_header.first_spectrum)

        assert sf.filter_string is not None
        assert sf.ms_order is not None

    def test_get_trailer_extra_information(self, raw_file):
        """Test getting trailer extra information."""
        run_header = raw_file.run_header
        trailer = raw_file.get_trailer_extra_information(run_header.first_spectrum)

        assert isinstance(trailer, dict)

    def test_status_log_header_information(self, raw_file):
        """Test getting status log header information."""
        fields = raw_file.get_status_log_header_information()
        assert isinstance(fields, list)

    def test_average_scans_not_implemented(self, raw_file):
        """Test that average_scans handles missing feature gracefully.

        The underlying library may not support spectrum averaging,
        in which case an empty spectrum is returned instead of raising.
        """
        run_header = raw_file.run_header

        # Try to average scans - should return a valid (possibly empty) spectrum
        scan_list = [run_header.first_spectrum]
        if run_header.last_spectrum > run_header.first_spectrum:
            scan_list.append(run_header.first_spectrum + 1)

        result = raw_file.average_scans(scan_list)

        # Should return a Spectrum object (may be empty if feature unavailable)
        assert result is not None

    def test_get_inclusion_exclusion_list(self, raw_file):
        """Test getting inclusion/exclusion list."""
        items = raw_file.get_inclusion_exclusion_list()
        assert isinstance(items, list)


class TestDataIntegrity:
    """Tests for data integrity and consistency."""

    def test_spectrum_array_lengths_match(self, raw_file):
        """Test that spectrum mass and intensity arrays have same length."""
        run_header = raw_file.run_header

        for scan_num in [run_header.first_spectrum, run_header.first_spectrum + 1]:
            spectrum = raw_file.get_spectrum(scan_num, centroid=True)
            assert len(spectrum.masses) == len(spectrum.intensities)

    def test_chromatogram_array_lengths_match(self, raw_file):
        """Test that chromatogram time and intensity arrays have same length."""
        chrom = raw_file.get_chromatogram(TraceType.BasePeak)
        assert len(chrom.times) == len(chrom.intensities)

    def test_consistent_retention_times(self, raw_file):
        """Test that retention times are monotonically increasing."""
        chrom = raw_file.get_chromatogram(TraceType.BasePeak)

        if chrom.num_points > 1:
            times = chrom.times
            for i in range(1, len(times)):
                assert times[i] >= times[i - 1], "Retention times should be non-decreasing"
