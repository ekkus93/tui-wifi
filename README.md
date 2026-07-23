# tui-wifi

[![CI/CD](https://github.com/ekkus93/tui-wifi/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/ekkus93/tui-wifi/actions/workflows/ci.yml)

`tui-wifi` is a desktop-like terminal Wi-Fi manager for Linux systems that use
NetworkManager. It presents nearby networks, saved profiles, connection status,
and common Wi-Fi actions without requiring users to learn `nmcli`.

> **Development status:** version 0.1.0 is an alpha release. The automated test
> suite is designed not to touch the host's real Wi-Fi state. Hardware validation
> must still be completed on supported distributions before treating it as a
> production-ready networking tool.

## Requirements

- Linux
- Python 3.10 or newer
- NetworkManager running
- `nmcli` available in `PATH`
- A terminal supported by Textual

The TUI runs as the normal user. NetworkManager and Polkit handle authorization;
`tui-wifi` does not invoke `sudo` or modify network configuration files directly.

## Installation

### Install directly from GitHub

Because the repository is public and contains a complete `pyproject.toml`, pip can
install `tui-wifi` directly from GitHub. Git must be installed on the local machine.

Install the latest code from `master`:

```bash
python -m pip install "tui-wifi @ git+https://github.com/ekkus93/tui-wifi.git@master"
```

Install a specific release tag, which is preferable for a stable installation:

```bash
python -m pip install "tui-wifi @ git+https://github.com/ekkus93/tui-wifi.git@v0.1.0"
```

Upgrade or reinstall the current `master` version:

```bash
python -m pip install --upgrade --force-reinstall \
  "tui-wifi @ git+https://github.com/ekkus93/tui-wifi.git@master"
```

After installation, start the application with:

```bash
tui-wifi
```

### Install from a checkout

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
tui-wifi
```

### Install with pipx after cloning

```bash
pipx install .
tui-wifi
```

## Usage

```bash
tui-wifi
tui-wifi --interface wlan0
tui-wifi --debug
tui-wifi --version
```

### Keyboard shortcuts

| Key | Action |
|---|---|
| Arrow keys / `j`, `k` | Select a network |
| Enter | Connect to the selected network |
| `r` | Rescan |
| `d` | Disconnect |
| `h` | Connect to a hidden network |
| `s` | Saved networks |
| `w` | Enable or disable Wi-Fi |
| `i` | Connection details |
| `q` | Quit |

The interface also supports mouse selection and buttons where the terminal
provides mouse events.

## Supported in version 0.1

- Open Wi-Fi networks
- WPA/WPA2/WPA3 personal networks, subject to hardware and NetworkManager support
- Saved-profile reconnection
- Hidden open or personal networks
- Disconnect, forget profile, and auto-connect controls
- Multiple Wi-Fi adapter discovery with `--interface` selection

## Deliberately unsupported

- WPA-Enterprise / 802.1X
- WEP
- Captive-portal login automation
- VPN, Ethernet, bridge, VLAN, hotspot, or static-IP management
- ConnMan or direct `wpa_supplicant` management

Unsupported security is shown explicitly. There is no security-downgrade or
direct-file fallback.

## Development

```bash
python -m pip install -e '.[dev]'
black --check .
ruff check .
mypy src/tui_wifi
pytest -m 'not real_network'
python scripts/check_critical_coverage.py coverage.json
python -m build
```

The project treats every enabled lint finding, static-type error, test warning,
and formatting difference as a defect. Ruff runs its complete rule set. Mypy
runs in strict mode without module exemptions. Pytest converts warnings to
errors. Findings must be corrected in code or documentation; they must not be
hidden with `noqa`, `type: ignore`, warning filters, per-file exemptions, or
disabled rule families.

The test suite uses deterministic process and Wi-Fi backends. Ordinary tests
never invoke the host's real `nmcli` mutation commands or change the machine's
network state. CI enforces a 90% global coverage floor plus explicit branch-
coverage floors for the mutation, profile, core backend, service, and process
runner modules.

Runtime dependencies are bounded in `pyproject.toml`. Contributors may create a
local lock file with their preferred environment manager; the distributable
package remains defined by `pyproject.toml`.

## CI/CD and release assets

GitHub Actions runs tests on Python 3.10, 3.11, 3.12, and 3.13, checks formatting,
linting, types, global and critical-module coverage, and validates an installable
wheel and source distribution. Ordinary branch and pull-request runs do not
upload or retain package or coverage assets.

Release assets are created only when a version tag matching the package version is
pushed. For version `0.1.0`, create and push tag `v0.1.0`:

```bash
git tag -a v0.1.0 -m "tui-wifi 0.1.0"
git push origin v0.1.0
```

The tagged workflow creates a GitHub Release and attaches exactly one wheel and
one source archive. A mismatched tag, such as `v0.1.1` while `pyproject.toml` still
contains `0.1.0`, fails without publishing assets.

## Privacy and credentials

Passwords are obscured by default, retained only for the active operation, and
redacted from command diagnostics, exceptions, logs, and test output. NetworkManager
is responsible for storing saved secrets.

See [the security notes](docs/SECURITY.md), [architecture](docs/ARCHITECTURE.md),
and [troubleshooting guide](docs/TROUBLESHOOTING.md).
