"""Tests for the instrument status log (acquisition-time instrument state).

Integration tests run against tests/testdata/sample.raw (Q Exactive HF-X, one
instrument stream: Device.MS instance 1). The numbers asserted here were read
from that file: 54 status-log fields of which 46 are numeric channels, and 5
logged entries.

The status log is sparse - 5 rows against 574 scans in this file - and its values
are the "live" instrument state (temperatures, spray voltage, gas flows, vacuum),
not per-scan data.

One test class repeats the read path on the Zenodo QC sample (Q Exactive GC) to
show that the channel set comes from the file rather than from a fixed list.

Stream discovery on a non-MS stream cannot be tested on real data: neither
test file has a second instrument stream, so those cases use a fake .NET adapter.
"""

import numpy as np
import pytest

from epyraw import Device, InstrumentStatusLog, RawFile, StatusLogEntry, StatusLogField
from epyraw.exceptions import InstrumentNotSelectedError
from epyraw.raw_file import _status_log_value

# Field labels verbatim from tests/testdata/sample.raw - they are the join key.
SECTION_ROW = "====  Overall Status:  ====:"
ION_SOURCE_ROW = "======  Ion Source:  ======:"
STATUS_ROW = "Status:"
SPRAY_VOLTAGE = "Spray Voltage (V)"
SPRAY_CURRENT = "Spray Current (µA)"
CAPILLARY_TEMPERATURE = "Capillary Temperature (°C)"
HIGH_VACUUM = "High Vacuum Sensor (mbar)"
SHEATH_GAS = "Sheath gas flow rate"

# Measured on tests/testdata/sample.raw.
FIELD_COUNT = 54
CHANNEL_COUNT = 46
ENTRY_COUNT = 5
TIMES = [
    0.0016197512159124017,
    0.17317695915699005,
    0.34005627036094666,
    0.5072169899940491,
    0.6750169992446899,
]


# =============================================================================
# Fakes for instrument-stream discovery
# =============================================================================


class FakeHeaderItem:
    """Stand-in for a .NET HeaderItem."""

    def __init__(self, label: str, data_type: int, is_numeric: bool):
        self.Label = label
        self.DataType = data_type
        self.IsNumeric = is_numeric


class FakeEntry:
    """Stand-in for a .NET IStatusLogEntry."""

    def __init__(self, time: float, values: list):
        self.Time = time
        self.Values = values


class FakeSelection:
    """Stand-in for a .NET InstrumentSelection value object."""

    def __init__(self, device_type: int, index: int):
        self.DeviceType = device_type
        self.InstrumentIndex = index


class FakeRawData:
    """Minimal stand-in for the IRawDataPlus surface the status log code uses.

    Lets us describe a file whose status log lives on a stream the caller did not
    select, which neither test file provides.
    """

    def __init__(self, streams: set, log: dict, fields: list):
        self.streams = streams
        self.log = log
        self.fields = fields
        # Left where RawFile.select_instrument(Device.MS, 1) put it.
        self.selection = FakeSelection(int(Device.MS), 1)
        self.select_calls: list[tuple[int, int]] = []
        # Which stream was selected each time status-log data was actually read.
        self.reads: list[tuple[int, int]] = []

    @property
    def SelectedInstrument(self) -> FakeSelection:
        # A fresh value object every read, like the .NET property.
        return FakeSelection(self.selection.DeviceType, self.selection.InstrumentIndex)

    def SelectInstrument(self, device_type: int, instance: int) -> None:
        key = (int(device_type), int(instance))
        self.select_calls.append(key)
        if key not in self.streams:
            raise ValueError(f"no such instrument stream: {key}")
        self.selection = FakeSelection(key[0], key[1])

    def GetInstrumentCountOfType(self, device_type: int) -> int:
        return sum(1 for stream in self.streams if stream[0] == int(device_type))

    def _logged(self) -> list:
        current = (self.selection.DeviceType, self.selection.InstrumentIndex)
        entries = self.log.get(current, [])
        if entries:
            self.reads.append(current)
        return entries

    def GetStatusLogEntriesCount(self) -> int:
        return len(self._logged())

    def GetStatusLogHeaderInformation(self) -> list:
        return self.fields if self._logged() else []

    def GetStatusLogEntry(self, index: int) -> FakeEntry:
        return self._logged()[index]

    def Dispose(self) -> None:
        pass


def fake_fields() -> list[FakeHeaderItem]:
    """Two numeric channels, one section row and one text row."""
    return [
        FakeHeaderItem(SECTION_ROW, 0, False),
        FakeHeaderItem(SPRAY_VOLTAGE, 11, True),
        FakeHeaderItem(CAPILLARY_TEMPERATURE, 11, True),
        FakeHeaderItem(STATUS_ROW, 12, False),
    ]


