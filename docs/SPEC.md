# tui-wifi Version 0.1 Specification

## 1. Document status

- **Project:** `tui-wifi`
- **Version:** 0.1
- **Status:** Initial implementation specification
- **Primary platform:** Linux systems managed by NetworkManager
- **Implementation language:** Python
- **TUI framework:** Textual
- **Initial backend:** `nmcli`

This document defines the required behavior, architecture, scope, safety properties, and acceptance criteria for the first usable release of `tui-wifi`.

## 2. Product summary

`tui-wifi` is a terminal user interface for connecting a Linux computer to Wi-Fi. It should provide an experience comparable to a desktop environment's Wi-Fi menu while remaining usable entirely from a terminal.

The primary workflow must be simple:

1. Start `tui-wifi`.
2. See nearby wireless networks.
3. Select a network.
4. Enter a password when required.
5. Connect.

Users must not need to understand NetworkManager connection profiles, interface names, BSSIDs, DHCP, `nmcli`, D-Bus, or `wpa_supplicant` to complete normal tasks.

## 3. Product goals

### 3.1 Primary goals

The first release must:

- Automatically discover usable Wi-Fi adapters.
- Automatically scan for nearby Wi-Fi networks.
- Display networks in a clear, desktop-like list.
- Clearly identify the connected network.
- Connect to open and personal WPA/WPA2/WPA3 networks.
- Reuse saved NetworkManager connection profiles when possible.
- Prompt securely for a password only when needed.
- Disconnect from the current wireless network.
- Forget saved wireless networks.
- connect to hidden SSIDs.
- Enable and disable Wi-Fi through NetworkManager.
- Present clear progress and actionable error messages.
- Keep technical details available without making them the default view.
- Work with keyboard-only interaction and support mouse input where the terminal supports it.

### 3.2 Quality goals

The implementation must prioritize:

- Correctness over optimistic fallback behavior.
- Explicit failures over silent or ambiguous failures.
- Credential safety.
- Testable separation between the TUI and system backend.
- Predictable state transitions.
- Compatibility with common NetworkManager-based Linux distributions.
- Graceful behavior in narrow or limited terminals.

## 4. Non-goals for version 0.1

The following are explicitly outside the initial scope:

- WPA-Enterprise and 802.1X configuration.
- EAP-TLS, PEAP, TTLS, or certificate management.
- Captive-portal login automation.
- VPN management.
- Ethernet management.
- Bridge, bond, VLAN, route, or DNS profile editing.
- Direct management of `wpa_supplicant.conf`.
- ConnMan support.
- Direct `iwd` support when NetworkManager is not managing it.
- Static IP configuration.
- Hotspot creation.
- Ad-hoc networking.
- Wi-Fi Direct.
- MAC address spoofing controls.
- General-purpose NetworkManager profile editing.

A network using an unsupported authentication method must be shown as unsupported rather than handled through a hidden fallback.

## 5. Target environment

### 5.1 Required runtime environment

Version 0.1 requires:

- Linux.
- Python 3.11 or newer.
- NetworkManager running and managing at least one Wi-Fi interface.
- `nmcli` available in `PATH`.
- A terminal capable of running Textual applications.

### 5.2 Expected distributions

The application should be designed and tested for NetworkManager-based installations of:

- Ubuntu.
- Debian.
- Fedora.
- Arch Linux.
- Linux Mint.

Distribution support is conditional on the required Python version, NetworkManager, and `nmcli` being available.

### 5.3 Privilege model

The TUI must run as the normal desktop or console user. The application must not require the whole TUI to run as root.

Privileged networking actions must be delegated to NetworkManager. NetworkManager and Polkit are responsible for authorization.

The application must not:

- Invoke itself through `sudo` automatically.
- Store a sudo password.
- ask for a sudo password in its own UI.
- modify system networking files directly.
- attempt a root-only fallback after an authorization failure.

