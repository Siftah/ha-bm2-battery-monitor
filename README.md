# BM2 Battery Monitor for Home Assistant

Live voltage monitoring and automatic recovery of stored BM2 battery history,
using ESPHome Bluetooth receivers. Local operation; no cloud account or MQTT broker required.

**First beta:** software tests cover setup, receiver selection and recovery. Real BM2
hardware and an ESPHome proxy still need an end-to-end acceptance test. Please
report your HA/ESPHome versions and device results in an issue.

## What it does

- One canonical live voltage sensor per physical battery, even with several ESP32 receivers.
- A connectivity sensor that turns off when all receiver readings are stale.
- Automatic history download after the battery returns from a coverage gap.
- Initial and hourly history synchronization, with serialized Bluetooth connections.
- Hourly minimum, mean and maximum voltage statistics under a stable battery ID.
- A **Recover history** button and `bm2_history.recover` action.
- Setup and receiver selection through Home Assistant's UI.

```text
BM2 battery ── Bluetooth broadcasts ── ESPHome receiver(s) ── HA live battery sensor
     └──── stored history ── active Bluetooth proxy ── HA hourly statistics
```

## Requirements

- Home Assistant **2026.4.0 or newer**, with Bluetooth and Recorder enabled.
- A BM2 monitor using the protocol documented by [KrystianD/bm2-battery-monitor](https://github.com/KrystianD/bm2-battery-monitor/tree/dev).
  BM6, BM7 and other variants are not verified.
- One or more supported ESP32 boards running the included [firmware configuration](bt-monitor.yaml).
  The default target is a classic ESP32 (`esp32dev`), using ESP-IDF.
- At least one active ESPHome Bluetooth proxy, or connectable local HA Bluetooth adapter,
  able to reach the BM2 when downloading history. A free connection slot is required.
- Existing live ESPHome voltage entities in HA. HACS installs the HA integration;
  it does **not** flash ESP32 firmware.

The included firmware was configuration-validated with ESPHome 2026.9.1; see
[validation status](docs/VALIDATION.md) for the exact tests and remaining hardware checks.

## Install through HACS

1. In HACS, open **Custom repositories** from its menu.
2. Add `https://github.com/Siftah/ha-bm2-battery-monitor` and select **Integration** as the category.
3. Find **BM2 Battery Monitor**, download it, and restart Home Assistant.
4. Open **Settings → Devices & services → Add integration → BM2 Battery Monitor**.
5. Add each physical battery once:
   - Give it a meaningful name, such as *Range Rover Starter Battery*.
   - Choose a permanent ID such as `rangerover_starter`.
   - Enter its Bluetooth MAC address.
   - Select **all ESPHome voltage receiver entities for that battery**.
6. Use **Configure** on the integration entry to change receivers or recovery intervals.

[Open repository in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=Siftah&repository=ha-bm2-battery-monitor&category=integration)

This is a HACS **custom repository**. Publication here does not mean it is listed
in HACS's default catalogue or endorsed by Home Assistant.

### Manual installation

Copy `custom_components/bm2_history` into `/config/custom_components/bm2_history`,
restart HA, then follow UI setup above. All runtime files are inside that directory.

## Prepare the ESPHome receivers

Follow [the firmware guide](esphome/README.md). Copy `bt-monitor.yaml`, `bm2_aes.h`
and your own `secrets.yaml` into your ESPHome configuration directory. Use a
**different node name for each receiver**, and configure the same battery MACs on
receivers that should monitor the same batteries. Physical battery names can remain
identical across receivers; HA still gives each receiver its own entities.

For an existing installation, compare and merge the firmware rather than replacing
working board/network settings. Voltage sensors must use `force_update: true` so
unchanged voltages continue to report freshness. Keep `bluetooth_proxy.active: true`.

## Entities and data

Each battery has a **Voltage** sensor, **Connected** binary sensor and
**Recover history** button. Entity IDs are assigned by HA from the battery name;
check the device page for your actual IDs.

The canonical voltage sensor selects the freshest finite receiver reading and
becomes unavailable after the offline threshold. Its attributes identify the chosen
source, last report, battery ID, recovery status, last sync and last download error.
Selection and expiry are checked every 30 seconds.

The external statistics ID is always:

```text
bm2_history:<battery_id>_voltage
```

For example, `bm2_history:rangerover_starter_voltage`. **Keep the battery ID stable**
to preserve the same statistics series. The live sensor has its own ordinary HA
history; downloaded records populate the external statistics series below.

```yaml
type: statistics-graph
title: Starter battery voltage
chart_type: line
period: hour
days_to_show: 7
stat_types: [min, mean, max]
entities:
  - bm2_history:rangerover_starter_voltage
  - bm2_history:porsche_starter_voltage
```

### Recovery settings

| Setting | Default | Minimum | Meaning |
| --- | --- | --- | --- |
| Offline threshold | 180 seconds | 60 seconds | A longer reporting gap marks recovery pending. |
| History sync interval | 3600 seconds | 3600 seconds | Regular sync while a receiver reports fresh voltage. |

A seamless change between receivers does not trigger gap recovery. Pending state
and last synchronization persist across HA restarts. Failed downloads retry no
sooner than five minutes later, when fresh receiver readings are available.
Downloads have a 90-second timeout, plus bounded disconnect cleanup. Connections
are released after each attempt. Close the BM2 phone app during downloads.

Press **Recover history**, or run:

```yaml
action: bm2_history.recover
data:
  battery_id: rangerover_starter
```

Manual recovery can run even if the receiver voltage is stale. A failed attempt
is logged and remains pending. Listen for `bm2_history_recovered` for the decoded
record count and queued hourly count. The event confirms queuing, not Recorder's
completion; inspect **Developer Tools → Statistics** to verify imported rows.

## History accuracy and limitations

BM2 history has no absolute clock. Following upstream, the latest sample is anchored
to the download's minute, with older samples spaced two minutes apart. Times are
**estimates**, particularly after a BM2 power interruption or changed sampling
interval. Repeated downloads can move estimated sample times between hour buckets.

Only complete, past UTC hours with 30 samples are imported. Partial oldest and
current hours are skipped. Existing hours are replaced on subsequent imports.
Min/max describe the two-minute samples; they do not capture all cranking transients.
The crank field is decoded but not imported. Gaps older than the BM2's retained
memory cannot be recovered.

Downloaded records do not backfill the native ESPHome sensor's History graph.
Charge estimates remain receiver entities; this integration's shared live entity
and recovered statistics currently measure **voltage**.

## Upgrade from the earlier YAML prototype

Back up HA first. Replace the old component directory with this version.
Existing `bm2_history:` YAML is imported into UI configuration entries, preserving
battery IDs and statistics IDs. After confirming each entry appears, remove that
YAML block and restart HA; future changes belong in the UI. Duplicate MAC addresses
are rejected. See the [legacy configuration example](home-assistant/bm2-history-example.yaml).

## Troubleshooting and removal

See [troubleshooting](docs/TROUBLESHOOTING.md). To remove a battery, delete its
integration entry. To uninstall completely, delete all entries, remove the HACS
repository download, and restart HA. Existing Recorder statistics remain until you
remove them separately using HA's statistics tools. Removing the integration does
not change the ESP32 firmware.

## Contributing and attribution

See [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md), and
[validation status](docs/VALIDATION.md). Report bugs through GitHub issues;
remove MAC addresses, credentials and private network details from logs.

MIT licensed. BM2 protocol and cryptography are adapted from
[Krystian Dużyński's upstream project](https://github.com/KrystianD/bm2-battery-monitor/tree/3deebb5c044ed76b93622e8cb73bd9f362d7eadb),
reviewed at `dev` commit `3deebb5c044ed76b93622e8cb73bd9f362d7eadb`.
See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). This project is independently
maintained and is not affiliated with the monitor manufacturer, ESPHome or HA.