def fake_entries() -> list[FakeEntry]:
    """Two rows in the layout fake_fields() describes."""
    return [
        FakeEntry(0.05, [None, 1500.5, 250.25, "Instrument status Ok"]),
        FakeEntry(0.6, [None, 2500.25, 275.5, "Instrument status Ok"]),
    ]


def fake_with_log_on(device: Device, instance: int) -> FakeRawData:
    """Build a fake file whose status log lives on a stream the caller did not select.

    The caller is on Device.MS instance 1, as the raw_file fixture leaves it.
    Instances are 1-based and consecutive, so instance 2 implies instance 1 exists.
    """
    streams = {(int(Device.MS), 1)}
    streams.update((int(device), num) for num in range(1, instance + 1))

    return FakeRawData(
        streams=streams,
        log={(int(device), instance): fake_entries()},
        fields=fake_fields(),
    )


# =============================================================================
# Field definitions
# =============================================================================


class TestStatusLogFields:
    """Field definitions of the status log."""

    def test_field_count(self, raw_file):
        """Test that every field is reported.

        Protects against: silently truncated header information.
        """
        fields = raw_file.status_log_fields

        assert len(fields) == FIELD_COUNT
        assert all(isinstance(field, StatusLogField) for field in fields)

    def test_header_information_is_alias_of_fields(self, raw_file):
        """Test the deprecated entry point still returns the same data.

        Protects against: get_status_log_header_information() drifting from the
        status_log_fields property it delegates to.
        """
        alias = raw_file.get_status_log_header_information()
        fields = raw_file.status_log_fields

        assert [(f.label, f.data_type, f.is_numeric, f.unit) for f in alias] == [
            (f.label, f.data_type, f.is_numeric, f.unit) for f in fields
        ]

    def test_section_row_is_not_numeric(self, raw_file):
        """Test a structure row stays on fields but is not a channel.

        Protects against: section titles being plotted or averaged as data.
        """
        field = raw_file.status_log_fields[0]

        assert field.label == SECTION_ROW
        assert field.is_numeric is False
        assert field.unit == ""

    def test_non_numeric_field_count(self, raw_file):
        """Test only the numeric channels become channels.

        Protects against: text rows ('Status:') or section rows leaking into
        channels, which cannot be coerced to float.
        """
        fields = raw_file.status_log_fields
        log = raw_file.get_status_log()

        assert sum(1 for f in fields if f.is_numeric) == CHANNEL_COUNT
        assert log.channels == [f.label for f in fields if f.is_numeric]
        assert len(log.channels) == CHANNEL_COUNT
        assert ION_SOURCE_ROW not in log.channels
        assert STATUS_ROW not in log.channels

    def test_unit_is_parsed_from_label(self, raw_file):
        """Test units come out of the label text, degree sign included.

        Protects against: losing or normalising non-ASCII unit text, and against
        inventing a unit for a field that has none.
        """
        by_label = {f.label: f for f in raw_file.status_log_fields}

        assert by_label[CAPILLARY_TEMPERATURE].unit == "°C"
        assert by_label[CAPILLARY_TEMPERATURE].label == CAPILLARY_TEMPERATURE
        assert by_label[SPRAY_VOLTAGE].unit == "V"
        assert by_label[SPRAY_CURRENT].unit == "µA"

    def test_channel_without_unit(self, raw_file):
        """Test a numeric channel whose label carries no unit.

        Protects against: claiming a unit the file does not state.
        """
        by_label = {f.label: f for f in raw_file.status_log_fields}

        assert by_label[SHEATH_GAS].is_numeric is True
        assert by_label[SHEATH_GAS].unit == ""

    def test_labels_are_unique(self, raw_file):
        """Test labels can be used as a dictionary key.

        Protects against: StatusLogEntry.values silently dropping a value if a
        file ever repeated a label, and against normalising labels into collisions.
        """
        labels = [f.label for f in raw_file.status_log_fields]

        assert len(set(labels)) == len(labels)


# =============================================================================
# Entries
# =============================================================================