When NetworkManager denies an action, the application must report an authorization error and provide technical details where available.

## 6. User experience

## 6.1 Startup behavior

On startup, the application must:

1. Validate that it is running on Linux.
2. Locate `nmcli`.
3. Confirm that NetworkManager is available.
4. Discover Wi-Fi devices.
5. Determine whether Wi-Fi networking is enabled.
6. Load current connection information.
7. Request an initial scan when appropriate.
8. Display available networks.

Startup checks must not block the TUI indefinitely. The interface should appear promptly and display a loading state while backend queries complete.

If no usable Wi-Fi adapter exists, the application must show a dedicated empty-state message rather than an empty list.

Examples:

- `No Wi-Fi adapter was found.`
- `NetworkManager is not running.`
- `The nmcli utility is not installed.`
- `Wi-Fi is disabled.`
- `Wi-Fi is blocked by a hardware or software switch.`

## 6.2 Main screen

The main screen must emphasize nearby networks and current connection state.

Each visible network row should include:

- Connected indicator.
- SSID.
- Signal-strength representation.
- Security indicator.
- Saved-profile indicator where useful.
- Unsupported indicator where applicable.

The default screen must not expose BSSID, frequency, channel, UUID, or raw NetworkManager state values.

Suggested ordering:

1. Currently connected network.
2. Saved networks in range.
3. Other supported networks by descending signal strength.
4. Unsupported networks by descending signal strength.

Networks with the same SSID and compatible security configuration should normally be grouped into one user-facing entry. The backend may retain individual BSSIDs for diagnostics and connection selection.

Blank SSIDs must not appear as ordinary unnamed rows. Hidden networks should be handled through the hidden-network workflow.

## 6.3 Main actions

The main screen must provide these actions:

- Connect.
- Disconnect.
- Refresh or rescan.
- Open connection details.
- Connect to a hidden network.
- Open saved networks.
- Enable or disable Wi-Fi.
- Quit.

Actions must be accessible through keyboard bindings. Mouse-accessible controls should also be available where practical.

The UI must visually disable actions that are invalid in the current state.

## 6.4 Connect workflow

### Saved network

When the selected network has a usable saved NetworkManager profile, the application should attempt to activate that profile without asking for the password again.

If activation fails because credentials are missing or rejected, the application may offer a password prompt. It must not repeatedly retry the same saved secret without telling the user.

### New secured network

For a new WPA/WPA2/WPA3 personal network, display a connection dialog containing:

- Network name.
- Password field.
- Show-password control.
- Auto-connect control, enabled by default.
- Connect button.
- Cancel button.

The password must be obscured by default.

### Open network

For an open network, present a confirmation dialog or connect directly depending on the final UI design. The application must clearly mark the network as open before connection.

### Unsupported network

Selecting an unsupported network must show a clear message such as:

`This network uses an authentication method that tui-wifi does not yet support.`

The application must not attempt to connect using guessed or downgraded security settings.

## 6.5 Connection progress

Connection is an asynchronous operation. While connecting, the UI must:

- Show the target SSID.
- Show that a connection attempt is active.
- Prevent duplicate connection requests for the same operation.
- Allow cancellation when it can be performed safely.
- Continue rendering and responding to user input.
- Enforce a bounded timeout.

Where backend information permits, progress may be translated into friendly stages:

- Preparing.
- Connecting to the network.
- Authenticating.
- Requesting an IP address.
- Verifying connection.
- Connected.

The UI must not declare success solely because the `nmcli` command exited successfully. It must refresh device and active-connection state and confirm that the selected Wi-Fi connection is active.

## 6.6 Successful connection

After a successful connection, show:

- Connected SSID.
- IP address when available.
- A brief success notification.

The network list and detail panel must refresh immediately.

## 6.7 Failed connection

Failures must be presented in plain language with an optional expandable technical-details section.

Required friendly error categories include:

