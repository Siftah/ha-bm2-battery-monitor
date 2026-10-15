# Third-party notices

BM2 protocol, AES key, GATT UUIDs, history command sequence and history record
layout are derived from KrystianD/bm2-battery-monitor, MIT licensed:
https://github.com/KrystianD/bm2-battery-monitor

Reviewed dev commit: 3deebb5c044ed76b93622e8cb73bd9f362d7eadb.
Relevant upstream files: bm2_python/src/bm2/client.py, encryption.py,
bit_utils.py, and bm2_esphome/bm2.yaml. The upstream copyright and full MIT terms
are retained in LICENSE and the integration's LICENSE.

The live advertisement routing and field offsets were inherited from the local
ESPHome prototype. They are not claimed to be verified by upstream's connected
GATT example. The AES header uses ESP-IDF's mbedTLS API; no mbedTLS source is vendored.