class TestStatusLogEntries:
    """Reading status-log rows."""

    def test_status_log_count(self, raw_file):
        """Test the reported entry count.

        Protects against: reading a different number of rows than the file has.
        """
        assert raw_file.status_log_count == ENTRY_COUNT

    def test_get_status_log_returns_every_entry(self, raw_file):
        """Test an unfiltered read returns exactly status_log_count entries.

        Protects against: silent sorting, deduplication or truncation, which would
        break the documented len(entries) == status_log_count guarantee.
        """
        log = raw_file.get_status_log()

        assert isinstance(log, InstrumentStatusLog)
        assert len(log) == ENTRY_COUNT
        assert len(log.entries) == raw_file.status_log_count
        assert [entry.time for entry in log.entries] == TIMES

    def test_entry_values_are_keyed_by_label(self, raw_file):
        """Test values are reachable by verbatim label.

        Protects against: index-based access breaking when the channel set differs
        between instruments, and against dropping non-ASCII labels.
        """
        log = raw_file.get_status_log()
        entry = log.entries[-1]

        assert set(entry.values) == {f.label for f in log.fields}
        assert entry.values[CAPILLARY_TEMPERATURE] == pytest.approx(274.8863185522019)
        assert entry.values[SPRAY_CURRENT] == pytest.approx(6.41254921109653)

    def test_value_types_follow_the_field(self, raw_file):
        """Test numeric channels hold floats, text fields strings, structure rows None.

        Protects against: numbers arriving as display strings, which cannot be
        compared or averaged.
        """
        log = raw_file.get_status_log()

        for entry in log.entries:
            for channel in log.channels:
                assert isinstance(entry.values[channel], float)
            assert isinstance(entry.values[STATUS_ROW], str)
            assert entry.values[SECTION_ROW] is None

        assert log.entries[0].values[STATUS_ROW] == "Instrument status Ok"

    def test_every_numeric_channel_is_a_float(self, raw_file):
        """Test every value under a numeric channel coerces to float.

        Protects against: a channel being reported numeric while holding text.
        """
        log = raw_file.get_status_log()

        for entry in log.entries:
            for channel in log.channels:
                assert float(entry.values[channel]) == entry.values[channel]

    def test_scientific_notation_channel_is_preserved(self, raw_file):
        """Test a very small value survives without being rounded away.

        Protects against: display formatting rendering a 1e-9 channel as '0', which
        would arrive as 0.0 or as NaN.
        """
        values = [entry.values[HIGH_VACUUM] for entry in raw_file.get_status_log().entries]

        assert values[0] == pytest.approx(3.136920385392773e-09)
        assert values[-1] == pytest.approx(3.136920385392773e-09)
        assert all(1e-9 < value < 1e-8 for value in values)

    def test_entry_by_index_matches_the_log(self, raw_file):
        """Test indexed access returns the same row as the whole-log read.

        Protects against: the two read paths disagreeing about order or values.
        """
        log = raw_file.get_status_log()

        for index, expected in enumerate(log.entries):
            entry = raw_file.get_status_log_entry(index)

            assert isinstance(entry, StatusLogEntry)
            assert entry.time == expected.time
            assert entry.values == expected.values
            assert len(entry) == FIELD_COUNT

    def test_entry_index_out_of_range(self, raw_file):
        """Test out-of-range indexes raise IndexError.

        Protects against: the .NET exception escaping, and against Python-style
        negative indexing silently reading from the end.
        """
        for index in (ENTRY_COUNT, ENTRY_COUNT + 99, -1):
            with pytest.raises(IndexError):
                raw_file.get_status_log_entry(index)


class TestStatusLogAtTime:
    """Nearest-entry lookup by retention time."""

    def test_returns_nearest_entry(self, raw_file):
        """Test the nearest logged entry is returned, not the next one.

        Protects against: an off-by-one that returns the following row.
        """
        assert raw_file.get_status_log_at_time(0.62).time == 0.6750169992446899
        assert raw_file.get_status_log_at_time(0.4).time == 0.34005627036094666

    def test_times_outside_the_log_are_clamped(self, raw_file):
        """Test times outside the logged range clamp to the first/last entry.

        Protects against: a silent exception, and against the clamping behaviour
        changing without the docs noticing.
        """
        assert raw_file.get_status_log_at_time(-5.0).time == TIMES[0]
        assert raw_file.get_status_log_at_time(9999.0).time == TIMES[-1]

    def test_entry_of_exact_time_matches_indexed_entry(self, raw_file):
        """Test both access paths yield the same values for the same row.

        Protects against: the retention-time path losing precision relative to the
        indexed path.
        """
        by_index = raw_file.get_status_log_entry(4)
        by_time = raw_file.get_status_log_at_time(TIMES[4])

        assert by_time.time == by_index.time
        assert by_time.values == by_index.values


class TestStatusLogDataFrame:
    """The tabular view of the status log."""

    def test_frame_shape_and_columns(self, raw_file):
        """Test the frame is time plus one column per channel.

        Protects against: shape drift, and against structure rows becoming columns.
        """
        log = raw_file.get_status_log()
        frame = log.to_pandas()

        assert frame.shape == (ENTRY_COUNT, CHANNEL_COUNT + 1)
        assert list(frame.columns) == ["time", *log.channels]

    def test_time_column_is_a_column_not_the_index(self, raw_file):
        """Test time is an ordinary column, as Chromatogram.to_pandas() does.

        Protects against: reset_index()/set_index() churn breaking user code.
        """
        frame = raw_file.get_status_log().to_pandas()

        assert "time" in frame.columns
        assert frame.index.name is None
        assert list(frame.index) == list(range(ENTRY_COUNT))

    def test_time_column_is_monotonically_increasing(self, raw_file):
        """Test the logged times increase.

        Protects against: rows in an order that makes a plot fold back on itself.
        """
        times = raw_file.get_status_log().to_pandas()["time"].to_numpy()

        assert np.all(np.diff(times) > 0)

    def test_channels_hold_the_logged_values(self, raw_file):
        """Test the frame holds the same values as the entries.

        Protects against: columns being matched to the wrong labels.
        """
        frame = raw_file.get_status_log().to_pandas()
        log = raw_file.get_status_log()

        for channel in log.channels:
            assert frame[channel].tolist() == [entry.values[channel] for entry in log.entries]

    def test_capillary_temperature_is_plausible(self, raw_file):
        """Test the capillary temperature is a finite value in its real range.

        Protects against: reading a neighbouring channel, or a unit/scale error.
        """
        values = raw_file.get_status_log().to_pandas()[CAPILLARY_TEMPERATURE]

        assert np.isfinite(values).all()
        assert ((values > 100) & (values < 400)).all()


