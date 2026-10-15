# Changelog

## 0.2.0b1

First shareable HACS beta; hardware acceptance remains pending.

- Root custom_components layout, HACS metadata, licensing and release documentation.
- UI battery setup, options and automatic import of legacy YAML configuration.
- Canonical live voltage and connectivity entities across multiple ESPHome receivers.
- Per-battery recovery button and deduplicated, serialized background downloads.
- Restored ESPHome AES header and moved private settings to secrets.
- Accepted low-voltage and zero-charge readings; publish the first report immediately.
- Added CI checks and integration tests alongside protocol tests.

## 0.1.0

Local YAML prototype: two-battery advertisements and automatic hourly history imports.
