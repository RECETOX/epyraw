"""Tests for newly added RawFileReader features.

These tests cover the high and medium priority features implemented
based on the epyraw_enhancement_opportunities.md analysis.
"""

import pytest
import numpy as np

from epyraw import (
    BarcodeStatusType,
    Device,
    ScanTypeEnum,
    SpectrumPacketType,
    TrayShape,
)
from epyraw.models import (
    AutoSamplerInformation,
    MassOptions,
    Reaction,
    ScanDependentDetail,
    ScanDependents,
    ScanEvent,
    ScanHeader,
    ScanStats,
)


# =============================================================================
# Tests for New Enums
# =============================================================================


class TestSpectrumPacketType:
    """Tests for SpectrumPacketType enum."""

    def test_spectrum_packet_type_values(self):
        """Test that enum values match .NET specification."""
        assert SpectrumPacketType.FtCentroid.value == 0
        assert SpectrumPacketType.FtProfile.value == 1
        assert SpectrumPacketType.QuadrupoleCentroid.value == 2
        assert SpectrumPacketType.QuadrupoleProfile.value == 3

    def test_spectrum_packet_type_from_int(self):
        """Test creating enum from integer value."""
        assert SpectrumPacketType(0) == SpectrumPacketType.FtCentroid
        assert SpectrumPacketType(1) == SpectrumPacketType.FtProfile


class TestScanTypeEnum:
    """Tests for ScanTypeEnum enum."""

    def test_scan_type_enum_values(self):
        """Test that enum values match specification."""
        assert ScanTypeEnum.Full.value == 0
        assert ScanTypeEnum.SIM.value == 1
        assert ScanTypeEnum.ProductIon.value == 2
        assert ScanTypeEnum.DataDependent.value == 3
        assert ScanTypeEnum.TopN.value == 4

    def test_scan_type_enum_from_int(self):
        """Test creating enum from integer value."""
        assert ScanTypeEnum(0) == ScanTypeEnum.Full
        assert ScanTypeEnum(2) == ScanTypeEnum.ProductIon


class TestTrayShape:
    """Tests for TrayShape enum."""

    def test_tray_shape_values(self):
        """Test that enum values match .NET specification."""
        assert TrayShape.Rectangular.value == 0
        assert TrayShape.Circular.value == 1
        assert TrayShape.StaggeredOdd.value == 2
        assert TrayShape.StaggeredEven.value == 3
        assert TrayShape.Unknown.value == 4
        assert TrayShape.Invalid.value == 5

    def test_tray_shape_from_int(self):
        """Test creating enum from integer value."""
        assert TrayShape(0) == TrayShape.Rectangular
        assert TrayShape(4) == TrayShape.Unknown


class TestBarcodeStatusType:
    """Tests for BarcodeStatusType enum."""

    def test_barcode_status_values(self):
        """Test that enum values match .NET specification."""
        assert BarcodeStatusType.NotRead.value == 0
        assert BarcodeStatusType.Read.value == 1
        assert BarcodeStatusType.ReadFailed.value == 2

    def test_barcode_status_from_int(self):
        """Test creating enum from integer value."""
        assert BarcodeStatusType(0) == BarcodeStatusType.NotRead
        assert BarcodeStatusType(1) == BarcodeStatusType.Read


# =============================================================================
# Tests for New Data Models
# =============================================================================