class TestStatusLogChannel:
    """Single-channel extraction by label."""

    def test_channel_matches_the_entries(self, raw_file):
        """Test a channel's series equals the same channel in the entries.

        Protects against: label-to-column mix-ups.
        """
        times, values = raw_file.get_status_log_channel(CAPILLARY_TEMPERATURE)
        log = raw_file.get_status_log()

        assert len(times) == raw_file.status_log_count
        assert len(values) == raw_file.status_log_count
        assert times.tolist() == [entry.time for entry in log.entries]
        assert values.tolist() == [entry.values[CAPILLARY_TEMPERATURE] for entry in log.entries]

    def test_channel_returns_float64_arrays(self, raw_file):
        """Test the arrays are float64.

        Protects against: string arrays coming back from the display-formatted API.
        """
        times, values = raw_file.get_status_log_channel(CAPILLARY_TEMPERATURE)

        assert times.dtype == np.float64
        assert values.dtype == np.float64

    def test_channel_keeps_full_precision(self, raw_file):
        """Test values keep the stored precision, not 4-digit display text.

        Protects against: switching to StatusLogPlottableData / GetStatusLogAtPosition,
        whose values are pre-formatted strings ('2515.9' for 2515.897091586047).
        """
        _times, values = raw_file.get_status_log_channel(SPRAY_VOLTAGE)

        assert values[-1] == raw_file.get_status_log_entry(4).values[SPRAY_VOLTAGE]
        assert values[-1] == pytest.approx(2515.897091586047)
        assert values[-1] != float("2515.9")
        assert values[0] != float("1519.5")

    def test_unknown_label_raises(self, raw_file):
        """Test an unknown label raises ValueError naming the available count.

        Protects against: a typo silently returning an empty series.
        """
        with pytest.raises(ValueError, match="Unknown status log channel"):
            raw_file.get_status_log_channel("Capillary Temp")

    def test_non_numeric_label_raises(self, raw_file):
        """Test a label that exists but is not numeric raises ValueError.

        Protects against: a section row being served as a channel of zeros.
        """
        with pytest.raises(ValueError, match="not a numeric channel"):
            raw_file.get_status_log_channel(SECTION_ROW)

    def test_error_names_the_available_channels(self, raw_file):
        """Test the error message reports how many channels the file offers.

        Protects against: an unhelpful error when the channel set differs per file.
        """
        with pytest.raises(ValueError, match=str(CHANNEL_COUNT)):
            raw_file.get_status_log_channel("nope")


class TestStatusLogTimeWindow:
    """Time-window filtering."""

    def test_unfiltered_read_returns_everything(self, raw_file):
        """Test no bounds means no filtering.

        Protects against: a default bound silently dropping rows.
        """
        assert len(raw_file.get_status_log().entries) == ENTRY_COUNT

    def test_bounds_are_inclusive(self, raw_file):
        """Test a bound exactly on an entry time keeps that entry.

        Protects against: exclusive bounds dropping the boundary row.
        """
        log = raw_file.get_status_log()

        assert [e.time for e in raw_file.get_status_log(start_time=TIMES[2]).entries] == TIMES[2:]
        assert [e.time for e in raw_file.get_status_log(end_time=TIMES[2]).entries] == TIMES[:3]
        assert [
            e.time for e in raw_file.get_status_log(start_time=TIMES[2], end_time=TIMES[2]).entries
        ] == [TIMES[2]]
        assert len(log.entries) == ENTRY_COUNT

    def test_window_between_entries(self, raw_file):
        """Test a window between two entries keeps the rows inside it.

        Protects against: rounding turning a 3-row window into a 2- or 4-row one.
        """
        entries = raw_file.get_status_log(start_time=0.1, end_time=0.51).entries

        assert [e.time for e in entries] == TIMES[1:4]

    def test_empty_window(self, raw_file):
        """Test a window past the end of the log is empty, not an error.

        Protects against: an exception for a range the run simply did not reach.
        """
        log = raw_file.get_status_log(start_time=5.0)

        assert len(log) == 0
        assert len(log.entries) == 0
        assert len(log.channels) == CHANNEL_COUNT
        assert log.to_pandas().shape == (0, CHANNEL_COUNT + 1)

    def test_filtered_read_keeps_all_field_definitions(self, raw_file):
        """Test filtering rows does not filter columns.

        Protects against: a filtered frame changing shape between windows, which
        breaks concatenating windows into one table.
        """
        log = raw_file.get_status_log(start_time=TIMES[1], end_time=TIMES[3])

        assert len(log.fields) == FIELD_COUNT
        assert log.to_pandas().shape == (3, CHANNEL_COUNT + 1)


