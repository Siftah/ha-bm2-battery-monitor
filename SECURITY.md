# Security

Do not include passwords, API keys, full secrets files or private Bluetooth
addresses in public issues. Use [GitHub private vulnerability reporting](https://github.com/Siftah/ha-bm2-battery-monitor/security/advisories/new)
for security reports if enabled; otherwise use the maintainer's GitHub profile
to arrange a private channel before sharing sensitive details.

BM2 uses a fixed device-protocol AES key. This project does not add authentication
to the monitor. Operate HA and ESPHome on a trusted network.
