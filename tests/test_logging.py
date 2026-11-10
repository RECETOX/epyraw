"""Tests that silent fallbacks are observable through the standard logger.

The package itself never configures logging, so every test opts in explicitly with
``caplog.at_level``.
"""

import io
import logging
import subprocess
import sys

import pytest

from epyraw import AutoSamplerInformation, cli, download
from epyraw.cli import _build_parser, _configure_logging
from epyraw.raw_file import RawFile, _attr_or_default, _safe_float, _safe_int


def _download_fails(*args: object, **kwargs: object) -> None:
    raise RuntimeError("simulated download failure")


class _RequestsFail:
    """Stand-in for the ``requests`` module, so the real download loop runs and fails."""

    @staticmethod
    def get(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated network failure")


class _DisposeRaises:
    """Stand-in for the .NET raw file whose Dispose() fails."""

    def __init__(self, exc: BaseException) -> None:
        self._exc = exc

    def Dispose(self) -> None:
        raise self._exc


class _FakeReaction:
    def __init__(self) -> None:
        self.PrecursorMass = 500.0
        self.CollisionEnergy = 20.0
        self.IsolationWidth = 1.0


class _FakeScanEvent:
    """Scan event that reports three reactions but only has one."""

    def __init__(self) -> None:
        self.ReactionCount = 3
        self.MassAnalyzer = 1

    def GetReaction(self, index: int) -> _FakeReaction:
        if index > 0:
            raise RuntimeError("no such reaction")
        return _FakeReaction()


class _FakeRawForScanEvent:
    def __init__(self, scan_event: object) -> None:
        self._scan_event = scan_event

    def GetScanEventForScanNumber(self, scan_number: int) -> object:
        return self._scan_event


class _CountingScanStats:
    """Stand-in for the .NET scan-stats object, counting its own property reads.

    A .NET property marshals across the runtime on every access, so the count is the
    cost of the read path, not an implementation detail of the test.
    """

    def __init__(self) -> None:
        self.reads = 0

    @property
    def IsCentroidScan(self) -> bool:
        self.reads += 1
        return True

    @property
    def SpectrumPacketType(self) -> int:
        self.reads += 1
        return 0

    @property
    def PacketCount(self) -> int:
        self.reads += 1
        return 3

    @property
    def TIC(self) -> float:
        self.reads += 1
        return 100.0

    @property
    def BasePeakIntensity(self) -> float:
        self.reads += 1
        return 50.0


class _FakeRawForStats:
    def __init__(self, stats: object) -> None:
        self._stats = stats

    def GetScanStatsForScanNumber(self, scan_number: int) -> object:
        return self._stats


class _FakeRawForMethod:
    """Instrument method with one good and two unusable mass-list rows."""

    InstrumentMethodsCount = 1

    def GetInstrumentMethod(self, index: int) -> str:
        return (
            "Mass List Table\n"
            "CompoundName|m/z|Threshold\n"
            "good|500.0|1000.0\n"
            "broken|not-a-number|1000.0\n"
            "short-row\n"
            "End Mass List Table\n"
        )


def _bare_raw_file(net_object: object | None = None) -> RawFile:
    """A RawFile that skips __init__, so tests can hand it a stand-in .NET object."""
    rf = RawFile.__new__(RawFile)
    rf._raw_file = net_object
    return rf


class TestLibraryDoesNotConfigureLogging:
    """A library must leave logging to the application that imports it."""

    def test_import_changes_nothing_and_prints_nothing(self):
        """Importing epyraw adds no root handler, sets no level, writes no stderr."""
        program = (
            "import logging\n"
            "root = logging.getLogger()\n"
            "before = (list(root.handlers), root.level)\n"
            "import epyraw\n"
            "after = (list(root.handlers), root.level)\n"
            "assert before == after, f'import changed root logging: {before} -> {after}'\n"
            "assert root.level == logging.WARNING, f'root level was changed to {root.level}'\n"
            "pkg = logging.getLogger('epyraw')\n"
            "assert pkg.level == logging.NOTSET, 'the library must not set a level'\n"
            "assert pkg.handlers and all(isinstance(h, logging.NullHandler) for h in pkg.handlers)"
            ", f'unexpected handlers on epyraw: {pkg.handlers}'\n"
        )
        result = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        assert result.stderr == "", f"import epyraw wrote to stderr: {result.stderr}"

    def test_runtime_selection_is_named(self, sample_raw_file):
        """Which .NET runtime was tried, and which one won, must be visible."""
        program = (
            "import logging, sys\n"
            "logging.basicConfig(level=logging.DEBUG, stream=sys.stdout,\n"
            "                    format='%(levelname)s %(name)s: %(message)s')\n"
            f"from epyraw import RawFile\nRawFile(r'{sample_raw_file}')\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", program], capture_output=True, text=True, timeout=300
        )
        assert result.returncode == 0, result.stderr
        assert "Trying the .NET runtime" in result.stdout
        assert "Initialized the .NET runtime" in result.stdout