- Password rejected.
- Secrets missing.
- Network no longer in range.
- Connection timed out.
- Connected to the access point but failed to obtain an IP address.
- Wi-Fi disabled.
- Radio blocked.
- NetworkManager unavailable.
- Authorization denied.
- Unsupported security.
- Adapter unavailable.
- Operation cancelled.
- Unexpected backend error.

Raw command output must not be the only error shown.

Unexpected errors must remain visible and diagnosable. They must not be silently converted into an empty network list, a generic `not connected` state, or a successful result.

## 6.8 Disconnect workflow

The user must be able to disconnect the active Wi-Fi connection.

After requesting disconnection, the application must refresh active connection state and confirm that the interface is no longer using that connection.

If disconnection fails, the previously known connection state must remain visible and an error must be shown.

## 6.9 Saved networks workflow

The saved-networks screen must list saved Wi-Fi connection profiles with at least:

- User-facing profile name.
- SSID when available.
- Auto-connect state.
- Active state.

Supported actions:

- Connect.
- Forget.
- Toggle auto-connect.
- View details.
- Return to the main screen.

Forgetting a network is destructive and must require confirmation.

The confirmation must identify the network or profile being deleted. The application must not remove multiple profiles merely because they share an SSID unless the UI explicitly asks the user to delete all matching profiles.

## 6.10 Hidden-network workflow

The hidden-network dialog must collect:

- SSID.
- Security type.
- Password when required.
- Auto-connect preference.

Version 0.1 should support:

- Open.
- WPA/WPA2/WPA3 personal, subject to NetworkManager and hardware support.

The dialog must reject an empty SSID and unsupported security modes before invoking the backend.

## 6.11 Wi-Fi enable and disable

The application must expose NetworkManager's Wi-Fi radio state.

When disabling Wi-Fi:

- Ask for confirmation when an active Wi-Fi connection exists.
- Clearly indicate that the connection will be interrupted.
- Refresh radio and device state after the operation.

When enabling Wi-Fi:

- Refresh device state.
- Request a scan when a usable adapter becomes available.

A hardware `rfkill` block must not be reported as though the software toggle succeeded in making Wi-Fi usable.

## 6.12 Details view

A non-default details view may show:

- Interface name.
- Device state.
- SSID.
- BSSID.
- Signal strength.
- Security.
- IPv4 and IPv6 addresses.
- Gateway.
- DNS servers.
- Connection profile name.
- Connection UUID.
- NetworkManager reason codes.

Sensitive secrets must never be displayed in the details view.

## 7. Keyboard and accessibility behavior

The application must support keyboard-only operation.

Recommended bindings:

- Arrow keys or `j`/`k`: move selection.
- Enter: connect or open the selected item.
- `r`: refresh.
- `d`: disconnect.
- `f`: forget selected saved network.
- `h`: hidden-network dialog.
- `s`: saved-networks screen.
- `w`: Wi-Fi toggle.
- `i`: connection details.
- Escape: close dialog or return.
- `q`: quit when no modal dialog is active.

Bindings must be displayed in the footer or discoverable help.

The UI should remain usable without Unicode icons. Signal bars and status markers must have plain-text fallbacks.

Color must not be the sole indicator of connection, security, failure, or selection state.

## 8. Backend architecture

## 8.1 Layering

The application must be divided into these conceptual layers:

1. **TUI layer**
   - Textual widgets, screens, dialogs, notifications, and key bindings.
2. **Application/service layer**
   - User operations, orchestration, state refresh, and operation serialization.
3. **Backend interface**
   - Abstract Wi-Fi management contract independent of `nmcli` formatting.
4. **NetworkManager `nmcli` adapter**
   - Command construction, execution, parsing, timeout handling, and error classification.
5. **Process runner**
   - Safe asynchronous subprocess execution with structured results.
6. **Domain models**
   - Immutable or controlled data structures representing devices, access points, profiles, active connections, and errors.

