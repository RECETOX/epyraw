"""Tests for typed trailer-extra access (issue #9).

Layout: unit tests that need no .NET runtime first, then integration
tests on tests/testdata/sample.raw (Q Exactive HF-X, scans 1-574, one
MS stream), then relative checks on the Zenodo QC file. The field-cache
tests sit with the integration tests: they install a fake .NET reader on
a closed RawFile, so they still need to open the file once.

Every literal number here was measured on those files:
- scan 100 typed values, the field-definition counts and the golden
  string snapshot of get_trailer_extra_information() were dumped from
  the files themselves.
"""

import dataclasses

import pytest

from epyraw import (
    Device,
    HeaderField,
    InstrumentNotSelectedError,
    InvalidScanNumberError,
    RawFile,
)
from epyraw.raw_file import _header_item_fields, _header_item_value, _unit_from_label

# Byte-for-byte snapshot of get_trailer_extra_information(100) on
# sample.raw, dumped from the unmodified implementation. The frozen
# method must keep producing exactly this, keys and order included.
GOLDEN_SCAN_100 = {
    "Multiple Injection:": "h ",
    "Multi Inject Info:": "IT=55 ",
    "AGC:": "On",
    "Micro Scan Count:": "1",
    "Scan Segment:": "1",
    "Scan Event:": "2",
    "Master Index:": "0",
    "Charge State:": "2",
    "Monoisotopic M/Z:": "0.0000",
    "Ion Injection Time (ms):": "55.000",
    "Max. Ion Time (ms):": "55.00",
    "FT Resolution:": "30000",
    "MS2 Isolation Width:": "1.40",
    "MS2 Isolation Offset:": "0.00",
    "AGC Target:": "100000",
    "HCD Energy:": "28.00",
    "Analyzer Temperature:": "27.06",
    "=== Mass Calibration: ===:": "",
    "Conversion Parameter B:": "211821440.4371",
    "Conversion Parameter C:": "-41163398.6430",
    "Temperature Comp. (ppm):": "-2.35",
    "RF Comp. (ppm):": "0.01",
    "Space Charge Comp. (ppm):": "-0.01",
    "Resolution Comp. (ppm):": "0.19",
    "Number of Lock Masses:": "0",
    "Lock Mass #1 (m/z):": "0.0000",
    "Lock Mass #2 (m/z):": "0.0000",
    "Lock Mass #3 (m/z):": "0.0000",
    "LM Search Window (ppm):": "0.0",
    "LM Search Window (mmu):": "0.0",
    "Number of LM Found:": "0",
    "Last Locking (sec):": "0.0",
    "LM m/z-Correction (ppm):": "0.00",
    "=== Ion Optics Settings: ===:": "",
    "S-Lens RF Level:": "40.00",
    "S-Lens Voltage (V):": "21.00",
    "Skimmer Voltage (V):": "15.00",
    "Inject Flatapole Offset (V):": "5.00",
    "Bent Flatapole DC (V):": "2.00",
    "MP2 and MP3 RF (V):": "900.00",
    "Gate Lens Voltage (V):": "2.25",
    "C-Trap RF (V):": "1420.0",
    "====  Diagnostic Data:  ====:": "",
    "Dynamic RT Shift (min):": "0.00",
    "Intens Comp Factor:": "0.5556",
    "Res. Dep. Intens:": "2.817",
    "CTCD NumF:": "0",
    "CTCD Comp:": "0.900",
    "CTCD ScScr:": "0.000",
    "RawOvFtT:": "13142.7",
    "LC FWHM parameter:": "15.0",
    "Rod:": "0",
    "PS Inj. Time (ms):": "13.750",
    "AGC PS Mode:": "-11",
    "AGC PS Diag:": "0",
    "HCD Energy eV:": "39.157",
    "AGC Fill:": "0.01",
    "Injection t0:": "0.000",
    "t0 FLP:": "0.00",
    "Access Id:": "0",
    "Analog Input 1 (V):": "0.000",
    "Analog Input 2 (V):": "0.000",
}