# =============================================================================
# Instrument selection
# =============================================================================


class TestStatusLogSelection:
    """Interaction with the selected instrument stream."""

    @pytest.mark.parametrize(
        "access",
        [
            lambda rf: rf.status_log_fields,
            lambda rf: rf.status_log_count,
            lambda rf: rf.status_log_streams(),
            lambda rf: rf.get_status_log(),
            lambda rf: rf.get_status_log_entry(0),
            lambda rf: rf.get_status_log_at_time(0.1),
            lambda rf: rf.get_status_log_channel(SPRAY_VOLTAGE),
        ],
        ids=["fields", "count", "streams", "log", "entry", "at_time", "channel"],
    )
    def test_requires_a_selected_instrument(self, sample_raw_file, access):
        """Test the accessors refuse to guess which instrument to read.

        Protects against: a .NET NoSelectedDeviceException escaping, and against
        reading an arbitrary stream when the user has not chosen one.
        """
        with RawFile(str(sample_raw_file)) as rf:
            with pytest.raises(InstrumentNotSelectedError):
                access(rf)

    def test_caller_selection_is_restored(self, raw_file):
        """Test status-log access never change which instrument is selected.

        Protects against: a later get_spectrum() silently reading another stream.
        """
        net = raw_file._raw_file
        before = (
            int(net.SelectedInstrument.DeviceType),
            int(net.SelectedInstrument.InstrumentIndex),
        )

        fields = raw_file.status_log_fields
        count = raw_file.status_log_count
        assert (len(fields), count) == (FIELD_COUNT, ENTRY_COUNT)
        raw_file.status_log_streams()
        raw_file.get_status_log()
        raw_file.get_status_log_entry(0)
        raw_file.get_status_log_at_time(0.1)
        raw_file.get_status_log_channel(SPRAY_VOLTAGE)

        after = (
            int(net.SelectedInstrument.DeviceType),
            int(net.SelectedInstrument.InstrumentIndex),
        )
        assert after == before == (int(Device.MS), 1)

    def test_streams_agree_with_probing_every_stream(self, raw_file):
        """Test status_log_streams() matches selecting every stream by hand.

        Protects against: the discovery pass missing a stream or inventing one.
        """
        streams = raw_file.status_log_streams()
        candidates = [
            (device, instance)
            for device in Device
            for instance in range(1, raw_file.get_instrument_count_by_type(device) + 1)
        ]

        assert set(streams) <= set(candidates)
        assert streams  # the file must have something to find

        for stream in candidates:
            raw_file.select_instrument(*stream)
            assert (stream in streams) == (raw_file.status_log_count > 0)

        raw_file.select_instrument(Device.MS, 1)

    @pytest.mark.parametrize("stream", [(Device.Analog, 2), (Device.Other, 1)])
    def test_log_is_found_on_a_non_ms_stream(self, raw_file, monkeypatch, stream):
        """Test a status log on another stream is found and read.

        Protects against: hard-coding Device.MS, which loses the LC-written
        channels of files that log on Device.Analog or Device.Other. Neither test
        file has a second instrument stream, so the streams here are a fake.
        """
        device, instance = stream
        fake = fake_with_log_on(device, instance)
        monkeypatch.setattr(raw_file, "_raw_file", fake)

        assert raw_file.status_log_streams() == [(device, instance)]
        assert raw_file.status_log_count == 2

        log = raw_file.get_status_log()
        assert log.channels == [SPRAY_VOLTAGE, CAPILLARY_TEMPERATURE]
        assert [e.time for e in log.entries] == [0.05, 0.6]
        assert raw_file.get_status_log_channel(CAPILLARY_TEMPERATURE)[1].tolist() == [
            250.25,
            275.5,
        ]

        # Nothing was ever read while the MS stream was selected.
        assert fake.reads
        assert set(fake.reads) == {(int(device), instance)}
        assert (int(Device.MS), 1) not in fake.reads

    def test_log_stream_is_probed_and_caller_selection_kept(self, raw_file, monkeypatch):
        """Test the caller's selection is restored after another stream is used.

        Protects against: leaving the file on the status-log stream, which would
        change what the caller's next spectrum read returns.
        """
        fake = fake_with_log_on(Device.Other, 1)
        monkeypatch.setattr(raw_file, "_raw_file", fake)

        raw_file.get_status_log()

        # The other stream was selected to read from, MS/1 was put back afterwards.
        assert fake.select_calls[0] == (int(Device.Other), 1)
        assert fake.select_calls[-1] == (int(Device.MS), 1)
        assert (fake.selection.DeviceType, fake.selection.InstrumentIndex) == (int(Device.MS), 1)

    def test_file_without_any_status_log(self, raw_file, monkeypatch):
        """Test a file whose streams have no status log yields empties, not errors.

        Protects against: an exception escaping while searching for a log that is
        simply not there.
        """
        fake = FakeRawData(
            streams={(int(Device.MS), 1), (int(Device.Analog), 1)},
            log={},
            fields=[],
        )
        monkeypatch.setattr(raw_file, "_raw_file", fake)

        assert raw_file.status_log_streams() == []
        assert raw_file.status_log_count == 0
        assert raw_file.status_log_fields == []
        assert raw_file.get_status_log() == InstrumentStatusLog()
        assert raw_file.get_status_log().to_pandas().shape == (0, 1)

    def test_missing_log_is_probed_only_once(self, raw_file, monkeypatch):
        """Test a "no status log anywhere" answer is cached like a found stream.

        Protects against: repeating the search of every stream - one select plus
        one count each, most of them raising - on every accessor call, because the
        negative answer was indistinguishable from "not searched yet".
        """
        fake = FakeRawData(
            streams={(int(Device.MS), 1), (int(Device.Analog), 1)},
            log={},
            fields=[],
        )
        monkeypatch.setattr(raw_file, "_raw_file", fake)

        real = RawFile._select_and_probe_status_log
        probes: list[tuple[Device, int]] = []

        def counting_probe(self: RawFile, device: Device, instance: int) -> int:
            probes.append((device, instance))
            return real(self, device, instance)

        monkeypatch.setattr(RawFile, "_select_and_probe_status_log", counting_probe)

        # These three search for the log themselves, unlike status_log_streams().
        fields = raw_file.status_log_fields
        assert fields == []
        # One stream besides the caller's own, so the search probes exactly once.
        assert probes == [(Device.Analog, 1)]

        count = raw_file.status_log_count
        empty = raw_file.get_status_log()

        assert (count, empty) == (0, InstrumentStatusLog())
        assert probes == [(Device.Analog, 1)]