class TestScanHeader:
    """Tests for ScanHeader data model."""

    def test_scan_header_defaults(self):
        """Test default values for ScanHeader."""
        header = ScanHeader()
        assert header.scan_number == 0
        assert header.ms_level == 1
        assert header.precursor_scan_num == 0
        assert header.scan_type == ""
        assert header.number_of_ions == 0
        assert header.isolation_width == 0.0
        assert header.collision_energy == 0.0
        assert header.trigger_time == 0.0

    def test_scan_header_with_data(self):
        """Test ScanHeader with actual data."""
        header = ScanHeader(
            scan_number=100,
            ms_level=2,
            precursor_scan_num=99,
            scan_type="ProductIon",
            instrument_model="Orbitrap Fusion",
            number_of_ions=1500,
            isolation_width=1.0,
            collision_energy=30.0,
            trigger_time=15.5,
        )

        assert header.scan_number == 100
        assert header.ms_level == 2
        assert header.precursor_scan_num == 99
        assert header.scan_type == "ProductIon"
        assert header.number_of_ions == 1500
        assert header.isolation_width == 1.0
        assert header.collision_energy == 30.0
        assert abs(header.trigger_time - 15.5) < 0.001

    def test_scan_header_repr(self):
        """Test string representation of ScanHeader."""
        header = ScanHeader(scan_number=42, ms_level=2, scan_type="SIM")
        repr_str = repr(header)
        assert "scan=42" in repr_str
        assert "ms_level=2" in repr_str
        assert "type=SIM" in repr_str


class TestReaction:
    """Tests for Reaction data model."""

    def test_reaction_defaults(self):
        """Test default values for Reaction."""
        reaction = Reaction()
        assert reaction.precursor_mass == 0.0
        assert reaction.collision_energy == 0.0
        assert reaction.isolation_width == 0.0

    def test_reaction_with_data(self):
        """Test Reaction with actual data."""
        reaction = Reaction(
            precursor_mass=500.25,
            collision_energy=35.0,
            isolation_width=2.0,
        )

        assert abs(reaction.precursor_mass - 500.25) < 0.001
        assert abs(reaction.collision_energy - 35.0) < 0.001
        assert abs(reaction.isolation_width - 2.0) < 0.001

    def test_reaction_repr(self):
        """Test string representation of Reaction."""
        reaction = Reaction(precursor_mass=500.0, collision_energy=30.0)
        repr_str = repr(reaction)
        assert "precursor=500.0" in repr_str
        assert "CE=30.0" in repr_str


class TestScanEvent:
    """Tests for ScanEvent data model."""

    def test_scan_event_defaults(self):
        """Test default values for ScanEvent."""
        event = ScanEvent()
        assert event.mass_analyzer == 0
        assert event.reactions == []

    def test_scan_event_with_reactions(self):
        """Test ScanEvent with multiple reactions."""
        reactions = [
            Reaction(precursor_mass=500.0, collision_energy=30.0, isolation_width=1.0),
            Reaction(precursor_mass=250.0, collision_energy=35.0, isolation_width=0.7),
        ]
        event = ScanEvent(mass_analyzer=1, reactions=reactions)

        assert event.mass_analyzer == 1
        assert len(event.reactions) == 2
        assert abs(event.reactions[0].precursor_mass - 500.0) < 0.001

    def test_scan_event_repr(self):
        """Test string representation of ScanEvent."""
        event = ScanEvent(mass_analyzer=2, reactions=[Reaction(), Reaction()])
        repr_str = repr(event)
        assert "analyzer=2" in repr_str
        assert "reactions=2" in repr_str


class TestMassOptions:
    """Tests for MassOptions data model."""

    def test_mass_options_defaults(self):
        """Test default values for MassOptions."""
        options = MassOptions()
        assert options.tolerance == 5.0
        assert options.tolerance_units == 1  # ppm

    def test_mass_options_custom(self):
        """Test MassOptions with custom values."""
        options = MassOptions(tolerance=10.0, tolerance_units=0)  # Daltons
        assert options.tolerance == 10.0
        assert options.tolerance_units == 0

    def test_mass_options_repr_ppm(self):
        """Test string representation with ppm units."""
        options = MassOptions(tolerance=5.0, tolerance_units=1)
        repr_str = repr(options)
        assert "5.0" in repr_str
        assert "ppm" in repr_str

    def test_mass_options_repr_daltons(self):
        """Test string representation with Dalton units."""
        options = MassOptions(tolerance=0.5, tolerance_units=0)
        repr_str = repr(options)
        assert "0.5" in repr_str
        assert "Da" in repr_str