SECTION_LABELS = (
    "=== Mass Calibration: ===:",
    "=== Ion Optics Settings: ===:",
    "====  Diagnostic Data:  ====:",
)


class FakeHeaderItem:
    """Stand-in for a .NET HeaderItem (only the members we read)."""

    def __init__(self, label: str, data_type: int, is_numeric: bool):
        self.Label = label
        self.DataType = data_type
        self.IsNumeric = is_numeric


class FakeSelectedInstrument:
    """Stand-in for .NET SelectedInstrument (only the guard reads it)."""

    def __init__(self, instrument_index: int = 0, device_type: int = 1):
        self.InstrumentIndex = instrument_index  # 0-based, as .NET reports
        self.DeviceType = device_type


def fake_items() -> list[FakeHeaderItem]:
    """A small trailer-extra header for fake .NET objects.

    Mirrors the three shapes a real header has - DOUBLE, CHAR_STRING and
    a NULL section row - in the same order as the start of sample.raw.
    """
    return [
        FakeHeaderItem("Ion Injection Time (ms):", 11, True),
        FakeHeaderItem("Multi Inject Info:", 12, False),
        FakeHeaderItem("=== Mass Calibration: ===:", 0, False),
    ]


class FakeRawFile:
    """Stand-in for the .NET reader, counting trailer-extra header reads.

    Exposes only what the trailer-extra accessors touch, and counts
    calls to GetTrailerExtraHeaderInformation() so the field cache can
    be observed without a real .NET object. Install one on a closed
    RawFile as ``rf._raw_file``.
    """

    def __init__(self, items: list[FakeHeaderItem] | None = None, instrument_index: int = 0):
        self.items = fake_items() if items is None else items
        self.SelectedInstrument = FakeSelectedInstrument(instrument_index)
        self.header_calls = 0

    def GetTrailerExtraHeaderInformation(self) -> list[FakeHeaderItem]:
        self.header_calls += 1
        return self.items

    def Dispose(self) -> None:
        """No-op, so close() and __del__ on the host stay quiet."""


def raw_file_with_fake(sample_raw_file, items: list[FakeHeaderItem] | None = None) -> RawFile:
    """A closed RawFile with a FakeRawFile installed as its .NET reader.

    close() leaves the Python object alive with _raw_file = None and the
    selection it had (MS/1), so the fake can take over without a .NET
    object; its InstrumentIndex 0 matches that selection.
    """
    rf = RawFile(str(sample_raw_file))
    rf.select_instrument(Device.MS, 1)
    rf.close()
    rf._raw_file = FakeRawFile(items)
    return rf


def typed_snapshot(rf: RawFile, scans: tuple[int, ...]) -> dict:
    """Values of ``scans`` as {scan: {label: (type name, repr)}}.

    Compared instead of the dicts themselves: repr() is exact and, unlike
    ==, stays meaningful if a field ever holds a NaN.
    """
    return {
        scan: {k: (type(v).__name__, repr(v)) for k, v in rf.get_trailer_extra_values(scan).items()}
        for scan in scans
    }