class TestClosedRawFile:
    """Behaviour after close()."""

    def test_closed_file_returns_empties(self, sample_raw_file):
        """Test a closed file returns empty values instead of raising.

        Protects against: AttributeError on the disposed .NET object.
        """
        rf = RawFile(str(sample_raw_file))
        rf.select_instrument(Device.MS, 1)
        assert rf.status_log_count == ENTRY_COUNT

        rf.close()

        assert rf.status_log_fields == []
        assert rf.status_log_count == 0
        assert rf.status_log_streams() == []
        log = rf.get_status_log()
        assert isinstance(log, InstrumentStatusLog)
        assert len(log) == 0
        assert log.fields == []
        assert log.to_pandas().shape == (0, 1)


# =============================================================================
# Value conversion (no .NET involved)
# =============================================================================


class TestStatusLogValueConverter:
    """The single converter shared by both .NET read paths."""

    def test_typed_values(self):
        """Test values as GetStatusLogEntry() reports them.

        Protects against: typed values being stringified on the way out.
        """
        numeric = StatusLogField(label=SPRAY_VOLTAGE, is_numeric=True)
        text = StatusLogField(label=STATUS_ROW, is_numeric=False)

        assert _status_log_value(numeric, 2515.897091586047) == 2515.897091586047
        assert _status_log_value(numeric, None) is None
        assert _status_log_value(text, "Instrument status Ok") == "Instrument status Ok"
        assert _status_log_value(text, None) is None

    def test_string_values(self):
        """Test values as the retention-time accessors report them.

        Protects against: a display string reaching the user as a string, and an
        empty cell becoming 0.0 instead of NaN.
        """
        numeric = StatusLogField(label=SPRAY_VOLTAGE, is_numeric=True)
        text = StatusLogField(label=STATUS_ROW, is_numeric=False)

        assert _status_log_value(numeric, "2515.9") == 2515.9
        assert _status_log_value(numeric, "") is None
        assert _status_log_value(numeric, "n/a") is None
        assert _status_log_value(text, "") == ""

    def test_text_field_is_never_coerced(self):
        """Test a text field keeps text that happens to look like a number.

        Protects against: a status message becoming a float.
        """
        text = StatusLogField(label=STATUS_ROW, is_numeric=False)

        assert _status_log_value(text, "2018") == "2018"


