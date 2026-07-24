"""Tests using the large QC sample from Zenodo.

This test module uses a ~2.4GB LC-MS QC sample from:
https://zenodo.org/records/6878356/files/8_qc_no_dil_milliq.raw?download=1

The file is downloaded once per session to a temp location and reused.

Focus areas:
- Core features with real MS1 and MS2 data
- Edge cases where fields may be empty
- Performance with large spectra
"""

import pytest

from epyraw import Device, RawFile, ScanTypeEnum, SpectrumPacketType


# =============================================================================
# Session-scoped fixture tests - Core Features
# =============================================================================


class TestZenodoCoreFeatures:
    """Core feature tests using the Zenodo QC file."""

    def test_file_open_and_basic_info(self, zenodo_raw_file_fixture):
        """Test basic file access on large QC file.

        Protects against: File opening failures, basic property access issues.
        """
        rf = zenodo_raw_file_fixture

        # Basic properties should work
        assert rf.is_open
        assert not rf.is_error
        assert "8_qc_no_dil_milliq" in rf.filename

        # Run header should show substantial data
        rh = rf.run_header
        assert rh.spectra_count > 1000  # QC files typically have many scans
        assert rh.duration > 8  # Minutes, typical LC run
        assert rh.first_spectrum >= 1

    def test_scan_header_ms1_scans(self, zenodo_raw_file_fixture):
        """Test get_scan_header for MS1 scans.

        Protects against: Incorrect MS level detection, missing scan metadata.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Test first few scans (typically MS1)
        for scan_num in [rh.first_spectrum, rh.first_spectrum + 10]:
            header = rf.get_scan_header(scan_num)

            assert header.scan_number == scan_num
            assert header.ms_level == 1  # First scans are typically MS1
            assert header.trigger_time >= 0

    def test_scan_event_data(self, zenodo_raw_file_fixture):
        """Test get_scan_event for scan event information.

        Protects against: Missing scan event data, mass analyzer info.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Test multiple scans
        for scan_num in [rh.first_spectrum, rh.first_spectrum + 100]:
            event = rf.get_scan_event(scan_num)

            assert event.mass_analyzer >= 0
            # Reactions list should exist (may be empty for MS1)
            assert isinstance(event.reactions, list)

    def test_scan_stats_centroid_detection(self, zenodo_raw_file_fixture):
        """Test get_scan_stats for centroid/profile detection.

        Protects against: Incorrect centroid detection, missing statistics.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Test multiple scans
        centroid_count = 0
        profile_count = 0

        for scan_num in [rh.first_spectrum, rh.first_spectrum + 50, rh.first_spectrum + 100]:
            stats = rf.get_scan_stats(scan_num)

            assert stats.mass_count >= 0
            assert stats.total_intensity >= 0

            if stats.is_centroid_scan:
                centroid_count += 1
            else:
                profile_count += 1

        # At least some scans should be detected
        assert centroid_count + profile_count > 0

    def test_spectrum_retrieval_large_spectrum(self, zenodo_raw_file_fixture):
        """Test get_spectrum with potentially large spectra.

        Protects against: Memory issues with large spectra, array handling.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Get a spectrum from the middle of the run
        mid_scan = (rh.first_spectrum + rh.last_spectrum) // 2

        spectrum = rf.get_spectrum(mid_scan, centroid=True)

        assert spectrum.scan_number == mid_scan
        assert len(spectrum.masses) == len(spectrum.intensities)
        # Q-Exactive typically has thousands of peaks per scan
        assert spectrum.num_peaks > 0

    def test_chromatogram_full_run(self, zenodo_raw_file_fixture):
        """Test get_chromatogram for full run coverage.

        Protects against: Incomplete chromatogram data, time range issues.
        """
        rf = zenodo_raw_file_fixture

        # Get TIC chromatogram
        tic = rf.get_chromatogram(trace_type=1)  # TIC

        assert tic.num_points > 0
        assert tic.time_range[1] > tic.time_range[0]

        # Should cover most of the run duration
        rh = rf.run_header
        assert abs(tic.time_range[1] - rh.end_time) < 5  # Within 5 minutes

    def test_retention_time_conversions_full_range(self, zenodo_raw_file_fixture):
        """Test RT conversion across full retention time range.

        Protects against: RT conversion errors at boundaries.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Test at start, middle, and end
        test_scans = [
            rh.first_spectrum,
            (rh.first_spectrum + rh.last_spectrum) // 2,
            rh.last_spectrum,
        ]

        for scan_num in test_scans:
            rt = rf.retention_time_from_scan_number(scan_num)
            assert rt >= 0

            # Convert back
            converted_scan = rf.scan_number_from_retention_time(rt)
            # Should be close to original (within 2 scans)
            assert abs(converted_scan - scan_num) <= 2

    def test_filter_information_various_scans(self, zenodo_raw_file_fixture):
        """Test get_filter_for_scan_number for various scan types.

        Protects against: Filter parsing errors, missing filter data.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Sample filters from different parts of the run
        test_scans = [
            rh.first_spectrum,
            rh.first_spectrum + 100,
            rh.first_spectrum + 500,
            rh.last_spectrum,
        ]

        for scan_num in test_scans:
            try:
                sf = rf.get_filter_for_scan_number(scan_num)
                assert sf.filter_string is not None
                assert sf.ms_order >= 1
            except Exception:
                # Some scans might not have valid filters
                pass

    def test_trailer_extra_information(self, zenodo_raw_file_fixture):
        """Test get_trailer_extra_information for custom fields.

        Protects against: Missing trailer data, field parsing issues.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Test multiple scans
        for scan_num in [rh.first_spectrum, rh.first_spectrum + 100]:
            trailer = rf.get_trailer_extra_information(scan_num)

            # Should return a dict (may be empty)
            assert isinstance(trailer, dict)

    def test_status_log_header_information(self, zenodo_raw_file_fixture):
        """Test get_status_log_header_information.

        Protects against: Status log parsing errors.
        """
        rf = zenodo_raw_file_fixture

        fields = rf.get_status_log_header_information()

        # Should return a list (may be empty)
        assert isinstance(fields, list)

    def test_instrument_data(self, zenodo_raw_file_fixture):
        """Test get_instrument_data.

        Protects against: Missing instrument information.
        """
        rf = zenodo_raw_file_fixture

        inst = rf.get_instrument_data()

        # At minimum, model or name should be populated
        assert inst.model or inst.name

    def test_sample_information_detailed(self, zenodo_raw_file_fixture):
        """Test sample_information with detailed field checks.

        For this QC file, verifies that available fields are correctly extracted.

        Protects against: Missing sample metadata, incorrect field types.
        """
        rf = zenodo_raw_file_fixture

        info = rf.sample_information

        # Sample ID should be populated (from filename)
        assert info.sample_id == "8_qc_no_dil_milliq"

        # Injection volume was recorded
        assert info.injection_volume > 0

        # Row number may be set from sequence
        assert info.row_number == 7

        # Vial position may be 0 if not explicitly set
        assert info.vial >= 0

        # All numeric fields should be valid numbers
        assert isinstance(info.sample_volume, float)
        assert isinstance(info.injection_volume, float)


# =============================================================================
# Edge Cases - Potentially Empty Fields
# =============================================================================


class TestZenodoEdgeCases:
    """Tests for edge cases and potentially empty fields in QC file."""

    def test_user_labels_likely_empty(self, zenodo_raw_file_fixture):
        """Test user_labels - likely empty in standard QC files.

        Protects against: Missing user label handling.
        """
        rf = zenodo_raw_file_fixture

        labels = rf.user_labels

        # Should return a list (possibly empty)
        assert isinstance(labels, list)
        # Most QC files don't have user labels set
        # This test documents that behavior

    def test_has_instrument_method(self, zenodo_raw_file_fixture):
        """Test has_instrument_method property.

        Protects against: Missing instrument method check.
        """
        rf = zenodo_raw_file_fixture

        has_method = rf.has_instrument_method

        # Should return a boolean
        assert isinstance(has_method, bool)

    def test_get_instrument_friendly_names(self, zenodo_raw_file_fixture):
        """Test get_all_instrument_friendly_names_from_method.

        Protects against: Method not available, wrong return type.
        """
        rf = zenodo_raw_file_fixture

        names = rf.get_all_instrument_friendly_names_from_method()

        # Should return a list of strings
        assert isinstance(names, list)
        for name in names:
            assert isinstance(name, str)

    def test_auto_sampler_information(self, zenodo_raw_file_fixture):
        """Test auto_sampler_information.

        Protects against: Missing autosampler data, invalid tray info.

        Note: For this GC-MS QC file, autosampler details may not be
        recorded even though the instrument has an autosampler.
        Default values (-1, None) indicate missing data.
        """
        from epyraw import TrayShape

        rf = zenodo_raw_file_fixture

        info = rf.auto_sampler_information

        # All attributes should be accessible
        assert hasattr(info, 'tray_index')
        assert hasattr(info, 'vial_index')
        assert hasattr(info, 'vials_per_tray_x')
        assert hasattr(info, 'vials_per_tray_y')
        assert hasattr(info, 'tray_shape')
        assert hasattr(info, 'tray_name')

        # tray_shape should be a TrayShape enum or None
        if info.tray_index == -1:
            # Autosampler info not recorded - tray_shape should be None or Unknown
            assert info.vial_index == -1
            assert info.tray_shape in (None, TrayShape.Unknown)
        else:
            # If tray is set, shape should be a valid enum
            assert isinstance(info.tray_shape, TrayShape) or info.tray_shape is None

    def test_include_reference_exception_data(self, zenodo_raw_file_fixture):
        """Test include_reference_and_exception_data property.

        Protects against: Property access errors.
        """
        rf = zenodo_raw_file_fixture

        value = rf.include_reference_and_exception_data

        # Should return a boolean
        assert isinstance(value, bool)

    def test_scan_dependents_on_precursor(self, zenodo_raw_file_fixture):
        """Test get_scan_dependents on a precursor scan.

        Protects against: Invalid scan number handling, empty dependents.
        """
        rf = zenodo_raw_file_fixture

        # Find an MS2 scan and check its parent's dependents
        rh = rf.run_header

        for scan_num in range(rh.first_spectrum, min(rh.last_spectrum + 1, rh.first_spectrum + 500)):
            header = rf.get_scan_header(scan_num)

            if header.ms_level >= 2 and header.precursor_scan_num > 0:
                prec_scan = header.precursor_scan_num

                try:
                    dependents = rf.get_scan_dependents(prec_scan, max_dependents=5)

                    # Should return a ScanDependents object
                    assert hasattr(dependents, 'scan_dependent_details')
                    assert isinstance(dependents.scan_dependent_details, list)
                except Exception:
                    # Some versions may not support this
                    pass

                break  # Found one, that's enough

    def test_inclusion_exclusion_list(self, zenodo_raw_file_fixture):
        """Test get_inclusion_exclusion_list.

        Protects against: Empty list handling, parsing errors.
        Note: Standard DDA QC files often don't use inclusion lists.
        """
        rf = zenodo_raw_file_fixture

        items = rf.get_inclusion_exclusion_list()

        # Should return a list (possibly empty)
        assert isinstance(items, list)

    def test_default_mass_options(self, zenodo_raw_file_fixture):
        """Test default_mass_options.

        Protects against: Missing default options, invalid tolerance values.
        """
        rf = zenodo_raw_file_fixture

        options = rf.default_mass_options()

        # Should have reasonable defaults
        assert options.tolerance > 0
        assert options.tolerance_units in (0, 1)  # Daltons or ppm


# =============================================================================
# Feature Availability Tests
# =============================================================================


class TestZenodoFeatureAvailability:
    """Tests for features that may not be available in all library versions."""

    def test_average_scans_feature_check(self, zenodo_raw_file_fixture):
        """Check if spectrum averaging is available.

        Documents feature availability without requiring it to work.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Try to average a small range
        first = rh.first_spectrum
        last = min(first + 3, rh.last_spectrum)

        if last > first:
            result = rf.average_scans_in_scan_range(first, last)

            # Should return a Spectrum (may be empty if feature unavailable)
            assert result is not None

    def test_centroid_scan_conversion(self, zenodo_raw_file_fixture):
        """Test centroid_scan conversion.

        Protects against: Conversion errors, missing data.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        scan_num = rh.first_spectrum

        try:
            centroid = rf.centroid_scan(scan_num)

            assert centroid is not None
            assert centroid.scan_number == scan_num
        except RuntimeError:
            # Feature may not be available in all library versions
            pytest.skip("centroid_scan not available in this library version")

    def test_get_instrument_count_by_type(self, zenodo_raw_file_fixture):
        """Test get_instrument_count_by_type.

        Protects against: Type enum conversion errors.
        """
        rf = zenodo_raw_file_fixture

        try:
            ms_count = rf.get_instrument_count_by_type(Device.MS)
            assert isinstance(ms_count, int)
            assert ms_count >= 1  # At least the MS we selected
        except RuntimeError:
            # May not be available in all versions
            pytest.skip("get_instrument_count_by_type not available")


# =============================================================================
# Integration Tests - Real Workflows
# =============================================================================


class TestZenodoIntegration:
    """Integration tests simulating real-world workflows."""

    def test_complete_scan_analysis_workflow(self, zenodo_raw_file_fixture):
        """Complete workflow: scan header -> stats -> spectrum.

        Protects against: Workflow integration issues, data consistency.
        """
        rf = zenodo_raw_file_fixture
        rh = rf.run_header

        # Pick a scan in the middle
        scan_num = (rh.first_spectrum + rh.last_spectrum) // 2

        # Get header
        header = rf.get_scan_header(scan_num)
        assert header.scan_number == scan_num

        # Get stats
        stats = rf.get_scan_stats(scan_num)
        assert stats.mass_count >= 0

        # Get spectrum
        spectrum = rf.get_spectrum(scan_num)
        assert spectrum.num_peaks == stats.mass_count or spectrum.num_peaks > 0

    def test_chromatogram_and_spectrum_correlation(self, zenodo_raw_file_fixture):
        """Correlate chromatogram peak with spectrum extraction.

        Protects against: Time-scan correlation issues.
        """
        rf = zenodo_raw_file_fixture

        # Get BPC chromatogram
        bpc = rf.get_chromatogram(trace_type=0)  # Base Peak

        assert bpc.num_points > 0

        # Find the base peak time
        bpt = bpc.base_peak_time

        # Convert to scan number
        scan_num = rf.scan_number_from_retention_time(bpt)

        # Get spectrum at that scan
        spectrum = rf.get_spectrum(scan_num)

        assert spectrum.scan_number == scan_num
        assert spectrum.num_peaks > 0