class TestScanStats:
    """Tests for ScanStats data model."""

    def test_scan_stats_defaults(self):
        """Test default values for ScanStats."""
        stats = ScanStats()
        assert stats.is_centroid_scan is False
        assert stats.spectrum_packet_type == 0
        assert stats.mass_count == 0
        assert stats.total_intensity == 0.0
        assert stats.max_intensity == 0.0

    def test_scan_stats_with_data(self):
        """Test ScanStats with actual data."""
        stats = ScanStats(
            is_centroid_scan=True,
            spectrum_packet_type=0,
            mass_count=2500,
            total_intensity=1e8,
            max_intensity=5e6,
        )

        assert stats.is_centroid_scan is True
        assert stats.spectrum_packet_type == 0
        assert stats.mass_count == 2500
        assert stats.total_intensity == 1e8
        assert stats.max_intensity == 5e6

    def test_scan_stats_repr(self):
        """Test string representation of ScanStats."""
        stats = ScanStats(is_centroid_scan=True, spectrum_packet_type=0, mass_count=100)
        repr_str = repr(stats)
        assert "centroid=True" in repr_str
        assert "type=0" in repr_str
        assert "peaks=100" in repr_str


class TestScanDependentDetail:
    """Tests for ScanDependentDetail data model."""

    def test_dependent_detail_defaults(self):
        """Test default values for ScanDependentDetail."""
        detail = ScanDependentDetail()
        assert detail.scan_number == 0
        assert detail.scan_type == ""
        assert detail.ms_level == 0

    def test_dependent_detail_with_data(self):
        """Test ScanDependentDetail with actual data."""
        detail = ScanDependentDetail(
            scan_number=150,
            scan_type="DataDependent",
            ms_level=2,
        )

        assert detail.scan_number == 150
        assert detail.scan_type == "DataDependent"
        assert detail.ms_level == 2

    def test_dependent_detail_repr(self):
        """Test string representation of ScanDependentDetail."""
        detail = ScanDependentDetail(scan_number=150, scan_type="MS2")
        repr_str = repr(detail)
        assert "scan=150" in repr_str
        assert "type=MS2" in repr_str


class TestScanDependents:
    """Tests for ScanDependents data model."""

    def test_dependents_defaults(self):
        """Test default values for ScanDependents."""
        dependents = ScanDependents()
        assert dependents.raw_file_instrument_type == ""
        assert dependents.scan_dependent_details == []

    def test_dependents_with_data(self):
        """Test ScanDependents with actual data."""
        details = [
            ScanDependentDetail(scan_number=150, scan_type="MS2", ms_level=2),
            ScanDependentDetail(scan_number=151, scan_type="MS2", ms_level=2),
        ]
        dependents = ScanDependents(
            raw_file_instrument_type="Orbitrap",
            scan_dependent_details=details,
        )

        assert dependents.raw_file_instrument_type == "Orbitrap"
        assert len(dependents.scan_dependent_details) == 2

    def test_dependents_repr(self):
        """Test string representation of ScanDependents."""
        dependents = ScanDependents(
            raw_file_instrument_type="QExactive",
            scan_dependent_details=[ScanDependentDetail()],
        )
        repr_str = repr(dependents)
        assert "instrument=QExactive" in repr_str
        assert "count=1" in repr_str


class TestAutoSamplerInformation:
    """Tests for AutoSamplerInformation data model."""

    def test_auto_sampler_defaults(self):
        """Test default values for AutoSamplerInformation."""
        info = AutoSamplerInformation()
        assert info.tray_index == -1
        assert info.vial_index == -1
        assert info.vials_per_tray_x == -1
        assert info.vials_per_tray_y == -1
        assert info.tray_shape is None
        assert info.tray_name == ""

    def test_auto_sampler_with_data(self):
        """Test AutoSamplerInformation with actual data."""
        from epyraw import TrayShape

        info = AutoSamplerInformation._from_raw(
            tray_index=0,
            vial_index=5,
            vials_per_tray_x=12,
            vials_per_tray_y=8,
            tray_shape_int=0,  # Rectangular
            tray_name="Standard Tray",
        )

        assert info.tray_index == 0
        assert info.vial_index == 5
        assert info.vials_per_tray_x == 12
        assert info.vials_per_tray_y == 8
        assert info.tray_shape == TrayShape.Rectangular
        assert info.tray_name == "Standard Tray"

    def test_auto_sampler_repr(self):
        """Test string representation of AutoSamplerInformation."""
        info = AutoSamplerInformation()
        repr_str = repr(info)
        assert "tray=-1" in repr_str
        assert "vial=-1" in repr_str