class TestStatusLogFieldModel:
    """Unit parsing of StatusLogField (pure, no file)."""

    @pytest.mark.parametrize(
        ("label", "unit"),
        [
            ("Spray Voltage (V)", "V"),
            ("Capillary Temperature (°C)", "°C"),
            ("Spray Current (µA)", "µA"),
            ("Inj. Flat. RF Freq (kHz)", "kHz"),
            ("Inj. Flat. RF Amp(V)", "V"),
            ("Ion (m/z) (V)", "V"),
            ("Sheath gas flow rate", ""),
            ("Status:", ""),
            ("Performance cy:", ""),
            ("Source (V):", ""),
            ("Fore Vacuum Sensor (mbar", ""),
            ("Voltage ()", ""),
            ("", ""),
        ],
    )
    def test_unit_from_label(self, label, unit):
        """Test only a trailing parenthetical is read as a unit.

        Protects against: inventing a unit from text in the middle of a label, and
        against reading nothing from a label that states one.
        """
        assert StatusLogField._unit_from_label(label) == unit

    def test_new_fields_have_defaults(self):
        """Test the added fields keep the old construction working.

        Protects against: a positional StatusLogField(label, data_type) call
        breaking when the dataclass gained fields.
        """
        field = StatusLogField("Test Field", 1)

        assert field.is_numeric is False
        assert field.unit == ""

    def test_field_is_equal_to_its_copy(self):
        """Test fields compare by value.

        Protects against: the dataclass losing equality, which tests and user code
        rely on when comparing two reads of the same file.
        """
        assert StatusLogField("x", 1, True, "V") == StatusLogField("x", 1, True, "V")


class TestStatusLogEntryModel:
    """StatusLogEntry behaviour (pure, no file)."""

    def test_defaults(self):
        """Test an empty entry.

        Protects against: a shared default dict being reused across entries.
        """
        first = StatusLogEntry()
        second = StatusLogEntry()

        assert first.time == 0.0
        assert len(first) == 0
        first.values["x"] = 1.0
        assert len(second) == 0

    def test_len_and_repr(self):
        """Test the size helpers.

        Protects against: __len__ counting fields rather than values.
        """
        entry = StatusLogEntry(time=1.5, values={"a": 1.0, "b": "text", "c": None})

        assert len(entry) == 3
        assert "1.5000" in repr(entry)
        assert "values=3" in repr(entry)


class TestInstrumentStatusLogModel:
    """InstrumentStatusLog behaviour (pure, no file)."""

    def build(self) -> InstrumentStatusLog:
        """A two-channel, one-section-row log with a missing numeric value."""
        fields = [
            StatusLogField(label=SECTION_ROW, is_numeric=False),
            StatusLogField(label=SPRAY_VOLTAGE, is_numeric=True, unit="V"),
            StatusLogField(label=CAPILLARY_TEMPERATURE, is_numeric=True, unit="°C"),
        ]
        entries = [
            StatusLogEntry(
                time=0.5, values={SECTION_ROW: None, SPRAY_VOLTAGE: 1.0, CAPILLARY_TEMPERATURE: 2.0}
            ),
            StatusLogEntry(
                time=1.5,
                values={SECTION_ROW: None, SPRAY_VOLTAGE: None, CAPILLARY_TEMPERATURE: 4.0},
            ),
        ]
        return InstrumentStatusLog(fields=fields, entries=entries)

    def test_channels_exclude_non_numeric_rows(self):
        """Test structure rows are not channels.

        Protects against: a section row becoming an all-NaN column.
        """
        log = self.build()

        assert log.channels == [SPRAY_VOLTAGE, CAPILLARY_TEMPERATURE]

    def test_defaults(self):
        """Test an empty log.

        Protects against: shared mutable defaults between instances.
        """
        log = InstrumentStatusLog()

        assert len(log) == 0
        assert log.channels == []
        assert log.to_pandas().shape == (0, 1)

    def test_frame_shape_and_missing_values(self):
        """Test a missing numeric value becomes NaN, not 0.

        Protects against: a gap in the log being plotted as a real zero.
        """
        frame = self.build().to_pandas()

        assert frame.shape == (2, 3)
        assert list(frame.columns) == ["time", SPRAY_VOLTAGE, CAPILLARY_TEMPERATURE]
        assert SECTION_ROW not in frame.columns
        assert frame[SPRAY_VOLTAGE].tolist()[0] == 1.0
        assert np.isnan(frame[SPRAY_VOLTAGE].tolist()[1])
        assert frame[CAPILLARY_TEMPERATURE].tolist() == [2.0, 4.0]
        assert frame["time"].tolist() == [0.5, 1.5]
        assert frame[SPRAY_VOLTAGE].dtype == np.float64

    def test_frame_keeps_channels_without_entries(self):
        """Test columns survive an entry filter that removed every row.

        Protects against: a filtered frame losing its shape.
        """
        log = self.build()
        empty = InstrumentStatusLog(fields=log.fields)

        assert empty.to_pandas().shape == (0, 3)

    def test_frame_coerces_unparseable_values(self):
        """Test a hand-built entry holding text under a numeric label yields NaN.

        Protects against: to_pandas() raising on a value the converter could not
        turn into a float.
        """
        fields = [StatusLogField(label="Temp (°C)", is_numeric=True)]
        entries = [
            StatusLogEntry(time=0.0, values={"Temp (°C)": "off"}),
            StatusLogEntry(time=1.0, values={}),
        ]

        frame = InstrumentStatusLog(fields=fields, entries=entries).to_pandas()

        assert np.isnan(frame["Temp (°C)"]).tolist() == [True, True]

    def test_len_and_repr(self):
        """Test the size helpers.

        Protects against: __len__ reporting fields instead of entries.
        """
        log = self.build()

        assert len(log) == 2
        assert "channels=2" in repr(log)
        assert "entries=2" in repr(log)

    def test_rows_are_not_sorted_or_deduplicated(self):
        """Test rows come out in the order they went in.

        Protects against: to_pandas() reordering rows away from file order.
        """
        fields = [StatusLogField(label="x", is_numeric=True)]
        entries = [
            StatusLogEntry(time=2.0, values={"x": 1.0}),
            StatusLogEntry(time=1.0, values={"x": 2.0}),
            StatusLogEntry(time=2.0, values={"x": 3.0}),
        ]

        frame = InstrumentStatusLog(fields=fields, entries=entries).to_pandas()

        assert frame["time"].tolist() == [2.0, 1.0, 2.0]


