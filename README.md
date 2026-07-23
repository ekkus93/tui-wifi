# tui-wifi

[![CI/CD](https://github.com/ekkus93/tui-wifi/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/ekkus93/tui-wifi/actions/workflows/ci.yml)

`tui-wifi` is a desktop-like terminal Wi-Fi manager for Linux systems that use
NetworkManager. It presents nearby networks, saved profiles, connection status,
and common Wi-Fi actions without requiring users to learn `nmcli`.

> **Development status:** version 0.1.0 is an alpha release. Basic read-only
> hardware validation has been completed with NetworkManager 1.36.6. The broader
> connection, mutation, distribution, and failure-mode acceptance matrix remains
> incomplete, so this should not yet be treated as a production-ready networking
> tool.

## Requirements

- Linux
- Python 3.10 or newer
- NetworkManager running and managing the Wi-Fi adapter
- `nmcli` available in `PATH`
- A terminal supported by Textual

The TUI runs as the normal user. NetworkManager and Polkit handle authorization;
`tui-wifi` does not invoke `sudo` or modify network configuration files directly.

## Installation

The recommended approaches isolate `tui-wifi` from unrelated Python applications.
Avoid installing it into a shared Conda `base` environment unless you intentionally
want it to share and potentially update that environment's dependencies.

### Install directly from GitHub with pipx

Because the repository is public and contains a complete `pyproject.toml`, pipx can
install the application directly from GitHub:

```bash
pipx install "git+https://github.com/ekkus93/tui-wifi.git@master"
```

If `pipx` has not configured its command directory yet, run:

```bash
pipx ensurepath
```

Open a new shell after changing `PATH`, then start the application with:

```bash
tui-wifi
```

### Install directly from GitHub with pip

Install the latest code from `master` into the active virtual environment:

```bash
python -m pip install \
  "tui-wifi @ git+https://github.com/ekkus93/tui-wifi.git@master"
```

Git must be installed locally for either Git-based installation command.

To install a reproducible revision, replace `master` with a full commit SHA:

```bash
python -m pip install \
  "tui-wifi @ git+https://github.com/ekkus93/tui-wifi.git@FULL_COMMIT_SHA"
```

A tagged installation can be used after the corresponding tag has actually been
published:

```bash
python -m pip install \
  "tui-wifi @ git+https://github.com/ekkus93/tui-wifi.git@v0.1.0"
```

### Cleanly update a development installation

The package version remains `0.1.0` while development continues on `master`. To
ensure pip does not retain an older source revision with the same package version,
uninstall it and reinstall without the download cache:

```bash
python -m pip uninstall -y tui-wifi
python -m pip install --no-cache-dir \
  "tui-wifi @ git+https://github.com/ekkus93/tui-wifi.git@master"
hash -r
```

Using `--no-deps` on the install command is appropriate only when the environment
already contains compatible versions of every runtime dependency.

### Install from a checkout

```bash
git clone https://github.com/ekkus93/tui-wifi.git
cd tui-wifi
python -m venv .venv
. .venv/bin/activate
python -m pip install .
tui-wifi
```

For editable development installs, use:

```bash
python -m pip install -e '.[dev]'
```

The installed executable is named `tui-wifi`. There is no `wifi-tui` compatibility
alias.

## Usage

```bash
tui-wifi
tui-wifi --interface wlan0
tui-wifi --debug
tui-wifi --no-mouse
tui-wifi --version
tui-wifi --help
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

The interface also supports mouse selection and buttons where the terminal provides
mouse events.

## Supported in version 0.1

- Open Wi-Fi networks
- WPA/WPA2/WPA3 personal networks, subject to hardware and NetworkManager support
- Saved-profile reconnection
- Hidden open or personal networks
- Disconnect, forget-profile, and auto-connect controls
- Wi-Fi radio enable and disable controls
- Multiple Wi-Fi adapter discovery with explicit `--interface` selection
- NetworkManager 1.36 terse output, including indexed IP properties, literal IPv6
  addresses, and access-point frequencies containing an explicit `MHz` suffix

## Deliberately unsupported

- WPA-Enterprise / 802.1X
- WEP
- Captive-portal login automation
- VPN, Ethernet, bridge, VLAN, hotspot, or static-IP management
- ConnMan or direct `wpa_supplicant` management

Unsupported security is shown explicitly. There is no security-downgrade or
direct-file fallback.

## Troubleshooting installation

Verify which interpreter and executable are active:

```bash
python -c 'import sys, tui_wifi; print(sys.executable); print(tui_wifi.__file__)'
command -v tui-wifi
tui-wifi --version
```

If the shell still resolves a removed or replaced command after reinstalling, run
`hash -r` or open a new shell. Dependency warnings concerning unrelated packages in
a shared environment do not necessarily indicate a `tui-wifi` installation failure;
`python -m pip check` reports the health of the entire environment.

## Development

```bash
python -m pip install -e '.[dev]'
black --check --diff .
ruff check .
mypy src/tui_wifi
pytest -m 'not real_network'
python scripts/check_critical_coverage.py coverage.json
python -m build
```

The project treats every enabled lint finding, static-type error, test warning, and
formatting difference as a defect. Ruff runs its complete rule set. Mypy runs in
strict mode without module exemptions. Pytest converts warnings to errors. Findings
must be corrected in code or documentation; they must not be hidden with `noqa`,
`type: ignore`, warning filters, per-file exemptions, or disabled rule families.

The test suite uses deterministic process and Wi-Fi backends. Ordinary tests never
invoke the host's real `nmcli` mutation commands or change the machine's network
state. CI enforces a 90% global coverage floor plus explicit branch-coverage floors
for the mutation, profile, core backend, service, and process-runner modules.

Runtime dependencies are bounded in `pyproject.toml`. Contributors may create a
local lock file with their preferred environment manager; the distributable package
remains defined by `pyproject.toml`.

## CI/CD and release assets

GitHub Actions runs tests on Python 3.10, 3.11, 3.12, and 3.13, checks Black
formatting, full Ruff linting, strict Mypy typing, global and critical-module
coverage, and validates an installable wheel and source distribution. The package
job installs the wheel in a clean virtual environment and verifies the `tui-wifi`
command. Ordinary branch and pull-request runs do not upload or retain package or
coverage assets.

Release assets are created only when a version tag matching the package version is
pushed. For version `0.1.0`, create and push tag `v0.1.0` only after the release gates
and manual validation are complete:

```bash
git tag -a v0.1.0 -m "tui-wifi 0.1.0"
git push origin v0.1.0
```

The tagged workflow creates a GitHub Release and attaches exactly one wheel and one
source archive. A mismatched tag, such as `v0.1.1` while `pyproject.toml` still
contains `0.1.0`, fails without publishing assets.

## Privacy and credentials

Passwords are obscured by default, retained only for the active operation, and
redacted from command diagnostics, exceptions, logs, and test output. NetworkManager
is responsible for storing saved secrets.

See [the security notes](docs/SECURITY.md), [architecture](docs/ARCHITECTURE.md),
[troubleshooting guide](docs/TROUBLESHOOTING.md), and
[manual acceptance checklist](tests/manual/V01_ACCEPTANCE.md).