The TUI must not construct arbitrary `nmcli` commands or parse `nmcli` output directly.

## 8.2 Backend interface

The backend contract should support operations equivalent to:

- Check backend availability.
- Get NetworkManager general state.
- Get Wi-Fi radio state.
- Set Wi-Fi radio state.
- List Wi-Fi devices.
- Request scan.
- List access points.
- Get active Wi-Fi connection.
- List saved Wi-Fi profiles.
- Connect using a saved profile.
- Connect to a visible network with supplied credentials.
- Connect to a hidden network.
- Disconnect a device or active connection.
- Delete a saved profile.
- Set profile auto-connect.
- Get connection details.

The contract must use domain models and typed exceptions or result objects rather than returning raw strings.

## 8.3 `nmcli` invocation rules

All `nmcli` execution must follow these rules:

- Use argument arrays; never build shell command strings.
- Do not use `shell=True`.
- Force machine-readable, explicitly selected fields where possible.
- Set locale to a predictable value for parsing.
- Use bounded timeouts.
- Capture stdout and stderr separately.
- Preserve exit code, timeout state, and stderr for diagnostics.
- Never log secrets or complete credential-bearing argument lists.
- Treat malformed output as a backend error, not as an empty result.
- Keep all command construction in the backend adapter.

Where `nmcli` supports terse and escaped output, the parser must correctly handle escaped delimiters and backslashes. Parsing must not rely on naive `str.split(':')` logic when fields may contain escaped separators.

## 8.4 Password handling

Passwords are sensitive ephemeral values.

The application must:

- Obscure password input by default.
- Keep passwords only as long as needed for the connection operation.
- Avoid copying passwords into persistent application state.
- Never include passwords in logs, exceptions, notifications, test snapshots, or crash reports.
- Never write passwords to project-owned configuration files.
- Allow NetworkManager to persist secrets according to its normal profile and secret-agent behavior.
- Redact command arguments and environment data in diagnostic output.

If an `nmcli` invocation necessarily receives a password as an argument or input, the process-runner API must mark the sensitive values and ensure they are redacted from all structured diagnostics.

## 8.5 Concurrency and operation ownership

Only one mutating Wi-Fi operation should run at a time per device.

Mutating operations include:

- Connect.
- Disconnect.
- Forget.
- Enable or disable Wi-Fi.
- Change auto-connect.

Scans and state refreshes must be coordinated so that stale results cannot overwrite newer state.

Each asynchronous request should have an operation identifier or generation number. Results from an obsolete operation must be discarded explicitly.

Cancellation must distinguish between:

- User cancellation.
- Timeout.
- Backend cancellation.
- Application shutdown.

These states must not be conflated with connection failure.

## 8.6 State model

The application service should maintain a coherent snapshot containing:

- Backend availability.
- NetworkManager state.
- Wi-Fi radio state.
- Hardware/software block state when discoverable.
- Wi-Fi devices.
- Selected device.
- Visible access-point groups.
- Saved profiles.
- Active connection.
- Current operation.
- Last refresh time.
- Current visible error or warning.

The UI should render from snapshots rather than making unrelated backend calls from individual widgets.

A refresh must either publish a coherent new snapshot or preserve the previous snapshot with an error. It must not partially erase valid state when one backend query fails.

## 9. Domain model requirements

Minimum models should include:

### WiFiDevice

- Interface name.
- Device identifier if needed.
- State.
- Managed state.
- Hardware address where useful.
- Active connection reference.

### AccessPoint

- SSID as bytes and safely decoded display text where possible.
- BSSID.
- Signal percentage.
- Frequency.
- Channel when derivable.
- Security capabilities.
- Active state.
- Device association.

### NetworkGroup

User-facing aggregation of compatible access points:

- Display SSID.
- Security class.
- Strongest signal.
- Connected state.
- Saved-profile references.
- Supported state.
- Member BSSIDs.

