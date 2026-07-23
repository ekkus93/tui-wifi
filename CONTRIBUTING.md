# Contributing

Use Python 3.11 or newer and install the development extras:

```bash
python -m pip install -e '.[dev]'
```

Before proposing a change, run `pytest`, `ruff format --check .`, `ruff check .`,
`mypy src/tui_wifi`, and `python -m build`.

Never add a fallback that invokes a shell, `sudo`, ConnMan, `wpa_supplicant`, or
writes NetworkManager configuration directly. Never place Wi-Fi credentials in
fixtures, logs, snapshots, or issue reports. Real-network tests must remain opt-in
and must not disconnect the developer's active network by default.
