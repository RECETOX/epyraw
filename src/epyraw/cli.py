"""CLI for epyraw package."""

import argparse
import logging
import sys
from pathlib import Path

from .download import check_runtimes_present, download_runtimes, get_default_runtime_path

logger = logging.getLogger(__name__)

# Root level for each repeated -v flag. Anything past -vv stays at DEBUG.
VERBOSITY_LEVELS = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}


class _TracebackOnlyAtDebug(logging.Filter):
    """Strip the traceback from a record, keeping its message.

    Attached to the handler the CLI installs, and only when the level is coarser
    than ``DEBUG``: below ``-vv`` nothing can ask for a traceback, so a ``WARNING``
    that carries ``exc_info`` must not print one unasked — the CLI instead points at
    ``-vv`` as where to get it. Filters have to mutate, since ``logging`` discards
    any record a filter returns.

    An embedder who configured logging before calling in is untouched:
    ``basicConfig`` then installs no handler, so no filter is attached and their
    records keep their exceptions.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.exc_info = None
        record.exc_text = None
        return True


def _configure_logging(verbosity: int) -> int:
    """Configure logging for the command line entry point.

    This is the only place in the package that configures logging; the library
    itself just attaches a ``NullHandler`` and leaves the decision to the caller.

    Args:
        verbosity: How many ``-v`` flags were given.

    Returns:
        The level that was configured.
    """
    level = VERBOSITY_LEVELS.get(verbosity, logging.DEBUG)
    root = logging.getLogger()
    owns_logging = not root.handlers
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    if owns_logging and level > logging.DEBUG:
        for handler in root.handlers:
            handler.addFilter(_TracebackOnlyAtDebug())
    return level


def _build_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="epyraw",
        description="Thermo RawFileReader Python wrapper - manage runtime DLLs",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Shared options for every subcommand, so that -v follows the subcommand:
    # `epyraw download -v`.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Show more output: -v for progress, -vv for full debug logs and tracebacks",
    )

    # Download command
    download_parser = subparsers.add_parser(
        "download", parents=[common], help="Download Thermo RawFileReader runtime DLLs"
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
    check_parser = subparsers.add_parser(
        "check", parents=[common], help="Check if runtime DLLs are installed"
    )
    check_parser.add_argument(
        "--path",
        "-p",
        type=str,
        help="Custom path to check (default: ~/.epyraw/runtimes/net8old)",
    )

    return parser


def main() -> None:
    """Main CLI entry point."""
    parser = _build_parser()
    args = parser.parse_args()

    verbosity = getattr(args, "verbose", 0)
    level = _configure_logging(verbosity)
    logger.debug("epyraw CLI invoked with %s, logging at %s", args, logging.getLevelName(level))

    if args.command == "download":
        target_path = Path(args.path) if args.path else None
        print("Downloading Thermo RawFileReader runtime DLLs...")
        try:
            path = download_runtimes(target_path, force=args.force)
            print(f"Successfully downloaded to: {path}")
        except Exception as e:
            # The message goes to stderr as before; the traceback is only
            # recoverable at DEBUG, which is what -vv enables.
            logger.debug("Unhandled error while downloading runtimes", exc_info=True)
            print(f"Error: {e}", file=sys.stderr)
            if verbosity < 2:
                print("Re-run with -vv for a full traceback.", file=sys.stderr)
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
