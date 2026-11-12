# Changelog

All notable changes to this project are documented here.

Version numbers follow [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`, incremented for
breaking / additive / bug-fix changes respectively. While the major version is `0` the public API is not
considered stable (SemVer §4.5), so a breaking change raises MINOR rather than MAJOR — additive work and
pure bug fixes are still kept apart.

## Adding an entry

One line per pull request, under **[Unreleased]**, newest first:

    - what a user of the package will notice ([#123](https://github.com/RECETOX/epyraw/pull/123))

Nothing else changes. When cutting a release: rename `[Unreleased]` to `[x.y.z] - YYYY-MM-DD`, add an
empty `[Unreleased]` above it, and set `version` in `pyproject.toml` to the same number — the tagged
release is what gets published, so the two must agree.

## [Unreleased]

- Trailer extra values can now be read as numbers, not just as display text:
  `RawFile.trailer_extra_fields` and `RawFile.get_trailer_extra_values(scan)` give the per-scan
  acquisition parameters at stored precision (injection time `54.999999701976776`, not `'55.000'`),
  typed by the file's own data types (a `bool` for `AGC:`, `'28.00'` as text for the string field
  `HCD Energy:`, zeros preserved), keyed by the file's verbatim labels;
  `get_trailer_extra_information()` is unchanged.
  ([#18](https://github.com/RECETOX/epyraw/pull/18))
- Type-checked `src/epyraw` under strict mypy, which exposed and fixed a latent bug:
  `Chromatogram.total_ion_current` raised `AttributeError` on numpy ≥ 2 because `np.trapz` was removed,
  so it now integrates directly and is covered by tests.
  ([#4](https://github.com/RECETOX/epyraw/pull/4))
- Bumped the locked `certifi` and `urllib3` versions.
  ([#2](https://github.com/RECETOX/epyraw/pull/2))

## [0.1.0] - 2026-10-22

- Initial release: read Thermo Scientific `.raw` mass spectrometry files from Python over the
  RawFileReader .NET assemblies — spectra, chromatograms, scan headers, trailer extras and file
  metadata, with typed auto-sampler tray handling.
  ([#1](https://github.com/RECETOX/epyraw/pull/1))

[Unreleased]: https://github.com/RECETOX/epyraw/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/RECETOX/epyraw/releases/tag/v0.1.0