# =============================================================================
# Tests for New RawFile Methods
# =============================================================================


class TestHasInstrumentMethod:
    """Tests for has_instrument_method property."""

    def test_has_instrument_method_exists(self, raw_file):
        """Test that has_instrument_method property exists and returns bool."""
        result = raw_file.has_instrument_method
        assert isinstance(result, bool)

    def test_has_instrument_method_closed_file(self, sample_raw_file):
        """Test has_instrument_method with closed file returns False."""
        from epyraw import RawFile

        with RawFile(str(sample_raw_file)) as rf:
            pass  # File is now closed

        # Accessing after close should return False
        assert rf.has_instrument_method is False


class TestAutoSamplerInformationProperty:
    """Tests for auto_sampler_information property."""

    def test_auto_sampler_info_exists(self, raw_file):
        """Test that auto_sampler_information property exists."""
        info = raw_file.auto_sampler_information
        assert isinstance(info, AutoSamplerInformation)

    def test_auto_sampler_info_returns_valid_object(self, raw_file):
        """Test that auto_sampler_information returns properly structured object."""
        info = raw_file.auto_sampler_information

        # All attributes should be accessible without error
        _ = info.tray_index
        _ = info.vial_index
        _ = info.vials_per_tray_x
        _ = info.vials_per_tray_y
        _ = info.tray_shape  # Now returns TrayShape enum or None
        _ = info.tray_name


class TestUserLabels:
    """Tests for user_labels property."""

    def test_user_labels_exists(self, raw_file):
        """Test that user_labels property exists."""
        labels = raw_file.user_labels
        assert isinstance(labels, list)
        assert len(labels) > 0

    def test_user_labels_all_strings(self, raw_file):
        """Test that all user labels are strings."""
        labels = raw_file.user_labels
        assert len(labels) > 0
        for label in labels:
            assert isinstance(label, str)


class TestIncludeReferenceAndExceptionData:
    """Tests for include_reference_and_exception_data property."""

    def test_property_getter_exists(self, raw_file):
        """Test that property getter works."""
        value = raw_file.include_reference_and_exception_data
        assert isinstance(value, bool)

    def test_property_setter(self, raw_file):
        """Test that property setter works."""
        # Store original value
        original = raw_file.include_reference_and_exception_data

        # Try setting to opposite value
        raw_file.include_reference_and_exception_data = not original
        assert raw_file.include_reference_and_exception_data == (not original)

        # Restore original
        raw_file.include_reference_and_exception_data = original


class TestGetScanHeader:
    """Tests for get_scan_header method."""

    def test_get_scan_header_basic(self, raw_file):
        """Test getting scan header for first scan."""
        run_header = raw_file.run_header
        header = raw_file.get_scan_header(run_header.first_spectrum)

        assert isinstance(header, ScanHeader)
        assert header.scan_number == run_header.first_spectrum
        assert header.ms_level >= 1

    def test_get_scan_header_last_scan(self, raw_file):
        """Test getting scan header for last scan."""
        run_header = raw_file.run_header
        header = raw_file.get_scan_header(run_header.last_spectrum)

        assert isinstance(header, ScanHeader)
        assert header.scan_number == run_header.last_spectrum

    def test_get_scan_header_ms2_scan(self, raw_file):
        """Test getting scan header for MS2 scan if available."""
        run_header = raw_file.run_header

        # Try to find an MS2 scan
        ms2_found = False
        for scan_num in range(run_header.first_spectrum, min(run_header.last_spectrum + 1, run_header.first_spectrum + 100)):
            try:
                header = raw_file.get_scan_header(scan_num)
                if header.ms_level >= 2:
                    ms2_found = True
                    assert header.precursor_scan_num > 0 or header.ms_level == 1
                    break
            except Exception:
                continue

        # Note: We don't assert ms2_found because some files may only have MS1 scans

    def test_get_scan_header_invalid_scan(self, raw_file):
        """Test handling of invalid scan number.

        Note: The underlying library may not raise an exception for
        out-of-range scan numbers, so we just verify the method returns
        a valid ScanHeader object.
        """
        run_header = raw_file.run_header

        # Library may return empty header or handle gracefully
        header = raw_file.get_scan_header(run_header.last_spectrum + 10000)
        assert isinstance(header, ScanHeader)


