# Troubleshooting

## Integration does not appear

Confirm `custom_components/bm2_history/manifest.json` is under HA's `/config`
directory, restart HA and refresh the browser. HA 2026.4.0 or newer is required.
HACS downloading the integration does not configure it or flash your ESP32.

## Voltage is unavailable / Connected is off

Check each configured ESPHome receiver voltage entity in Developer Tools → States.
Check the BM2 MACs, firmware decryption and Wi-Fi/API connection. Select the physical
battery's receiver entities rather than the canonical BM2 sensor. Keep `force_update`
enabled. The offline threshold defaults to three minutes; checks occur every 30 seconds.
A source must be numeric and finite. An entity that republishes stale values can
misrepresent freshness, so use the included receiver sensors without intermediary
helpers. HA cannot prove that a republished value came from a new radio packet.

## History download fails

Enable Bluetooth and Recorder. Set `bluetooth_proxy.active: true` on the receiver,
check available connection slots, and close the phone's BM2 app. An advertisement
can reach a scanner that cannot make an active connection. Look for
`custom_components.bm2_history` in HA logs and inspect the canonical voltage sensor's
`last_history_error` attribute. Move the battery within range and press Recover
history. Failed automatic attempts wait five minutes before retrying while fresh
receiver readings are available.

## Recovery succeeds but graph is empty

Use the external `bm2_history:<battery_id>_voltage` statistics ID in a statistics-graph
card. The live sensor's History graph is separate. Less than one complete past hour
may yield zero imported rows. A recovery event reports rows queued to Recorder;
check Developer Tools → Statistics for actual data and metadata errors.

## Wrong times or different values after another sync

BM2 does not supply timestamps. Downloads assume uninterrupted two-minute sampling
and anchor the newest sample to download time. Power interruption, firmware behavior
or a different sampling cadence makes this estimate inaccurate. Full hour aggregates
can change when the download minute shifts the reconstructed sample timestamps.

## Debug logging

```yaml
logger:
  default: warning
  logs:
    custom_components.bm2_history: debug
```

Share HA and ESPHome versions, board, steps, expected versus actual results and
redacted logs. Never attach secrets.yaml or an unredacted full ESPHome configuration.
