"""CLI for epyraw package."""

import argparse
import sys
from pathlib import Path

from .download import check_runtimes_present, download_runtimes, get_default_runtime_path


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="epyraw",
        description="Thermo RawFileReader Python wrapper - manage runtime DLLs",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Download command
    download_parser = subparsers.add_parser(
        "download", help="Download Thermo RawFileReader runtime DLLs"
    )
    download_parser.add_argument(
        "--path",
        "-p",
        type=str,
        help="Custom path for DLLs (default: ~/.epyraw/runtimes/net8old)",
    )
    download_parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Re-download even if files exist",
    )

    # Check command
    check_parser = subparsers.add_parser("check", help="Check if runtime DLLs are installed")
    check_parser.add_argument(
        "--path",
        "-p",
        type=str,
        help="Custom path to check (default: ~/.epyraw/runtimes/net8old)",
    )

    args = parser.parse_args()

    if args.command == "download":
        target_path = Path(args.path) if args.path else None
        print("Downloading Thermo RawFileReader runtime DLLs...")
        try:
            path = download_runtimes(target_path, force=args.force)
            print(f"Successfully downloaded to: {path}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "check":
        path = Path(args.path) if args.path else get_default_runtime_path()
        if check_runtimes_present(path):
            print(f"Runtime DLLs found at: {path}")
            sys.exit(0)
        else:
            print(f"Runtime DLLs NOT found at: {path}")
            print("Run 'epyraw download' to install them.")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
