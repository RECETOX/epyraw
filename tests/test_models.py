"""Tests for data model classes."""

import numpy as np

from epyraw.models import (
    AutoSamplerInformation,
    Chromatogram,
    FileHeader,
    InclusionListItem,
    InstrumentData,
    MassOptions,
    Reaction,
    RunHeader,
    SampleInformation,
    ScanDependentDetail,
    ScanDependents,
    ScanEvent,
    ScanFilter,
    ScanHeader,
    ScanStats,
    Spectrum,
    StatusLogField,
)


class TestSpectrum:
    """Tests for Spectrum class."""

    def test_empty_spectrum(self):
        """Test creating empty spectrum."""
        spec = Spectrum()
        assert spec.num_peaks == 0
        assert spec.mass_range == (0.0, 0.0)
        assert spec.intensity_range == (0.0, 0.0)

    def test_spectrum_with_data(self):
        """Test spectrum with actual data."""
        masses = np.array([100.0, 200.0, 300.0])
        intensities = np.array([1000.0, 5000.0, 2000.0])

        spec = Spectrum(
            masses=masses,
            intensities=intensities,
            scan_number=42,
            is_centroid=True,
        )

        assert spec.num_peaks == 3
        assert spec.mass_range == (100.0, 300.0)
        assert spec.intensity_range == (1000.0, 5000.0)
        assert spec.scan_number == 42
        assert spec.base_peak == (200.0, 5000.0)
        assert spec.total_ion_current == 8000.0

    def test_spectrum_charges(self):
        """Test spectrum with charge states."""
        masses = np.array([100.0, 200.0])
        intensities = np.array([1000.0, 2000.0])
        charges = np.array([1, 2])

        spec = Spectrum(masses=masses, intensities=intensities, charges=charges)

        assert spec.charges is not None
        np.testing.assert_array_equal(spec.charges, charges)

    def test_spectrum_to_pandas(self):
        """Test converting spectrum to pandas DataFrame."""
        masses = np.array([100.0, 200.0])
        intensities = np.array([1000.0, 2000.0])

        spec = Spectrum(masses=masses, intensities=intensities, scan_number=1)
        df = spec.to_pandas()

        assert "mass" in df.columns
        assert "intensity" in df.columns
        assert len(df) == 2


class TestChromatogram:
    """Tests for Chromatogram class."""

    def test_empty_chromatogram(self):
        """Test creating empty chromatogram."""
        chrom = Chromatogram()
        assert chrom.num_points == 0
        assert chrom.time_range == (0.0, 0.0)

    def test_chromatogram_with_data(self):
        """Test chromatogram with actual data."""
        times = np.array([0.0, 1.0, 2.0, 3.0])
        intensities = np.array([100.0, 500.0, 300.0, 100.0])

        chrom = Chromatogram(times=times, intensities=intensities, trace_type=0)

        assert chrom.num_points == 4
        assert chrom.time_range == (0.0, 3.0)
        assert chrom.base_peak_time == 1.0
        assert chrom.base_peak_intensity == 500.0

    def test_chromatogram_with_mass_range(self):
        """Test extracted ion chromatogram with mass range."""
        times = np.array([0.0, 1.0, 2.0])
        intensities = np.array([100.0, 200.0, 100.0])

        chrom = Chromatogram(
            times=times,
            intensities=intensities,
            trace_type=0,
            mass_range=(100.0, 101.0),
        )

        assert chrom.mass_range == (100.0, 101.0)

    def test_chromatogram_to_pandas(self):
        """Test converting chromatogram to pandas DataFrame."""
        times = np.array([0.0, 1.0, 2.0])
        intensities = np.array([100.0, 200.0, 100.0])

        chrom = Chromatogram(times=times, intensities=intensities)
        df = chrom.to_pandas()

        assert "time" in df.columns
        assert "intensity" in df.columns
        assert len(df) == 3


class TestRunHeader:
    """Tests for RunHeader class."""

    def test_run_header_properties(self):
        """Test run header computed properties."""
        rh = RunHeader(
            first_spectrum=1,
            last_spectrum=100,
            start_time=0.0,
            end_time=60.0,
            spectra_count=100,
        )

        assert rh.scan_range == (1, 100)
        assert rh.time_range == (0.0, 60.0)
        assert rh.duration == 60.0


class TestScanFilter:
    """Tests for ScanFilter class."""

    def test_scan_filter_repr(self):
        """Test scan filter string representation."""
        sf = ScanFilter(filter_string="FTMS + p ESI Full ms")
        assert "FTMS" in repr(sf)


class TestFileHeader:
    """Tests for FileHeader class."""

    def test_file_header_defaults(self):
        """Test file header default values."""
        fh = FileHeader()
        assert fh.revision == ""
        assert fh.creation_date == ""


class TestSampleInformation:
    """Tests for SampleInformation class."""

    def test_sample_information_defaults(self):
        """Test sample information default values."""
        si = SampleInformation()
        assert si.sample_name == ""
        assert si.vial == 0
        assert si.sample_volume == 0.0


class TestInstrumentData:
    """Tests for InstrumentData class."""

    def test_instrument_data_defaults(self):
        """Test instrument data default values."""
        inst = InstrumentData()
        assert inst.model == ""
        assert inst.serial_number == ""


class TestInclusionListItem:
    """Tests for InclusionListItem class."""

    def test_inclusion_item_repr(self):
        """Test inclusion item string representation."""
        item = InclusionListItem(
            mass=500.0,
            threshold=1000.0,
            descriptor="Test Compound",
        )
        assert "inclusion" in repr(item)
        assert "500.0" in repr(item)

    def test_exclusion_item_repr(self):
        """Test exclusion item string representation."""
        item = InclusionListItem(
            mass=500.0,
            is_exclusion=True,
        )
        assert "exclusion" in repr(item)


class TestStatusLogField:
    """Tests for StatusLogField class."""

    def test_status_log_field(self):
        """Test status log field creation."""
        field = StatusLogField(label="Test Field", data_type=1)
        assert "Test Field" in repr(field)


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
        assert abs(header.isolation_width - 1.0) < 0.001
        assert abs(header.collision_energy - 30.0) < 0.001
        assert abs(header.trigger_time - 15.5) < 0.001

    def test_scan_header_repr(self):
        """Test string representation of ScanHeader."""
        header = ScanHeader(scan_number=42, ms_level=2, scan_type="SIM")
        repr_str = repr(header)
        assert "scan=42" in repr_str
        assert "ms_level=2" in repr_str


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

    def test_auto_sampler_unknown_shape(self):
        """Test AutoSamplerInformation with unknown tray shape."""
        info = AutoSamplerInformation._from_raw(
            tray_index=0,
            vial_index=5,
            vials_per_tray_x=12,
            vials_per_tray_y=8,
            tray_shape_int=99,  # Invalid value
            tray_name="",
        )

        assert info.tray_shape is None

    def test_auto_sampler_repr(self):
        """Test string representation of AutoSamplerInformation."""

        info = AutoSamplerInformation._from_raw(
            tray_index=1,
            vial_index=10,
            vials_per_tray_x=12,
            vials_per_tray_y=8,
            tray_shape_int=0,  # Rectangular
            tray_name="",
        )
        repr_str = repr(info)
        assert "tray=1" in repr_str
        assert "vial=10" in repr_str
        assert "shape=Rectangular" in repr_str