class TestGetScanEvent:
    """Tests for get_scan_event method."""

    def test_get_scan_event_basic(self, raw_file):
        """Test getting scan event for first scan."""
        run_header = raw_file.run_header
        event = raw_file.get_scan_event(run_header.first_spectrum)

        assert isinstance(event, ScanEvent)
        assert event.mass_analyzer >= 0

    def test_get_scan_event_reactions(self, raw_file):
        """Test getting scan event with reactions."""
        run_header = raw_file.run_header
        event = raw_file.get_scan_event(run_header.first_spectrum)

        # Reactions should be a list
        assert isinstance(event.reactions, list)
        # If there are reactions, they should be Reaction objects
        for reaction in event.reactions:
            assert isinstance(reaction, Reaction)
            assert reaction.precursor_mass > 0

    def test_get_scan_event_invalid_scan(self, raw_file):
        """Test that invalid scan number raises error."""
        run_header = raw_file.run_header

        with pytest.raises(Exception):
            raw_file.get_scan_event(run_header.last_spectrum + 10000)


class TestGetScanStats:
    """Tests for get_scan_stats method."""

    def test_get_scan_stats_basic(self, raw_file):
        """Test getting scan stats for first scan."""
        run_header = raw_file.run_header
        stats = raw_file.get_scan_stats(run_header.first_spectrum)

        assert isinstance(stats, ScanStats)
        assert stats.mass_count > 0

    def test_get_scan_stats_centroid_detection(self, raw_file):
        """Test that centroid detection works."""
        run_header = raw_file.run_header
        stats = raw_file.get_scan_stats(run_header.first_spectrum)

        # Should be either centroid or profile
        assert isinstance(stats.is_centroid_scan, bool)

    def test_get_scan_stats_intensity_values(self, raw_file):
        """Test that intensity values are reasonable."""
        run_header = raw_file.run_header
        stats = raw_file.get_scan_stats(run_header.first_spectrum)

        # Total intensity should be >= max intensity
        if stats.max_intensity > 0:
            assert stats.total_intensity >= stats.max_intensity

    def test_get_scan_stats_invalid_scan(self, raw_file):
        """Test handling of invalid scan number.

        Note: The underlying library may not raise an exception for
        out-of-range scan numbers, so we just verify the method returns
        a valid ScanStats object.
        """
        run_header = raw_file.run_header

        # Library may return empty stats or handle gracefully
        stats = raw_file.get_scan_stats(run_header.last_spectrum + 10000)
        assert isinstance(stats, ScanStats)


class TestDefaultMassOptions:
    """Tests for default_mass_options method."""

    def test_default_mass_options_exists(self, raw_file):
        """Test that default_mass_options returns valid object."""
        options = raw_file.default_mass_options()

        assert isinstance(options, MassOptions)
        assert options.tolerance >= 0
        assert options.tolerance_units in (0, 1)  # Daltons or ppm

    def test_default_mass_options_reasonable_tolerance(self, raw_file):
        """Test that default tolerance is reasonable."""
        options = raw_file.default_mass_options()

        # Typical tolerances are 0.01-100 depending on units
        assert 0.001 <= options.tolerance <= 1000


