# ESPHome receiver firmware

The repository root contains `bt-monitor.yaml` and its required `bm2_aes.h`.
Download both from the same release. HACS only installs the Home Assistant component;
copy these firmware files separately to your ESPHome configuration directory.

1. Copy `secrets.yaml.example` from this directory to `secrets.yaml` beside the YAML.
2. Set your Wi-Fi, API encryption key, OTA and fallback hotspot passwords and BM2 MACs.
   Use uppercase, colon-separated MAC addresses. Generate an API key using the
   Python command in the example. Keep these secrets private.
3. Change `devicename` to a unique lowercase node name, e.g. `garage-bm2`.
   Preserve the existing name and credentials when updating a deployed receiver.
4. Adapt `esp32.board` to your actual ESP32. Boards without BLE cannot be used.
5. Rename the example Range Rover/Porsche battery labels to your physical batteries.
   To monitor one battery, remove the other battery's substitutions, globals,
   lambda branches and entities. For more batteries, extend those sections together.
6. Validate and compile with ESPHome, then flash by USB for a first installation:

```sh
esphome config bt-monitor.yaml
esphome compile bt-monitor.yaml
esphome upload bt-monitor.yaml
```

7. Add the ESPHome node to HA and confirm real voltage changes before setting up
   BM2 Battery Monitor. Select the actual receiver voltage entity IDs in its UI.
8. For another receiver, use another node name and its own API key. Add its voltage
   entities to each battery's receiver list in the integration's Configure dialog.

Live monitoring decrypts manufacturer advertisements from configured MAC addresses;
only 14-byte manufacturer payloads are considered. The manufacturer ID contributes
the first two ciphertext bytes. The inherited advertisement field offsets still
need validation against captured hardware packets. History decoding follows the
separate GATT protocol verified against upstream source.

Live voltage accepts 0–40.95 V (the BM2 history voltage encoding range), including
flat-battery values. Charge is published only for values 0–100; an invalid charge
byte does not suppress voltage or presence. These checks cannot authenticate a BLE
broadcast. Do not use this monitor as a safety interlock.

The node reports at most every 30 seconds per battery. Presence expires after
120 seconds. HA canonical sensor expiry defaults to 180 seconds. Voltage is force
updated even if unchanged. The first accepted report is published immediately.
The active Bluetooth proxy offers three connection slots for short HA history
connections; do not add a persistent BM2 BLE client alongside it.

The original local configuration is preserved in ignored `.local/` during repository
preparation. It is not part of the public repository. Existing deployed credentials
have not been rotated by this change.