class TestUnitFromLabel:
    """Unit parsing from label text - no .NET needed.

    Rule: strip at most one trailing ':', then take a parenthetical at
    the very end of what remains. This is a strict superset of the
    strict-end rule (no colon stripping): the two agree on every
    status-log label of sample.raw and of the Zenodo QC file, and on
    every label that does not end in ':' after the parenthetical.
    """

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            # real trailer-extra labels from sample.raw
            ("Ion Injection Time (ms):", "ms"),
            ("Temperature Comp. (ppm):", "ppm"),
            ("Lock Mass #1 (m/z):", "m/z"),
            ("S-Lens Voltage (V):", "V"),
            ("Max. Ion Time (ms):", "ms"),
            ("LM Search Window (mmu):", "mmu"),
            ("Last Locking (sec):", "sec"),
            ("Dynamic RT Shift (min):", "min"),
            # label without trailing colon behaves as the strict-end rule
            ("Ion Injection Time (ms)", "ms"),
        ],
    )
    def test_labels_with_units(self, label, expected):
        assert _unit_from_label(label) == expected

    @pytest.mark.parametrize(
        "label",
        [
            # real trailer-extra labels carrying no unit
            "Charge State:",
            "FT Resolution:",
            "HCD Energy:",
            "Multiple Injection:",
            "Master Index:",
            # section-header rows must never yield garbage
            *SECTION_LABELS,
        ],
    )
    def test_labels_without_units(self, label):
        assert _unit_from_label(label) == ""

    @pytest.mark.parametrize(
        ("label", "expected"),
        [
            ("", ""),  # empty label
            (":", ""),  # lone colon
            (")", ""),  # lone closer
            ("):", ""),  # closer plus colon
            ("weird):", ""),  # ends in ')' but no '(' anywhere
            ("Foo ():", ""),  # empty parenthetical
            ("Foo (a)b):", ""),  # nested ')' inside the content
            ("Foo (V)::", ""),  # two trailing colons: strip only one
            ("(V)", "V"),  # minimal positive case
        ],
    )
    def test_defensive_cases(self, label, expected):
        assert _unit_from_label(label) == expected


class TestHeaderItemValueConverter:
    """Type coercion by the field definition - no .NET needed."""

    numeric = HeaderField(
        label="Ion Injection Time (ms):", data_type=11, is_numeric=True, unit="ms"
    )
    text = HeaderField(label="Multi Inject Info:", data_type=12)
    section = HeaderField(label="=== Mass Calibration: ===:", data_type=0)
    onoff = HeaderField(label="AGC:", data_type=4)

    def test_float_keeps_stored_precision(self):
        assert _header_item_value(self.numeric, 54.999999701976776) == 54.999999701976776

    def test_int_widened_to_float(self):
        value = _header_item_value(self.numeric, 30000)
        assert value == 30000.0
        assert isinstance(value, float)

    def test_numeric_string_parsed_as_float(self):
        # float('55.000') is fine; int('55.000') would raise - never int()
        assert _header_item_value(self.numeric, "55.000") == 55.0

    def test_text_value_verbatim(self):
        assert _header_item_value(self.text, "IT=55 ") == "IT=55 "

    def test_numeric_looking_text_stays_text(self):
        # 'HCD Energy:' is CHAR_STRING in the file: '28.00' must not become 28.0
        value = _header_item_value(self.text, "28.00")
        assert value == "28.00"
        assert isinstance(value, str)

    def test_blank_text_stays_empty_string(self):
        assert _header_item_value(self.text, "") == ""

    def test_section_row_is_none(self):
        assert _header_item_value(self.section, None) is None

    def test_none_numeric_is_none(self):
        assert _header_item_value(self.numeric, None) is None

    def test_zero_survives_integer(self):
        # the truthiness trap the issue is about: bool(0) is False
        value = _header_item_value(self.numeric, 0)
        assert value == 0.0
        assert isinstance(value, float)

    def test_zero_survives_float(self):
        assert _header_item_value(self.numeric, 0.0) == 0.0

    def test_negative_integer_survives(self):
        assert _header_item_value(self.numeric, -11) == -11.0

    def test_bool_before_numeric(self):
        # isinstance(True, int) is True - a numeric field handed a bool
        # must still yield bool, never 1.0
        assert _header_item_value(self.numeric, True) is True

    def test_onoff_true(self):
        assert _header_item_value(self.onoff, True) is True

    def test_onoff_false_survives(self):
        # bool(False) is falsy; only an `is None` check may gate this
        assert _header_item_value(self.onoff, False) is False

    @pytest.mark.parametrize("raw", ["", "On"])
    def test_unparseable_numeric_becomes_none_not_crash(self, raw):
        # float('') and float('On') both raise ValueError; defensive only,
        # no blank numeric was observed in any file probed
        assert _header_item_value(self.numeric, raw) is None


