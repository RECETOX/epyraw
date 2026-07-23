#!/usr/bin/env python3
"""Example: Extract all spectra from a RAW file to NumPy arrays.

This example demonstrates how to iterate through all scans in a file
and extract spectrum data for further analysis.
"""

from typing import Any

from thermo_raw_file_reader import Device, RawFile


def extract_all_spectra(filepath: str) -> dict[str, Any]:
    """Extract all spectra from a RAW file.

    Args:
        filepath: Path to the .raw file.

    Returns:
        Dictionary containing:
            - 'scan_numbers': list of scan numbers
            - 'masses': list of mass arrays (one per scan)
            - 'intensities': list of intensity arrays (one per scan)
            - 'filters': list of filter strings (one per scan)
    """
    result = {
        "scan_numbers": [],
        "masses": [],
        "intensities": [],
        "filters": [],
    }

    with RawFile(filepath) as rf:
        rf.select_instrument(Device.MS, 1)

        run_header = rf.run_header

        for scan_num in range(run_header.first_spectrum, run_header.last_spectrum + 1):
            # Get spectrum
            spectrum = rf.get_spectrum(scan_num, centroid=True)

            # Get filter
            sf = rf.get_filter_for_scan_number(scan_num)

            result["scan_numbers"].append(scan_num)
            result["masses"].append(spectrum.masses.copy())
            result["intensities"].append(spectrum.intensities.copy())
            result["filters"].append(sf.filter_string)

            if scan_num % 100 == 0:
                print(f"Processed {scan_num}/{run_header.last_spectrum} scans")

    return result


def main():
    """Main entry point."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python extract_spectra.py <path/to/file.raw>")
        return

    filepath = sys.argv[1]
    print(f"Extracting spectra from: {filepath}")

    data = extract_all_spectra(filepath)

    print("\nExtraction complete!")
    print(f"Total scans: {len(data['scan_numbers'])}")
    print(f"Total peaks: {sum(len(m) for m in data['masses'])}")


if __name__ == "__main__":
    main()