### SavedProfile

- Profile name.
- UUID.
- SSID.
- Interface restriction if any.
- Auto-connect state.
- Security class.
- Active state.

### ActiveWiFiConnection

- Profile name and UUID.
- SSID.
- Device.
- Connection state.
- IPv4 details.
- IPv6 details.
- Gateway and DNS.

### BackendError

- Stable application error category.
- User-facing summary.
- Optional user-facing guidance.
- Technical details.
- Command exit code when applicable.
- NetworkManager reason code when applicable.
- Retriable flag.
- Sensitive-data-redacted guarantee.

## 10. Security classification

The backend must normalize detected networks into user-facing classes:

- Open.
- WEP, unsupported by default.
- WPA personal.
- WPA2 personal.
- WPA3 personal.
- Mixed personal mode.
- Enterprise, unsupported in version 0.1.
- Unknown or unsupported.

Security detection must be conservative. If the adapter cannot confidently classify a network as a supported personal mode, it must not silently attempt an open or weaker connection.

WEP should be treated as unsupported in version 0.1 unless a later product decision explicitly adds it.

## 11. Error handling and observability

## 11.1 No silent failures

The implementation must not:

- Convert parser errors into empty lists.
- Ignore nonzero subprocess exit codes.
- Ignore timeout exceptions.
- report connection success without state verification.
- catch broad exceptions and continue without recording the failure.
- replace a valid state snapshot with empty defaults after a failed refresh.
- retry mutating operations indefinitely.
- downgrade to direct configuration-file edits.
- select a different interface or profile without making that decision explicit.

## 11.2 Diagnostics

The application should support a diagnostics mode, likely through a command-line flag such as `--debug`.

Diagnostics may include:

- Application version.
- Python version.
- Textual version.
- NetworkManager version.
- `nmcli` version.
- Selected non-sensitive command metadata.
- Timings.
- Exit codes.
- Parsed state transitions.

Diagnostics must redact:

- Passwords.
- Secret fields.
- Private keys or certificates if enterprise support is added later.

Normal users should see friendly messages. Technical details should remain available for troubleshooting.

## 12. Command-line behavior

The installed command should be:

```text
wifi-tui
```

The exact package distribution name may be `tui-wifi`, while the import package should use a valid Python identifier such as `tui_wifi`.

Initial command-line options should include:

- `--version`.
- `--debug`.
- `--no-mouse` if needed by Textual behavior.
- `--interface <name>` for explicit adapter selection.

Invalid options or an unavailable requested interface must produce a clear nonzero exit.

## 13. Configuration

Version 0.1 should require little or no configuration.

Any application configuration must follow the XDG Base Directory conventions. Configuration must not store Wi-Fi passwords.

Potential future preferences include:

- Preferred interface.
- Unicode icon use.
- Mouse behavior.
- Refresh interval.
- Debug logging location.

The application must work without a configuration file.

## 14. Packaging and repository standards

The project should use:

- `pyproject.toml` as the package and tool configuration source.
- A `src/` package layout.
- Type annotations for public and internal interfaces.
- `pytest` for tests.
- Ruff for linting and formatting.
- Mypy or Pyright for static type checking.
- A lock strategy documented for contributors.

Recommended repository layout:

```text
.
├── docs/
│   ├── SPEC.md
│   └── TOOD.md
├── src/
│   └── tui_wifi/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── cli.py
│       ├── models.py
│       ├── errors.py
│       ├── services/
│       ├── backends/
│       │   ├── base.py
│       │   └── nmcli.py
│       ├── process/
│       └── ui/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── manual/
├── pyproject.toml
├── README.md
├── LICENSE
└── .gitignore
```

The implementation may refine this layout, but it must preserve clear separation between UI, application logic, backend code, and subprocess handling.

## 15. Testing strategy

## 15.1 Unit tests

Unit tests must cover:

