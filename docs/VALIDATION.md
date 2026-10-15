# Validation status

Target baseline: Home Assistant 2026.4.0 (Python 3.14.2+).
Firmware configuration baseline: ESPHome 2026.9.1, classic ESP32, ESP-IDF.

## Local preparation results

- ESPHome 2026.9.1: final configuration validated and firmware compiled successfully.
- Home Assistant 2026.4.0: integration tests run with an in-memory Recorder and
  mocked Bluetooth transport; physical devices were not used.
- Protocol compared with upstream dev commit `3deebb5c044ed76b93622e8cb73bd9f362d7eadb`.

## Automated checks

- Unit tests: encryption, history framing, record decoding, timestamp reconstruction,
  complete-hour statistics, receiver handoff, gap and retry decisions.
- Home Assistant tests: UI setup and options, duplicate rejection, entry/platform
  lifecycle, canonical sensor freshness, manual recovery, failure and serialization.
- Ruff formatting and linting.
- HACS validation and Home Assistant hassfest in GitHub Actions.
- ESPHome configuration and firmware compilation with dummy CI-only credentials.

Consult the Actions run for the release you install. A configured check is not
proof that it passed; the first beta remains hardware-unverified.

## Hardware acceptance before a stable release

1. Flash a receiver; compare voltage and charge to the BM2 app and a voltmeter.
2. Capture a known advertisement to verify the inherited live-field offsets.
3. Add a second receiver and verify one canonical voltage sensor follows the
   freshest receiver, then expires when both stop reporting.
4. Let coverage lapse for over three minutes, return the BM2 to range and confirm
   automatic history recovery through the ESPHome proxy.
5. Inspect complete UTC hours in Recorder, not just a queued-import event.
6. Restart HA during a gap and verify pending recovery survives.
7. Test a busy connection slot/phone connection and verify retry and cleanup.
8. Check low-voltage and 0% charge behavior using a controlled fixture.

No physical hardware was flashed during repository preparation.