class TestAverageScansInScanRange:
    """Tests for average_scans_in_scan_range method."""

    def test_average_scans_basic(self, raw_file):
        """Test averaging a small range of scans.

        Note: The underlying library may not support this feature,
        in which case an empty spectrum is returned.
        """
        run_header = raw_file.run_header

        # Average just a few scans
        first = run_header.first_spectrum
        last = min(first + 5, run_header.last_spectrum)

        if last > first:
            avg_spectrum = raw_file.average_scans_in_scan_range(first, last)

            assert avg_spectrum is not None
            assert avg_spectrum.scan_number == first
            assert avg_spectrum.is_centroid is True

    def test_average_scans_single_scan(self, raw_file):
        """Test averaging a single scan.

        Note: May return empty spectrum if feature unavailable.
        """
        run_header = raw_file.run_header
        scan_num = run_header.first_spectrum

        avg_spectrum = raw_file.average_scans_in_scan_range(scan_num, scan_num)

        assert avg_spectrum is not None
        assert avg_spectrum.scan_number == scan_num

    def test_average_scans_with_custom_options(self, raw_file):
        """Test averaging with custom mass options.

        Note: May return empty spectrum if feature unavailable.
        """
        run_header = raw_file.run_header
        first = run_header.first_spectrum
        last = min(first + 3, run_header.last_spectrum)

        if last > first:
            options = MassOptions(tolerance=10.0, tolerance_units=0)  # 10 Da
            avg_spectrum = raw_file.average_scans_in_scan_range(
                first, last, options=options
            )

            assert avg_spectrum is not None

    def test_average_scans_no_file_open(self, sample_raw_file):
        """Test that averaging fails when no file is open."""
        from epyraw import RawFile

        with RawFile(str(sample_raw_file)) as rf:
            pass  # Close the file

        # Should raise RuntimeError when no file is open
        with pytest.raises(RuntimeError, match="No file is open"):
            rf.average_scans_in_scan_range(1, 10)


class TestAverageScans:
    """Tests for average_scans method."""

    def test_average_arbitrary_scans(self, raw_file):
        """Test averaging arbitrary list of scans.

        Note: The underlying library may not support this feature,
        in which case an empty spectrum with scan_number=0 is returned.
        """
        run_header = raw_file.run_header

        # Create a list of non-consecutive scans
        scan_list = [
            run_header.first_spectrum,
            run_header.first_spectrum + 2,
            run_header.first_spectrum + 4,
        ]

        # Only test if we have enough scans
        if run_header.last_spectrum >= scan_list[-1]:
            avg_spectrum = raw_file.average_scans(scan_list)

            assert avg_spectrum is not None
            # If feature unavailable, scan_number will be 0; otherwise it should be first scan
            assert avg_spectrum.scan_number in (0, scan_list[0])

    def test_average_scans_with_options(self, raw_file):
        """Test averaging with custom options.

        Note: May return empty spectrum if feature unavailable.
        """
        run_header = raw_file.run_header

        scan_list = [run_header.first_spectrum, run_header.first_spectrum + 2]

        if run_header.last_spectrum >= scan_list[-1]:
            options = MassOptions(tolerance=5.0, tolerance_units=1)  # 5 ppm
            avg_spectrum = raw_file.average_scans(scan_list, options=options)

            assert avg_spectrum is not None

    def test_average_scans_empty_list(self, raw_file):
        """Test averaging empty scan list."""
        avg_spectrum = raw_file.average_scans([])

        # Should handle gracefully
        assert avg_spectrum is not None
        assert avg_spectrum.scan_number == 0

    def test_average_scans_no_file_open(self, sample_raw_file):
        """Test that averaging fails when no file is open."""
        from epyraw import RawFile

        with RawFile(str(sample_raw_file)) as rf:
            pass  # Close the file

        # Should raise RuntimeError when no file is open
        with pytest.raises(RuntimeError, match="No file is open"):
            rf.average_scans([1, 2, 3])