class TestHeaderItemFields:
    """HeaderItem[] -> HeaderField mapping - no .NET needed."""

    def test_maps_fields_verbatim(self):
        items = [
            FakeHeaderItem("Ion Injection Time (ms):", 11, True),
            FakeHeaderItem("Multi Inject Info:", 12, False),
            FakeHeaderItem("=== Mass Calibration: ===:", 0, False),
        ]
        fields = _header_item_fields(items)
        assert [f.label for f in fields] == [
            "Ion Injection Time (ms):",
            "Multi Inject Info:",
            "=== Mass Calibration: ===:",
        ]
        assert [f.data_type for f in fields] == [11, 12, 0]
        assert [f.is_numeric for f in fields] == [True, False, False]
        assert fields[0].unit == "ms"
        assert fields[1].unit == ""
        assert fields[2].unit == ""

    def test_non_ascii_label_kept_verbatim(self):
        fields = _header_item_fields([FakeHeaderItem("Säule (µV):", 11, True)])
        assert fields[0].label == "Säule (µV):"
        assert fields[0].unit == "µV"

    def test_empty_header_yields_empty_list(self):
        # designed answer for a file without trailer extra; never
        # exercised by a real file (none available unverified)
        assert _header_item_fields([]) == []


class TestTrailerExtraFields:
    """Field definitions on sample.raw: 62 columns (measured)."""

    def test_field_count(self, raw_file):
        assert len(raw_file.trailer_extra_fields) == 62

    def test_data_type_counts(self, raw_file):
        fields = raw_file.trailer_extra_fields
        assert sum(1 for f in fields if f.data_type == 11) == 41  # DOUBLE
        assert sum(1 for f in fields if f.data_type == 8) == 14  # LONG
        assert sum(1 for f in fields if f.data_type == 12) == 3  # CHAR_STRING
        assert sum(1 for f in fields if f.data_type == 4) == 1  # ONOFF
        assert sum(1 for f in fields if f.data_type == 0) == 3  # NULL sections

    def test_numeric_field_count(self, raw_file):
        # IsNumeric is True exactly for LONG and DOUBLE (measured on all
        # 35,588 value cells of 574 scans)
        assert sum(f.is_numeric for f in raw_file.trailer_extra_fields) == 55

    def test_section_rows_are_present_but_not_numeric(self, raw_file):
        fields = raw_file.trailer_extra_fields
        labels = [f.label for f in fields]
        for section in SECTION_LABELS:
            assert section in labels
            field = next(f for f in fields if f.label == section)
            assert field.is_numeric is False
            assert field.data_type == 0
            assert field.unit == ""

    def test_units_parsed_from_labels(self, raw_file):
        fields = {f.label: f for f in raw_file.trailer_extra_fields}
        assert fields["Ion Injection Time (ms):"].unit == "ms"
        assert fields["Temperature Comp. (ppm):"].unit == "ppm"
        assert fields["Lock Mass #1 (m/z):"].unit == "m/z"
        assert fields["S-Lens Voltage (V):"].unit == "V"
        assert fields["Charge State:"].unit == ""
        assert fields["FT Resolution:"].unit == ""

    def test_unit_counts(self, raw_file):
        # 24 of the 62 labels contain a parenthetical and all 24 yield
        # a unit; the unit vocabulary measured on this file is these 7
        fields = raw_file.trailer_extra_fields
        units = [f.unit for f in fields if f.unit]
        assert len(units) == 24
        assert set(units) == {"ms", "ppm", "mmu", "m/z", "sec", "min", "V"}
        assert sum("(" in f.label for f in fields) == 24

    def test_labels_unique(self, raw_file):
        labels = [f.label for f in raw_file.trailer_extra_fields]
        assert len(set(labels)) == len(labels)

    def test_property_is_stable_across_calls(self, raw_file):
        assert raw_file.trailer_extra_fields == raw_file.trailer_extra_fields


