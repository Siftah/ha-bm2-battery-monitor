# Contributing

Open an issue with a reproducible example before a substantial behavioral change.
Preserve stable battery IDs and distinguish live history from external statistics.
Never commit secrets or private BLE captures without sanitizing addresses.

Use Python 3.14.2+ for the Home Assistant test suite:

```sh
python3.14 -m venv .venv
. .venv/bin/activate
pip install -r requirements-test.txt
pytest -q
ruff check custom_components tests
ruff format --check custom_components tests
```

Protocol-only checks can run without HA:

```sh
python3 -m unittest discover -s tests -p 'test_protocol.py' -v
python3 -m unittest discover -s tests -p 'test_tracking.py' -v
```

For ESPHome, follow esphome/README.md. CI uses dummy credentials and compiles
without flashing. Real BM2 recovery must be checked using docs/VALIDATION.md.

## Releases

Update manifest.json, CHANGELOG.md and validation notes together. Run all checks,
commit, tag the exact version (for example `v0.2.0b1`), and publish a GitHub prerelease
for betas. HACS installs the integration directory directly from the repository;
no ZIP asset is required. Stable releases should follow successful hardware acceptance.
A repository can be added through HACS Custom repositories without being in the
default catalogue. Default-catalogue submission is a separate review process.