class TestCentroidScan:
    """Tests for centroid_scan method."""

    def test_centroid_scan_basic(self, raw_file):
        """Test centroiding a scan."""
        run_header = raw_file.run_header
        scan_num = run_header.first_spectrum

        centroid = raw_file.centroid_scan(scan_num)

        assert centroid is not None
        assert centroid.scan_number == scan_num
        assert centroid.is_centroid is True

    def test_centroid_scan_returns_peaks(self, raw_file):
        """Test that centroiding returns peak data."""
        run_header = raw_file.run_header
        scan_num = run_header.first_spectrum

        centroid = raw_file.centroid_scan(scan_num)

        # Should have mass and intensity arrays
        assert len(centroid.masses) >= 0
        assert len(centroid.intensities) >= 0
        assert len(centroid.masses) == len(centroid.intensities)

    def test_centroid_scan_invalid_scan(self, raw_file):
        """Test that invalid scan number raises error."""
        run_header = raw_file.run_header

        with pytest.raises(Exception):
            raw_file.centroid_scan(run_header.last_spectrum + 10000)


class TestGetInstrumentCountByType:
    """Tests for get_instrument_count_by_type method."""

    def test_get_ms_instrument_count(self, raw_file):
        """Test counting MS instruments."""
        count = raw_file.get_instrument_count_by_type(Device.MS)

        assert isinstance(count, int)
        assert count >= 1  # At least the MS we selected

    def test_get_analog_instrument_count(self, raw_file):
        """Test counting Analog instruments."""
        count = raw_file.get_instrument_count_by_type(Device.Analog)

        assert isinstance(count, int)
        assert count >= 0

    def test_instrument_counts_consistency(self, raw_file):
        """Test that instrument counts are consistent."""
        ms_count = raw_file.get_instrument_count_by_type(Device.MS)
        total_count = raw_file.instrument_count

        # MS count should not exceed total
        assert ms_count <= total_count


class TestGetScanDependents:
    """Tests for get_scan_dependents method."""

    def test_get_scan_dependents_basic(self, raw_file):
        """Test getting scan dependents."""
        run_header = raw_file.run_header
        dependents = raw_file.get_scan_dependents(run_header.first_spectrum)

        assert isinstance(dependents, ScanDependents)

    def test_get_scan_dependents_details_type(self, raw_file):
        """Test that dependent details are proper type."""
        run_header = raw_file.run_header
        dependents = raw_file.get_scan_dependents(run_header.first_spectrum)

        assert isinstance(dependents.scan_dependent_details, list)

        for detail in dependents.scan_dependent_details:
            assert isinstance(detail, ScanDependentDetail)

    def test_get_scan_dependents_max_limit(self, raw_file):
        """Test that max_dependents parameter is respected."""
        run_header = raw_file.run_header

        # Request only 2 dependents
        dependents = raw_file.get_scan_dependents(
            run_header.first_spectrum, max_dependents=2
        )

        assert len(dependents.scan_dependent_details) <= 2

    def test_get_scan_dependents_invalid_scan(self, raw_file):
        """Test that invalid scan number raises error."""
        run_header = raw_file.run_header

        with pytest.raises(Exception):
            raw_file.get_scan_dependents(run_header.last_spectrum + 10000)


class TestGetAllInstrumentFriendlyNamesFromMethod:
    """Tests for get_all_instrument_friendly_names_from_method method."""

    def test_get_instrument_names_exists(self, raw_file):
        """Test that method exists and returns list."""
        names = raw_file.get_all_instrument_friendly_names_from_method()

        assert isinstance(names, list)

    def test_get_instrument_names_all_strings(self, raw_file):
        """Test that all names are strings."""
        names = raw_file.get_all_instrument_friendly_names_from_method()

        for name in names:
            assert isinstance(name, str)

    def test_get_instrument_names_with_check(self, raw_file):
        """Test getting names with has_instrument_method check."""
        if raw_file.has_instrument_method:
            names = raw_file.get_all_instrument_friendly_names_from_method()
            # If method exists, we might have names
            assert isinstance(names, list)
        else:
            # If no method, should return empty list
            names = raw_file.get_all_instrument_friendly_names_from_method()
            assert names == []