class TestTrailerExtraFieldCache:
    """The parsed header is cached per (file, selection), not per call.

    Re-parsing the 62-item header across the pythonnet boundary costs
    about 1.4 ms - 92% of a get_trailer_extra_values() call on
    sample.raw - and the header cannot vary by scan because
    GetTrailerExtraHeaderInformation() takes no scan argument.
    """

    def test_header_read_once_for_repeated_access(self, sample_raw_file):
        rf = raw_file_with_fake(sample_raw_file)
        first = rf.trailer_extra_fields
        assert [f.label for f in first] == [
            "Ion Injection Time (ms):",
            "Multi Inject Info:",
            "=== Mass Calibration: ===:",
        ]
        for _ in range(5):
            assert rf.trailer_extra_fields == first
        assert rf._raw_file.header_calls == 1
        rf.close()

    def test_changed_instance_forces_reread(self, sample_raw_file):
        # a different instrument index means a different header. The key
        # is the selection the .NET side reports, which is what
        # select_instrument() changes on success.
        rf = raw_file_with_fake(sample_raw_file)
        assert len(rf.trailer_extra_fields) == 3
        rf._raw_file.SelectedInstrument = FakeSelectedInstrument(instrument_index=1)
        assert len(rf.trailer_extra_fields) == 3
        assert rf._raw_file.header_calls == 2
        rf.close()

    def test_changed_device_forces_reread(self, sample_raw_file):
        # a different device type at the same index is also a new header
        rf = raw_file_with_fake(sample_raw_file)
        assert len(rf.trailer_extra_fields) == 3
        rf._raw_file.SelectedInstrument = FakeSelectedInstrument(
            instrument_index=0, device_type=int(Device.Analog)
        )
        assert len(rf.trailer_extra_fields) == 3
        assert rf._raw_file.header_calls == 2
        rf.close()

    def test_wrapper_bookkeeping_is_not_what_the_cache_trusts(self, sample_raw_file):
        # stale Python-side bookkeeping must not mask the live selection:
        # the .NET selection is unchanged, so the cached header is still
        # the one that selection was read for
        rf = raw_file_with_fake(sample_raw_file)
        first = rf.trailer_extra_fields
        rf._selected_instance = 7
        rf._selected_device = Device.Analog
        assert rf.trailer_extra_fields == first
        assert rf._raw_file.header_calls == 1
        rf.close()

    def test_cache_cannot_be_poisoned_through_a_field(self, sample_raw_file):
        # the cached HeaderField objects are shared between calls, so
        # their immutability is what stops one caller relabelling the
        # values that later reads of another scan return
        rf = raw_file_with_fake(sample_raw_file)
        field = rf.trailer_extra_fields[0]
        with pytest.raises(dataclasses.FrozenInstanceError):
            field.label = "POISONED:"
        assert rf._raw_file.header_calls == 1  # still served from cache
        assert rf.trailer_extra_fields[0].label == "Ion Injection Time (ms):"
        rf.close()

    def test_new_dotnet_object_forces_reread(self, sample_raw_file):
        # a reopened file is a different .NET object under the same
        # selection; the cache compares identity, never a recycled id()
        rf = raw_file_with_fake(sample_raw_file)
        assert len(rf.trailer_extra_fields) == 3
        replacement = FakeRawFile(
            [FakeHeaderItem("Charge State:", 8, True)],
            instrument_index=0,
        )
        rf._raw_file = replacement
        assert [f.label for f in rf.trailer_extra_fields] == ["Charge State:"]
        assert replacement.header_calls == 1
        rf.close()

    def test_reselection_to_same_selection_reuses_cache(self, sample_raw_file):
        # re-selecting what is already selected is a no-op for the cache
        rf = raw_file_with_fake(sample_raw_file)
        first = rf.trailer_extra_fields
        assert rf.trailer_extra_fields == first
        assert rf._raw_file.header_calls == 1
        rf.close()

    def test_property_equality_and_copy_semantics(self, sample_raw_file):
        rf = raw_file_with_fake(sample_raw_file)
        fields = rf.trailer_extra_fields
        assert fields == rf.trailer_extra_fields  # equal content ...
        assert fields is not rf.trailer_extra_fields  # ... but a fresh list
        fields.append(HeaderField(label="injected:"))
        del fields[0]
        again = rf.trailer_extra_fields
        assert [f.label for f in again] == [
            "Ion Injection Time (ms):",
            "Multi Inject Info:",
            "=== Mass Calibration: ===:",
        ]
        rf.close()

    def test_copy_does_not_trigger_a_reread(self, sample_raw_file):
        # the mutated list above must not look like a miss to be refetched
        rf = raw_file_with_fake(sample_raw_file)
        fields = rf.trailer_extra_fields
        fields.clear()
        assert len(rf.trailer_extra_fields) == 3
        assert rf._raw_file.header_calls == 1
        rf.close()

    def test_values_identical_across_reselection(self, raw_file):
        scans = (1, 100, 574)
        before = typed_snapshot(raw_file, scans)
        raw_file.select_instrument(Device.MS, 1)
        assert typed_snapshot(raw_file, scans) == before

    def test_fields_intact_after_reading_every_scan(self, raw_file):
        # guards a stale or short cache: labels must still line up with
        # the values of the last scan read
        for scan in range(
            raw_file.run_header.first_spectrum, raw_file.run_header.last_spectrum + 1
        ):
            raw_file.get_trailer_extra_values(scan)
        fields = raw_file.trailer_extra_fields
        assert len(fields) == 62
        assert [f.label for f in fields] == list(raw_file.get_trailer_extra_values(574))

    def test_value_keys_keep_field_order_with_cache_hot(self, raw_file):
        labels = [f.label for f in raw_file.trailer_extra_fields]  # fills the cache
        for scan in (1, 7, 100, 574):
            assert list(raw_file.get_trailer_extra_values(scan)) == labels