# =============================================================================
# A second instrument model (Zenodo QC sample)
# =============================================================================


class TestStatusLogOnASecondInstrument:
    """The same accessors on a different instrument model.

    The Zenodo QC sample was acquired on a Q Exactive GC, which reports a
    different channel set than the Q Exactive HF-X of tests/testdata/sample.raw.
    The numbers asserted here were read from that file: 72 status-log fields of
    which 54 are numeric channels, and 57 logged entries.

    Protects against: label handling and table building that only hold for
    tests/testdata/sample.raw.
    """

    # Measured on the Zenodo QC sample (Q Exactive GC).
    FIELD_COUNT = 72
    CHANNEL_COUNT = 54
    ENTRY_COUNT = 57
    FORE_VACUUM = "Fore Vacuum Sensor (mbar)"

    def test_log_shape(self, zenodo_raw_file_fixture):
        """Test counts and frame shape on the second instrument.

        Protects against: hard-coded field/channel/entry counts from the other file.
        """
        rf = zenodo_raw_file_fixture

        log = rf.get_status_log()

        assert len(log.fields) == self.FIELD_COUNT
        assert len(log.channels) == self.CHANNEL_COUNT
        assert len(log) == rf.status_log_count == self.ENTRY_COUNT
        assert log.to_pandas().shape == (self.ENTRY_COUNT, self.CHANNEL_COUNT + 1)

    def test_every_numeric_channel_holds_floats(self, zenodo_raw_file_fixture):
        """Test every numeric channel converts cleanly on this instrument too.

        Protects against: a value format on this instrument that the shared
        converter turns into None, silently filling the frame with NaN.
        """
        rf = zenodo_raw_file_fixture

        log = rf.get_status_log()
        frame = log.to_pandas()

        for channel in log.channels:
            assert frame[channel].notna().all(), channel
        for entry in log.entries:
            for channel in log.channels:
                assert isinstance(entry.values[channel], float), channel

    def test_rows_are_in_file_order(self, zenodo_raw_file_fixture):
        """Test a longer log still comes back with increasing times.

        Protects against: reordering introduced by windowing or by the reader.
        """
        times = zenodo_raw_file_fixture.get_status_log().to_pandas()["time"]

        assert (times.to_numpy()[1:] > times.to_numpy()[:-1]).all()

    def test_channels_are_the_labels_of_this_instrument(self, zenodo_raw_file_fixture):
        """Test the channel set follows the file, not a fixed list.

        Protects against: looking channels up by position, or assuming one
        instrument's labels exist on every instrument.
        """
        rf = zenodo_raw_file_fixture

        log = rf.get_status_log()

        assert "MS transfer line temp (°C)" in log.channels
        assert CAPILLARY_TEMPERATURE not in log.channels
        assert HIGH_VACUUM in log.channels

    def test_channel_lookups_agree_with_the_frame(self, zenodo_raw_file_fixture):
        """Test the single-channel accessor equals the frame column.

        Protects against: two read paths disagreeing about the same channel.
        """
        rf = zenodo_raw_file_fixture

        log = rf.get_status_log()
        frame = log.to_pandas()
        times, values = rf.get_status_log_channel(self.FORE_VACUUM)

        assert times.tolist() == frame["time"].tolist()
        assert values.tolist() == frame[self.FORE_VACUUM].tolist()
        assert rf.status_log_streams() == [(Device.MS, 1)]
