# tui-wifi Version 0.1 Implementation TODO

This is the authoritative implementation checklist for [`SPEC.md`](./SPEC.md). It is
updated after the initial Ralph Loop implementation on 2026-07-22.

## Completed automated implementation

- [x] Python 3.11+ `src/` package with `wifi-tui` entry point and Textual dependency.
- [x] Repository metadata, MIT license, contributor guide, changelog, and CI/CD workflow.
- [x] CI matrix for Python 3.11, 3.12, and 3.13; formatting, linting, typing, tests, and
  clean package-install validation.
- [x] GitHub Release assets restricted to matching `v<package-version>` tag runs; normal
  branch and pull-request builds do not upload persistent assets.
- [x] CI/CD status badge and release procedure documented in `README.md`.
- [x] Backend-independent domain models, stable error categories, and friendly messages.
- [x] Ephemeral secret wrapper and command/diagnostic redaction, including child output
  that echoes sensitive argument values.
- [x] Asynchronous subprocess execution using argument arrays, fixed locale, bounded
  timeouts, child cleanup, separate stdout/stderr, and no shell.
- [x] Backend protocol, typed operation inputs, and deterministic fake backend.
- [x] Strict escaped-field, scalar, UUID, IP, state, and security parsers.
- [x] NetworkManager `nmcli` status, radio, adapter, scan, access-point, saved-profile,
  active-connection, connect, hidden-connect, disconnect, delete, and auto-connect
  operations.
- [x] State verification after every mutating backend operation.
- [x] Conservative AP grouping, saved-profile association, and desktop-like sorting.
- [x] Coherent service snapshots, refresh generations, stale-result rejection,
  last-valid-state preservation, selected-interface policy, and serialized mutations.
- [x] Main TUI, loading/empty/error states, keyboard bindings, mouse-capable controls,
  responsive layout, and network detail view.
- [x] Password, open-network, unsupported-network, hidden-network, disconnect, radio,
  and destructive forget confirmations.
- [x] Saved-network connect, forget-by-UUID, and auto-connect controls.
- [x] CLI `--version`, `--debug`, `--interface`, `--no-mouse`, and help behavior.
- [x] Bounded XDG debug logging without credential disclosure.
- [x] Unit, service, process, fake-`nmcli`, CLI, and Textual smoke/pilot tests.
- [x] Architecture, security, troubleshooting, installation, limitations, and privacy
  documentation.
- [x] Unsafe-fallback audit: no shell, sudo, direct networking-file writes, ConnMan, or
  `wpa_supplicant` fallback.

## Validation still required

- [ ] Let GitHub Actions validate Python 3.11, 3.12, and 3.13 with Textual, Ruff, Mypy,
  pytest coverage, wheel build, and source-distribution build.
- [ ] Resolve any CI-only compatibility or static-analysis findings without weakening
  failure visibility or credential protections.
- [ ] Complete Ubuntu or Debian hardware validation as a normal user.
- [ ] Complete Fedora or Arch hardware validation as a normal user.
- [ ] Validate WPA2 personal, WPA3 personal, an open test network, saved reconnect,
  incorrect password, hidden SSID, disconnect, forget, and Wi-Fi toggle.
- [ ] Validate `rfkill`, duplicate SSIDs, multiple adapters, adapter removal, terminal
  resizing, SSH use, and NetworkManager restart where test hardware permits.
- [ ] Inspect normal and debug logs after success, command failure, timeout, and
  cancellation to confirm no credential leakage.
- [ ] Record evidence in `tests/manual/V01_ACCEPTANCE.md`.

## Release gate

- [ ] All GitHub Actions jobs pass.
- [ ] Manual platform evidence is recorded.
- [ ] Every acceptance criterion in `SPEC.md` is implemented, tested, or explicitly
  deferred with rationale.
- [ ] No known credential leak, dangerous fallback, silent failure, or unverified success
  remains.
- [ ] Tag and publish version 0.1.0 only after the preceding gates pass.

## Deferred backlog

- [ ] Direct NetworkManager D-Bus backend.
- [ ] WPA-Enterprise and 802.1X.
- [ ] Captive-portal detection/browser integration.
- [ ] Hotspot creation.
- [ ] Static IP and DNS editing.
- [ ] Additional networking backends, internationalization, themes, and native packages.