- Escaped `nmcli` field parsing.
- Empty and malformed output.
- Device parsing.
- Access-point parsing.
- Security classification.
- Saved-profile parsing.
- Active connection and IP detail parsing.
- Error classification.
- Password redaction.
- Network grouping and sorting.
- State snapshot behavior.
- Operation cancellation and stale-result rejection.
- User-facing error mapping.

## 15.2 Backend contract tests

A fake backend must implement the same backend interface and support deterministic scenarios:

- No adapter.
- Wi-Fi disabled.
- Empty scan.
- Successful open connection.
- Successful secured connection.
- Password rejection.
- DHCP timeout.
- Network disappearance.
- Authorization denial.
- NetworkManager restart.
- Malformed backend response.
- Slow operation and cancellation.

The TUI tests should primarily use the fake backend rather than the host's real Wi-Fi state.

## 15.3 TUI tests

Textual pilot tests should verify:

- Startup loading state.
- Main list rendering.
- Keyboard navigation.
- Password-dialog behavior.
- Password visibility toggle.
- Connect progress.
- Success notification.
- Failure dialog and technical details.
- Saved-network deletion confirmation.
- Hidden-network validation.
- Wi-Fi toggle confirmation.
- Narrow-terminal behavior.

## 15.4 Integration tests

Integration tests may invoke a fake `nmcli` executable placed earlier in `PATH`. This allows validation of:

- Exact command arguments.
- Environment variables.
- Timeout handling.
- stdout/stderr parsing.
- exit-code handling.
- secret redaction.

Real NetworkManager integration tests must be opt-in and must never disconnect the developer's active network by default.

## 15.5 Manual validation

Manual release validation should cover at least:

- A supported Ubuntu or Debian system.
- A supported Fedora or Arch system.
- Open network.
- WPA2 personal network.
- WPA3 personal network when hardware is available.
- Saved credential reconnect.
- Incorrect password.
- Hidden network.
- Wi-Fi software toggle.
- Hardware `rfkill` block where testable.
- Multiple visible access points with one SSID.
- Multiple Wi-Fi adapters where available.
- Terminal resize.
- SSH session behavior.

## 16. Acceptance criteria for version 0.1

Version 0.1 is acceptable when all of the following are true:

1. `wifi-tui` starts successfully on a supported NetworkManager-based Linux installation.
2. The main screen appears without requiring root privileges.
3. Nearby supported networks are displayed and sorted sensibly.
4. The current connection is clearly identified.
5. A user can connect to a new WPA2 personal network by selecting it and entering a password.
6. A user can reconnect to a saved network without re-entering a stored password.
7. A user can connect to an open network.
8. A user can disconnect from the active Wi-Fi network.
9. A user can forget one selected saved profile after confirmation.
10. A user can connect to a supported hidden network.
11. A user can enable and disable Wi-Fi through NetworkManager.
12. Incorrect passwords produce a specific visible error.
13. DHCP failure is distinguished from authentication failure where NetworkManager exposes enough information.
14. Backend failures do not silently erase the last valid UI state.
15. Passwords never appear in logs, exception strings, test output, or technical-details views.
16. All subprocess calls use argument arrays and bounded timeouts.
17. The UI remains responsive while scanning and connecting.
18. Unit, backend, integration, and TUI test suites pass.
19. Documentation describes installation, use, limitations, and troubleshooting.
20. No direct `wpa_supplicant`, ConnMan, or networking-file fallback exists.

## 17. Future considerations

Potential later releases may add:

- Direct NetworkManager D-Bus backend.
- Enterprise Wi-Fi workflows.
- Captive-portal detection and browser launching.
- Hotspot creation.
- Static IP and custom DNS settings.
- Additional backend implementations.
- Internationalization.
- Theme customization.
- Distribution packages.

These additions must not compromise the version 0.1 backend abstraction, credential protections, or failure-visibility requirements.