class TestTrailerExtraValuesScan100:
    """Typed values at scan 100, every literal measured."""

    def test_keys_match_field_definitions(self, raw_file):
        values = raw_file.get_trailer_extra_values(100)
        assert len(values) == 62
        assert [f.label for f in raw_file.trailer_extra_fields] == list(values)

    def test_floats_at_stored_precision(self, raw_file):
        v = raw_file.get_trailer_extra_values(100)
        # NOT the display text '55.000', '1.40', '27.06', ...
        assert v["Ion Injection Time (ms):"] == 54.999999701976776
        assert v["MS2 Isolation Width:"] == 1.399999976158142
        assert v["Analyzer Temperature:"] == 27.058326641163664
        assert v["Temperature Comp. (ppm):"] == -2.3464923709637375
        assert v["Conversion Parameter B:"] == 211821440.4371274
        assert v["HCD Energy eV:"] == 39.15726089477539
        assert v["Intens Comp Factor:"] == 0.5555748343467712

    def test_plain_floats(self, raw_file):
        v = raw_file.get_trailer_extra_values(100)
        assert v["Max. Ion Time (ms):"] == 55.0
        assert v["AGC Fill:"] == 0.01
        assert v["C-Trap RF (V):"] == 1420.0

    def test_integers_widened_to_float(self, raw_file):
        v = raw_file.get_trailer_extra_values(100)
        assert v["FT Resolution:"] == 30000.0
        assert isinstance(v["FT Resolution:"], float)
        assert v["AGC Target:"] == 100000.0
        assert v["Charge State:"] == 2.0
        assert v["Micro Scan Count:"] == 1.0

    def test_negative_integer_survives(self, raw_file):
        assert raw_file.get_trailer_extra_values(100)["AGC PS Mode:"] == -11.0

    def test_text_values_verbatim(self, raw_file):
        v = raw_file.get_trailer_extra_values(100)
        assert v["Multiple Injection:"] == "h "
        assert v["Multi Inject Info:"] == "IT=55 "

    def test_numeric_looking_text_field_stays_string(self, raw_file):
        # CHAR_STRING per the file, even though it looks like a number
        value = raw_file.get_trailer_extra_values(100)["HCD Energy:"]
        assert value == "28.00"
        assert isinstance(value, str)

    def test_onoff_field_is_bool(self, raw_file):
        value = raw_file.get_trailer_extra_values(100)["AGC:"]
        assert value is True
        assert isinstance(value, bool)

    def test_zeros_survive(self, raw_file):
        v = raw_file.get_trailer_extra_values(100)
        assert v["Number of Lock Masses:"] == 0.0
        assert v["Master Index:"] == 0.0
        assert v["Analog Input 1 (V):"] == 0.0
        assert v["MS2 Isolation Offset:"] == 0.0
        assert v["Monoisotopic M/Z:"] == 0.0

    def test_section_rows_are_none(self, raw_file):
        v = raw_file.get_trailer_extra_values(100)
        for section in SECTION_LABELS:
            assert v[section] is None
            assert v[section] != 0.0

    def test_numeric_fields_are_all_float(self, raw_file):
        v = raw_file.get_trailer_extra_values(100)
        numeric = {f.label for f in raw_file.trailer_extra_fields if f.is_numeric}
        assert len(numeric) == 55
        assert all(isinstance(v[label], float) for label in numeric)


