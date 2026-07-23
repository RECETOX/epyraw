"""Tests for data model classes."""

import numpy as np

from epyraw.models import (Chromatogram, FileHeader,
                                           InclusionListItem, InstrumentData,
                                           RunHeader, SampleInformation,
                                           ScanFilter, Spectrum,
                                           StatusLogField)


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