class TestFallbacksAreLogged:
    """Every 'expected a value, found none' path must leave a record."""

    def test_safe_int_logs_a_failed_conversion(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            assert _safe_int("not a number", context="Vial") == 0
        assert "Could not convert Vial" in caplog.text

    def test_safe_float_logs_a_failed_conversion(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            assert _safe_float("n/a", default=2.5, context="SampleVolume") == 2.5
        assert "Could not convert SampleVolume" in caplog.text

    def test_missing_value_uses_the_default_without_a_log(self, caplog):
        """None means the file has no value here - a default is the answer, not a fault."""
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            assert _safe_float(None, default=2.5) == 2.5
            assert _safe_int(None, default=7) == 7
        assert caplog.records == []

    def test_zero_is_a_value_and_not_a_missing_marker(self):
        """0 must convert to 0 rather than falling through to the default."""
        assert _safe_int(0, default=7) == 0
        assert _safe_float(0.0, default=1.5) == 0.0

    def test_zero_conversions_log_nothing(self, caplog):
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            assert _safe_int(3) == 3
        assert caplog.records == []

    def test_unrecognised_tray_shape_warns(self, caplog):
        with caplog.at_level(logging.WARNING, logger="epyraw.models"):
            info = AutoSamplerInformation._from_raw(0, 1, 12, 8, 99, "tray")
        assert info.tray_shape is None
        assert "Unrecognised tray shape value 99" in caplog.text

    def test_known_tray_shape_logs_nothing(self, caplog):
        with caplog.at_level(logging.WARNING, logger="epyraw.models"):
            AutoSamplerInformation._from_raw(0, 1, 12, 8, 0, "tray")
        assert caplog.records == []

    def test_truncated_reaction_list_warns(self, caplog):
        rf = _bare_raw_file(_FakeRawForScanEvent(_FakeScanEvent()))
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            event = rf.get_scan_event(10)
        assert len(event.reactions) == 1
        assert "truncated to 1 of 3" in caplog.text

    def test_dropped_inclusion_rows_are_counted(self, caplog):
        rf = _bare_raw_file(_FakeRawForMethod())
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            items = rf.get_inclusion_exclusion_list()
        assert len(items) == 1
        assert "dropped 2 unparseable row(s), kept 1" in caplog.text

    def test_missing_method_on_a_range_average_warns(self, raw_file, caplog):
        """Averaging is unavailable on these assemblies - the caller must be told."""
        with caplog.at_level(logging.WARNING, logger="epyraw.raw_file"):
            spectrum = raw_file.average_scans_in_scan_range(1, 5)
        assert spectrum.num_peaks == 0
        assert "AverageScansInScanRange is not available" in caplog.text

    def test_default_mass_options_logs_the_substituted_tolerance(self, raw_file, caplog):
        """The 5 ppm tolerance is invented here, so the substitution is recorded."""
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            options = raw_file.default_mass_options()
        assert options.tolerance == 5.0
        assert "DefaultMassOptions is unavailable" in caplog.text

    def test_disposal_errors_are_swallowed_but_logged(self, caplog):
        rf = _bare_raw_file(_DisposeRaises(RuntimeError("boom")))
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            rf.close()
        assert rf._raw_file is None
        assert "Error while disposing" in caplog.text

    def test_disposal_does_not_swallow_base_exception(self):
        """KeyboardInterrupt/SystemExit must not be caught on the way out."""
        rf = _bare_raw_file(_DisposeRaises(KeyboardInterrupt()))
        with pytest.raises(KeyboardInterrupt):
            rf.close()
        assert rf._raw_file is None


class TestObservingCostsNothing:
    """Logging a fallback must not double the interop calls the fallback came from."""

    def test_present_attribute_is_read_once(self, caplog):
        """Probing with hasattr before reading would marshal every present field twice."""
        stats = _CountingScanStats()
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            assert _attr_or_default(stats, "TIC", 0.0, "stats") == 100.0
        assert stats.reads == 1
        assert caplog.records == []

    def test_absent_attribute_logs_the_default(self, caplog):
        stats = _CountingScanStats()
        with caplog.at_level(logging.DEBUG, logger="epyraw.raw_file"):
            assert _attr_or_default(stats, "NotInThisVersion", 0.0, "stats") == 0.0
        assert "NotInThisVersion is not available, using 0.0" in caplog.text

    def test_scan_stats_read_each_field_once(self):
        """The site that regressed: five fields must cost five reads, not ten."""
        stats = _CountingScanStats()
        rf = _bare_raw_file(_FakeRawForStats(stats))
        assert rf.get_scan_stats(1).mass_count == 3
        assert stats.reads == 5


class TestCliVerbosity:
    """-v / -vv are how a CLI user gets at any of the above."""

    @pytest.mark.parametrize(
        "verbosity,expected",
        [
            (0, logging.WARNING),
            (1, logging.INFO),
            (2, logging.DEBUG),
            (5, logging.DEBUG),
        ],
    )
    def test_verbosity_sets_the_root_level(self, verbosity, expected):
        """basicConfig only configures an unconfigured root, so clear pytest's handler."""
        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers.clear()
        try:
            assert _configure_logging(verbosity) == expected
            assert root.level == expected
        finally:
            root.handlers[:] = saved_handlers
            root.setLevel(saved_level)

    @pytest.mark.parametrize(
        "argv,expected",
        [
            (["check"], 0),
            (["check", "-v"], 1),
            (["download", "-vv"], 2),
            (["download", "-v", "-v"], 2),
            (["download", "--verbose"], 1),
        ],
    )
    def test_verbose_flag_is_accepted_after_each_subcommand(self, argv, expected):
        assert _build_parser().parse_args(argv).verbose == expected

    def test_no_subcommand_has_no_verbosity(self):
        """main() falls back to 0 when the flag was never reachable."""
        assert not hasattr(_build_parser().parse_args([]), "verbose")

    def _run_failing_download(self, monkeypatch, argv: list[str]) -> object:
        """Run the CLI against a download that always fails, restoring logging after."""
        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers.clear()  # basicConfig only configures an unconfigured root
        monkeypatch.setattr(cli, "download_runtimes", _download_fails)
        monkeypatch.setattr(sys, "argv", ["epyraw", *argv])
        try:
            cli.main()
        except SystemExit as exc:
            return exc.code
        finally:
            root.handlers[:] = saved_handlers
            root.setLevel(saved_level)
        return None

    def test_failure_exits_one_and_points_at_vv(self, monkeypatch, capsys):
        code = self._run_failing_download(monkeypatch, ["download"])
        err = capsys.readouterr().err
        assert code == 1
        assert "Error: simulated download failure" in err
        assert "-vv" in err  # says where the traceback can be found
        assert "Traceback" not in err  # but does not print one unasked

    def test_failure_with_vv_prints_a_traceback(self, monkeypatch, capsys):
        code = self._run_failing_download(monkeypatch, ["download", "-vv"])
        err = capsys.readouterr().err
        assert code == 1
        assert "Traceback (most recent call last)" in err
        assert "Re-run with -vv" not in err

    def _render_real_download_failure(self, monkeypatch, tmp_path, argv: list[str]) -> str:
        """Let the real downloader fail, and return what the CLI's handler rendered.

        Only ``requests`` is replaced, so the failure comes out of ``download_runtimes``
        itself — a WARNING carrying ``exc_info`` — rather than from a stubbed function.
        """
        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers.clear()  # basicConfig only configures an unconfigured root
        rendered = io.StringIO()
        monkeypatch.setattr(download, "requests", _RequestsFail())
        try:
            verbosity = _build_parser().parse_args(argv).verbose
            cli._configure_logging(verbosity)
            for handler in root.handlers:
                if isinstance(handler, logging.StreamHandler):
                    handler.setStream(rendered)
            with pytest.raises(RuntimeError, match="simulated network failure"):
                download.download_runtimes(tmp_path, progress=False)
        finally:
            root.handlers[:] = saved_handlers
            root.setLevel(saved_level)
        return rendered.getvalue()

    def test_download_failure_prints_no_traceback_without_vv(self, monkeypatch, tmp_path):
        """The warning is worth printing at any verbosity; its traceback is not."""
        out = self._render_real_download_failure(monkeypatch, tmp_path, ["download"])
        assert "Failed to download OpenMcdf.dll" in out
        assert "Traceback" not in out

    def test_download_failure_prints_no_traceback_with_one_v(self, monkeypatch, tmp_path):
        out = self._render_real_download_failure(monkeypatch, tmp_path, ["download", "-v"])
        assert "Traceback" not in out

    def test_download_failure_prints_a_traceback_with_vv(self, monkeypatch, tmp_path):
        out = self._render_real_download_failure(monkeypatch, tmp_path, ["download", "-vv"])
        assert "Failed to download OpenMcdf.dll" in out
        assert "Traceback (most recent call last)" in out

    def test_an_embedder_keeps_the_exception_on_the_record(self, monkeypatch, tmp_path):
        """Suppressing the traceback is the CLI's choice, not something done to callers."""
        seen: list[logging.LogRecord] = []

        class _Collect(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                seen.append(record)

        root = logging.getLogger()
        saved_handlers, saved_level = root.handlers[:], root.level
        root.handlers[:] = [_Collect()]  # logging is already configured, as by an embedder
        root.setLevel(logging.WARNING)
        monkeypatch.setattr(download, "requests", _RequestsFail())
        try:
            assert cli._configure_logging(0) == logging.WARNING
            with pytest.raises(RuntimeError, match="simulated network failure"):
                download.download_runtimes(tmp_path, progress=False)
        finally:
            root.handlers[:] = saved_handlers
            root.setLevel(saved_level)

        failures = [r for r in seen if r.levelno == logging.WARNING]
        assert failures, "the per-file failure was never logged"
        assert all(r.exc_info is not None for r in failures)