class TestTrailerExtraValuesScanEdges:
    """First and last scan on sample.raw (1-574, measured)."""

    def test_first_scan(self, raw_file):
        first = raw_file.get_trailer_extra_values(raw_file.run_header.first_spectrum)
        assert first["Charge State:"] == 0.0  # 0, not '', not None
        assert first["Number of Lock Masses:"] == 0.0
        assert first["FT Resolution:"] == 120000.0
        assert first["MS2 Isolation Width:"] == 1450.0
        assert first["AGC PS Diag:"] == 3501800.0
        assert first["Multiple Injection:"] == "ii"
        assert first["=== Mass Calibration: ===:"] is None

    def test_first_scan_blank_text_field(self, raw_file):
        # blank NON-numeric field: stays '', the only blanks ever observed
        first = raw_file.get_trailer_extra_values(raw_file.run_header.first_spectrum)
        assert first["HCD Energy:"] == ""
        assert sum(x is None for x in first.values()) == 3  # sections only

    def test_last_scan(self, raw_file):
        last = raw_file.get_trailer_extra_values(raw_file.run_header.last_spectrum)
        assert last["Multi Inject Info:"] == "IT=55 "
        assert last["FT Resolution:"] == 30000.0
        assert last["Charge State:"] == 2.0

    def test_labels_align_across_scans(self, raw_file):
        # labels align index-for-index with the header on all 574 scans
        # (measured); sampled here with stride 50 to keep the suite fast
        labels = [f.label for f in raw_file.trailer_extra_fields]
        first = raw_file.run_header.first_spectrum
        last = raw_file.run_header.last_spectrum
        for scan in [*range(first, last, 50), last]:
            assert list(raw_file.get_trailer_extra_values(scan)) == labels


class TestTrailerExtraInformationUnchanged:
    """The frozen string accessor must keep producing exactly what it did."""

    def test_scan_100_golden_snapshot(self, raw_file):
        trailer = raw_file.get_trailer_extra_information(100)
        assert trailer == GOLDEN_SCAN_100
        assert list(trailer) == list(GOLDEN_SCAN_100)

    def test_display_text_and_quirks(self, raw_file):
        t = raw_file.get_trailer_extra_information(100)
        assert len(t) == 62
        assert t["Ion Injection Time (ms):"] == "55.000"  # display, not typed
        assert t["Multi Inject Info:"] == "IT=55 "  # trailing space survives
        assert t["AGC:"] == "On"  # ONOFF renders 'On' here, True typed
        assert t["Master Index:"] == "0"  # the `if values[i]` guard stays put
        assert t["=== Mass Calibration: ===:"] == ""  # '' here, None typed
        assert sum(1 for x in t.values() if x == "0") == 7  # at scan 100 and 1
        assert sum(1 for x in t.values() if x == "") == 3  # scan 100; 4 at scan 1

    def test_scan_1_display_text(self, raw_file):
        t = raw_file.get_trailer_extra_information(1)
        assert t["HCD Energy:"] == ""  # blank numeric-looking text field
        assert t["Charge State:"] == "0"
        assert t["Multi Inject Info:"] == "IT=28;28 "
        assert sum(1 for x in t.values() if x == "") == 4

    def test_typed_and_string_accessors_have_the_same_keys(self, raw_file):
        assert list(raw_file.get_trailer_extra_values(100)) == list(
            raw_file.get_trailer_extra_information(100)
        )

    def test_closed_file_still_returns_empty_dict(self, sample_raw_file):
        rf = RawFile(str(sample_raw_file))
        rf.close()
        assert rf.get_trailer_extra_information(100) == {}

    def test_no_selection_still_raises_runtime_error(self, sample_raw_file):
        rf = RawFile(str(sample_raw_file))
        with pytest.raises(RuntimeError):
            rf.get_trailer_extra_information(100)
        rf.close()