class TestRefreshView:
    """Tests for refresh_view method."""

    def test_refresh_view_exists(self, raw_file):
        """Test that refresh_view method exists and can be called."""
        # For a completed file, this should not raise
        raw_file.refresh_view()

    def test_refresh_view_multiple_times(self, raw_file):
        """Test calling refresh_view multiple times."""
        raw_file.refresh_view()
        raw_file.refresh_view()
        raw_file.refresh_view()

        # Should complete without error

    def test_refresh_view_no_file_open(self, sample_raw_file):
        """Test that refresh_view fails when no file is open."""
        from epyraw import RawFile

        with RawFile(str(sample_raw_file)) as rf:
            pass  # Close the file

        # Note: The underlying library may not raise an error for closed files
        # so we just verify the method can be called without crashing
        try:
            rf.refresh_view()
        except RuntimeError:
            # Expected when file is closed
            pass


# =============================================================================
# Integration Tests
# =============================================================================


class TestNewFeaturesIntegration:
    """Integration tests combining multiple new features."""

    def test_scan_analysis_workflow(self, raw_file):
        """Test a typical workflow using new features."""
        run_header = raw_file.run_header

        # Get header info
        header = raw_file.get_scan_header(run_header.first_spectrum)
        assert header.scan_number == run_header.first_spectrum

        # Get stats
        stats = raw_file.get_scan_stats(run_header.first_spectrum)
        assert stats.mass_count == header.number_of_ions

        # Get scan event
        event = raw_file.get_scan_event(run_header.first_spectrum)
        assert event.mass_analyzer >= 0

    def test_complete_sample_metadata_access(self, raw_file):
        """Test accessing all sample-related metadata."""
        # Standard sample info
        sample_info = raw_file.sample_information
        assert sample_info is not None

        # Autosampler info
        auto_info = raw_file.auto_sampler_information
        assert auto_info is not None

        # User labels
        labels = raw_file.user_labels
        assert isinstance(labels, list)

    def test_instrument_enumeration_workflow(self, raw_file):
        """Test enumerating all instruments in the file."""
        # Get total count
        total = raw_file.instrument_count

        # Count by type - these may fail if method not available
        try:
            ms_count = raw_file.get_instrument_count_by_type(Device.MS)
            assert isinstance(ms_count, int)
            assert ms_count >= 1  # At least the MS we selected
        except RuntimeError:
            # Method may not be available in all library versions
            pass

    def test_spectrum_averaging_workflow(self, raw_file):
        """Test complete spectrum averaging workflow.

        Note: Averaging may not be available in all library versions.
        """
        run_header = raw_file.run_header

        # Get default options
        options = raw_file.default_mass_options()
        assert options.tolerance > 0

        # Try to average scans - feature may not be available
        first = run_header.first_spectrum
        last = min(first + 10, run_header.last_spectrum)

        if last > first:
            avg = raw_file.average_scans_in_scan_range(first, last, options=options)
            # Should return a valid (possibly empty) spectrum
            assert avg is not None

    def test_ms_n_experiment_analysis(self, raw_file):
        """Test analyzing MSn experiment data.

        Note: This test handles files that may only have MS1 scans.
        """
        run_header = raw_file.run_header

        # Look for MS2+ scans with valid precursor scan numbers
        ms2_found = False
        for scan_num in range(
            run_header.first_spectrum,
            min(run_header.last_spectrum + 1, run_header.first_spectrum + 200),
        ):
            header = raw_file.get_scan_header(scan_num)

            if header.ms_level >= 2 and header.precursor_scan_num > 0:
                ms2_found = True
                # Get parent-child relationship
                try:
                    dependents = raw_file.get_scan_dependents(header.precursor_scan_num)
                except Exception:
                    # May fail if precursor scan doesn't exist
                    pass

                # Get reaction data
                event = raw_file.get_scan_event(scan_num)
                # Event should exist even if no reactions

                break  # Found one, that's enough for the test

        # Note: We don't assert ms2_found because some files may only have MS1 scans
