#!/usr/bin/env python3
"""Basic usage examples for epyraw."""

from epyraw import Device, RawFile, TraceType


def main():
    """Demonstrate basic usage of the RawFile reader."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python basic_usage.py <path/to/file.raw>")
        print()
        print("This example demonstrates basic file reading operations.")
        return

    filepath = sys.argv[1]

    print(f"Opening file: {filepath}")
    print("=" * 60)

    # Open the file using context manager
    with RawFile(filepath) as raw_file:
        # Select the MS instrument (typically instance 1)
        raw_file.select_instrument(Device.MS, 1)

        # Print file information
        print("\n--- File Information ---")
        fh = raw_file.file_header
        print(f"File: {raw_file.filename}")
        print(f"Created: {fh.creation_date}")
        print(f"Operator: {fh.who_created_id}")
        print(f"Instruments: {raw_file.instrument_count}")

        # Print run header information
        print("\n--- Run Header ---")
        rh = raw_file.run_header
        print(f"Scan range: {rh.first_spectrum} - {rh.last_spectrum}")
        print(f"Time range: {rh.start_time:.2f} - {rh.end_time:.2f} min")
        print(f"Duration: {rh.duration:.2f} min")
        print(f"Spectra count: {rh.spectra_count}")
        print(f"Mass range: {rh.low_mass:.2f} - {rh.high_mass:.2f} m/z")
        print(f"Max intensity: {rh.max_intensity:.2e}")

        # Print sample information
        print("\n--- Sample Information ---")
        si = raw_file.sample_information
        print(f"Sample name: {si.sample_name}")
        print(f"Sample ID: {si.sample_id}")
        print(f"Comment: {si.comment}")

        # Print instrument details
        print("\n--- Instrument Details ---")
        inst = raw_file.get_instrument_data()
        print(f"Model: {inst.model}")
        print(f"Serial: {inst.serial_number}")
        print(f"Software: {inst.software_version}")

        # Get available filters
        print("\n--- Available Filters ---")
        filters = raw_file.get_filters()
        for i, f in enumerate(filters[:5], 1):  # Show first 5
            print(f"  {i}. {f}")
        if len(filters) > 5:
            print(f"  ... and {len(filters) - 5} more")

        # Get a spectrum
        if rh.spectra_count > 0:
            print("\n--- Spectrum Example (scan 1) ---")
            spectrum = raw_file.get_spectrum(rh.first_spectrum, centroid=True)
            print(f"Peaks: {spectrum.num_peaks}")
            print(
                f"m/z range: {spectrum.mass_range[0]:.2f} - {spectrum.mass_range[1]:.2f}"
            )
            print(
                f"Base peak: {spectrum.base_peak[0]:.4f} m/z @ {spectrum.base_peak[1]:.2e}"
            )
            print(f"TIC: {spectrum.total_ion_current:.2e}")

            # Show top 5 peaks
            print("\nTop 5 peaks:")
            import numpy as np

            top_indices = np.argsort(spectrum.intensities)[-5:][::-1]
            for idx in top_indices:
                print(
                    f"  {spectrum.masses[idx]:.4f} m/z @ {spectrum.intensities[idx]:.2e}"
                )

        # Get chromatogram
        print("\n--- Chromatogram Example ---")
        chrom = raw_file.get_chromatogram(TraceType.BasePeak)
        print(f"Points: {chrom.num_points}")
        print(f"Time range: {chrom.time_range[0]:.2f} - {chrom.time_range[1]:.2f} min")
        print(f"Base peak time: {chrom.base_peak_time:.2f} min")

        # Get trailer extra data for first scan
        if rh.spectra_count > 0:
            print("\n--- Trailer Extra Data (scan 1) ---")
            trailer = raw_file.get_trailer_extra_information(rh.first_spectrum)
            # Show some common fields
            common_fields = [
                "Monoisotopic M/Z:",
                "Charge State:",
                "Precursor Mass:",
                "Collision Energy:",
            ]
            for field in common_fields:
                if field in trailer:
                    print(f"  {field} {trailer[field]}")

        # Average scans example
        if rh.spectra_count >= 2:
            print("\n--- Averaged Spectrum Example ---")
            avg_spec = raw_file.average_scans(
                (rh.first_spectrum, min(rh.first_spectrum + 9, rh.last_spectrum)),
                tolerance=5.0,
            )
            print(f"Averaged 10 scans: {avg_spec.num_peaks} peaks")

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