class TestTrailerExtraErrors:
    """Error paths of the new typed accessors."""

    @pytest.mark.parametrize("bad_scan", [0, -1, -574, 10**6])
    def test_out_of_range_scan(self, raw_file, bad_scan):
        with pytest.raises(InvalidScanNumberError):
            raw_file.get_trailer_extra_values(bad_scan)

    def test_scan_just_past_last(self, raw_file):
        with pytest.raises(InvalidScanNumberError):
            raw_file.get_trailer_extra_values(raw_file.run_header.last_spectrum + 1)

    def test_closed_file_values(self, sample_raw_file):
        rf = RawFile(str(sample_raw_file))
        rf.close()
        with pytest.raises(InstrumentNotSelectedError):
            rf.get_trailer_extra_values(100)

    def test_closed_file_fields(self, sample_raw_file):
        rf = RawFile(str(sample_raw_file))
        rf.close()
        with pytest.raises(InstrumentNotSelectedError):
            _ = rf.trailer_extra_fields

    def test_no_selection_values(self, sample_raw_file):
        rf = RawFile(str(sample_raw_file))  # opened, nothing selected
        with pytest.raises(InstrumentNotSelectedError):
            rf.get_trailer_extra_values(100)
        rf.close()

    def test_no_selection_fields(self, sample_raw_file):
        rf = RawFile(str(sample_raw_file))
        with pytest.raises(InstrumentNotSelectedError):
            _ = rf.trailer_extra_fields
        rf.close()

    def test_selection_makes_calls_work(self, sample_raw_file):
        # the guard uses SelectedInstrument.InstrumentIndex, measured -1
        # when nothing is selected and >= 0 after select_instrument()
        rf = RawFile(str(sample_raw_file))
        rf.select_instrument(Device.MS, 1)
        assert len(rf.trailer_extra_fields) == 62
        rf.close()


class TestZenodoTrailerExtra:
    """Relative checks on the Zenodo QC file - no absolute counts.

    (Measured here: 58 fields, 51 numeric, scans 1-4117; kept as
    relative assertions so the file can be swapped without churn.)
    """

    def test_fields_non_empty_and_values_aligned(self, zenodo_raw_file_fixture):
        fields = zenodo_raw_file_fixture.trailer_extra_fields
        assert len(fields) > 0
        scan = zenodo_raw_file_fixture.run_header.first_spectrum
        values = zenodo_raw_file_fixture.get_trailer_extra_values(scan)
        assert len(values) == len(fields)
        assert [f.label for f in fields] == list(values)

    def test_numeric_values_are_float(self, zenodo_raw_file_fixture):
        fields = zenodo_raw_file_fixture.trailer_extra_fields
        scan = zenodo_raw_file_fixture.run_header.first_spectrum
        values = zenodo_raw_file_fixture.get_trailer_extra_values(scan)
        for field in fields:
            if field.is_numeric:
                assert isinstance(values[field.label], float)

    def test_same_keys_as_string_accessor(self, zenodo_raw_file_fixture):
        scan = zenodo_raw_file_fixture.run_header.first_spectrum
        assert list(zenodo_raw_file_fixture.get_trailer_extra_values(scan)) == list(
            zenodo_raw_file_fixture.get_trailer_extra_information(scan)
        )
