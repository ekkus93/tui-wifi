# tui-wifi Version 0.1 Implementation TODO

> The filename is intentionally `TOOD.md` to match the requested repository path. This document is the authoritative implementation checklist for the requirements in [`SPEC.md`](./SPEC.md).

## 1. Execution rules

The implementation must follow these rules throughout the project:

- Implement tasks in dependency order unless a task explicitly says it may be parallelized.
- Do not silently weaken a requirement because an `nmcli` operation is difficult to model.
- Do not add direct `wpa_supplicant`, networking-file, ConnMan, or root-execution fallbacks.
- Do not catch broad exceptions and continue with empty or default state.
- Do not report a mutating operation as successful until refreshed backend state verifies it.
- Do not log passwords or unredacted credential-bearing command arguments.
- Keep TUI, application logic, backend parsing, and subprocess execution separated.
- Add or update tests with every functional task.
- A task is complete only when its code, tests, error handling, and documentation are complete.
- Preserve the last valid state snapshot when a refresh fails.
- Any deviation from `SPEC.md` must be documented and approved before implementation.

## 2. Definition of done

A task or subtask is done only when:

- The behavior is implemented.
- Public and internal interfaces are type annotated.
- Relevant unit tests exist and pass.
- Negative and failure paths are tested.
- Sensitive values are redacted.
- User-visible failures are specific and actionable.
- Ruff formatting and linting pass.
- Static type checking passes.
- No unrelated regressions are introduced.
- Documentation is updated where behavior or setup changed.

## 3. Phase 0 — Repository foundation

### 0.1 Confirm project metadata

- [ ] Confirm the project name is `tui-wifi`.
- [ ] Confirm the installed console command will be `wifi-tui`.
- [ ] Confirm the Python import package will be `tui_wifi`.
- [ ] Confirm Python 3.11 is the minimum supported version.
- [ ] Confirm Textual is the TUI framework.
- [ ] Confirm NetworkManager through `nmcli` is the only version 0.1 backend.
- [ ] Confirm the default branch remains `master` unless deliberately changed by the repository owner.

### 0.2 Add repository-level files

Create and populate:

- [ ] `README.md`
- [ ] `LICENSE`
- [ ] `.gitignore`
- [ ] `.editorconfig`
- [ ] `pyproject.toml`
- [ ] `CHANGELOG.md`
- [ ] `CONTRIBUTING.md`

The README must initially include:

- [ ] Product summary.
- [ ] Current development status.
- [ ] Supported platform requirements.
- [ ] Explicit version 0.1 limitations.
- [ ] Development environment setup.
- [ ] Test, lint, formatting, and type-check commands.
- [ ] Warning that the project is not yet production-ready until the acceptance checklist passes.

### 0.3 Configure Python project tooling

- [ ] Use a `src/` layout.
- [ ] Configure the `wifi-tui` console entry point.
- [ ] Add runtime dependencies with bounded compatible versions.
- [ ] Add development dependencies for tests, linting, formatting, and typing.
- [ ] Configure Ruff linting.
- [ ] Configure Ruff formatting.
- [ ] Configure pytest.
- [ ] Configure static type checking with Mypy or Pyright.
- [ ] Configure coverage reporting.
- [ ] Decide and document the dependency lock workflow.
- [ ] Ensure build metadata produces a valid wheel and source distribution.

### 0.4 Create initial directory structure

Create:

```text
src/tui_wifi/
src/tui_wifi/backends/
src/tui_wifi/process/
src/tui_wifi/services/
src/tui_wifi/ui/
src/tui_wifi/ui/screens/
src/tui_wifi/ui/dialogs/
src/tui_wifi/ui/widgets/
tests/unit/
tests/integration/
tests/tui/
tests/fixtures/nmcli/
tests/manual/
```

Create package initializers only where appropriate for the selected packaging strategy.

### 0.5 Add initial application entry points

Create:

- [ ] `src/tui_wifi/__init__.py`
- [ ] `src/tui_wifi/__main__.py`
- [ ] `src/tui_wifi/cli.py`
- [ ] `src/tui_wifi/app.py`

Initial behavior:

- [ ] `python -m tui_wifi --version` works.
- [ ] `wifi-tui --version` works after installation.
- [ ] Starting the command launches a minimal Textual application.
- [ ] Startup exceptions produce a nonzero process exit.
- [ ] No networking behavior is implemented in this phase.

### 0.6 Add continuous integration

- [ ] Add a GitHub Actions workflow.
- [ ] Test supported Python versions.
- [ ] Run unit and integration tests.
- [ ] Run Ruff formatting check.
- [ ] Run Ruff lint.
- [ ] Run static type checking.
- [ ] Build wheel and source distribution.
- [ ] Ensure CI does not access or modify the runner's real Wi-Fi state.

### Phase 0 checkpoint

- [ ] Clean clone setup is documented and reproducible.
- [ ] The empty Textual app starts.
- [ ] Tests, lint, format, type checking, build, and CI pass.

## 4. Phase 1 — Domain model and error contract

### 1.1 Define stable enums and value objects

Create domain types for:

- [ ] Backend availability.
- [ ] NetworkManager general state.
- [ ] Wi-Fi radio state.
- [ ] Device state.
- [ ] Connection operation state.
- [ ] Security class.
- [ ] Error category.
- [ ] Signal quality representation.

Requirements:

- [ ] Domain enums must not expose raw localized `nmcli` strings to the UI.
- [ ] Unknown values must be represented explicitly.
- [ ] Unknown values must not be silently mapped to healthy or disconnected states.

### 1.2 Define core models

Create typed models equivalent to:

- [ ] `WiFiDevice`
- [ ] `AccessPoint`
- [ ] `NetworkGroup`
- [ ] `SavedProfile`
- [ ] `ActiveWiFiConnection`
- [ ] `IPConfiguration`
- [ ] `BackendStatus`
- [ ] `OperationStatus`
- [ ] `ApplicationSnapshot`

Model requirements:

- [ ] Prefer immutable models where practical.
- [ ] Separate raw identifiers from display text.
- [ ] Preserve SSID bytes or an unambiguous backend representation when possible.
- [ ] Do not use a blank SSID as a normal visible-network identity.
- [ ] Store BSSID separately from SSID.
- [ ] Make optional and unavailable values explicit.

### 1.3 Define structured errors

Create a base application/backend error model containing:

- [ ] Stable category.
- [ ] User-facing summary.
- [ ] Optional user guidance.
- [ ] Redacted technical details.
- [ ] Exit code where applicable.
- [ ] Backend reason code where applicable.
- [ ] Retriable flag.
- [ ] Operation context.

Required categories:

- [ ] Missing `nmcli`.
- [ ] NetworkManager unavailable.
- [ ] No adapter.
- [ ] Unmanaged adapter.
- [ ] Wi-Fi disabled.
- [ ] Radio blocked.
- [ ] Authorization denied.
- [ ] Authentication rejected.
- [ ] Missing secrets.
- [ ] Network unavailable.
- [ ] Unsupported security.
- [ ] DHCP or IP configuration failure.
- [ ] Timeout.
- [ ] Cancelled.
- [ ] Parse failure.
- [ ] Command failure.
- [ ] State verification failure.
- [ ] Unexpected internal failure.

### 1.4 Implement error-to-message mapping

- [ ] Map every stable error category to a friendly default message.
- [ ] Allow backend details to refine the message without replacing the stable category.
- [ ] Keep raw stderr in redacted technical details only.
- [ ] Ensure raw messages are never the sole user-facing explanation.
- [ ] Add tests for all mappings.

### 1.5 Implement secret wrapper and redaction policy

- [ ] Create a narrow representation for sensitive values.
- [ ] Ensure its string and representation methods never reveal the value.
- [ ] Implement structured command redaction.
- [ ] Implement technical-detail redaction.
- [ ] Redact passwords regardless of whether the command succeeds, fails, times out, or is cancelled.
- [ ] Add tests that deliberately trigger exceptions and assert the secret is absent from all output.

### Phase 1 checkpoint

- [ ] Domain models and errors are backend-independent.
- [ ] All models and error mappings have unit tests.
- [ ] Secret values cannot appear through normal string formatting or diagnostics.

## 5. Phase 2 — Safe asynchronous process execution

### 2.1 Define process-runner interface

Create an asynchronous process runner that accepts:

- [ ] Executable and argument array.
- [ ] Environment overrides.
- [ ] Timeout.
- [ ] Optional stdin input.
- [ ] Sensitive argument indexes or redaction metadata.
- [ ] Cancellation signal or task cancellation.

Return a structured result containing:

- [ ] Redacted command description.
- [ ] Exit code.
- [ ] stdout.
- [ ] stderr.
- [ ] Duration.
- [ ] Timeout status.
- [ ] Cancellation status.

### 2.2 Enforce subprocess safety

- [ ] Never use `shell=True`.
- [ ] Never concatenate user-supplied values into a shell command.
- [ ] Use argument arrays only.
- [ ] Set a predictable locale for parseable commands.
- [ ] Bound every subprocess call with a timeout.
- [ ] Terminate and reap timed-out child processes.
- [ ] Distinguish timeout from user cancellation.
- [ ] Preserve stdout and stderr separately.
- [ ] Do not silently ignore a nonzero exit code.

### 2.3 Define process-level exceptions

- [ ] Executable not found.
- [ ] Timeout.
- [ ] Cancellation.
- [ ] Spawn failure.
- [ ] Nonzero exit.
- [ ] Decode failure if non-text output is unexpectedly returned.

### 2.4 Add fake process runner

- [ ] Queue expected commands and deterministic results.
- [ ] Fail tests on unexpected command arguments.
- [ ] Support delayed responses.
- [ ] Support timeout and cancellation scenarios.
- [ ] Record only redacted invocation metadata.

### 2.5 Test process runner

Test:

- [ ] Successful command.
- [ ] stdout and stderr separation.
- [ ] Nonzero exit.
- [ ] Missing executable.
- [ ] Timeout.
- [ ] Cancellation.
- [ ] Values containing spaces, colons, quotes, and shell metacharacters.
- [ ] Password redaction in success and failure objects.
- [ ] Child-process cleanup.

### Phase 2 checkpoint

- [ ] All system commands can be executed without blocking the TUI.
- [ ] Process failures are structured and fully tested.
- [ ] No secrets appear in recorded command metadata.

## 6. Phase 3 — Backend abstraction

### 3.1 Define backend protocol or abstract base class

Create operations for:

- [ ] `check_status`
- [ ] `get_wifi_radio_state`
- [ ] `set_wifi_radio_state`
- [ ] `list_wifi_devices`
- [ ] `request_scan`
- [ ] `list_access_points`
- [ ] `get_active_wifi_connection`
- [ ] `list_saved_wifi_profiles`
- [ ] `activate_saved_profile`
- [ ] `connect_visible_network`
- [ ] `connect_hidden_network`
- [ ] `disconnect`
- [ ] `delete_saved_profile`
- [ ] `set_profile_autoconnect`
- [ ] `get_connection_details`

### 3.2 Define operation inputs

Create typed request models for:

- [ ] Visible-network connection.
- [ ] Hidden-network connection.
- [ ] Saved-profile activation.
- [ ] Disconnection.
- [ ] Profile deletion.
- [ ] Auto-connect update.
- [ ] Radio-state update.

Inputs must distinguish:

- [ ] SSID from BSSID.
- [ ] Profile name from UUID.
- [ ] Interface name from connection identifier.
- [ ] Open network from secured network.
- [ ] Missing password from empty password.

### 3.3 Add fake backend

The fake backend must support:

- [ ] Initial snapshots.
- [ ] Controlled state mutation.
- [ ] Delayed operations.
- [ ] Expected operation assertions.
- [ ] Failure injection.
- [ ] Mid-operation network disappearance.
- [ ] Backend restart simulation.
- [ ] State verification mismatch simulation.

### 3.4 Add backend contract tests

Run the same behavioral contract against the fake backend and later against the `nmcli` adapter where feasible.

Contract assertions:

- [ ] No raw command strings escape the backend.
- [ ] Unsupported security is rejected before connection.
- [ ] Deleting one profile does not delete unrelated profiles sharing an SSID.
- [ ] Successful mutation returns or permits verification of resulting state.
- [ ] Cancellation has a distinct result.
- [ ] Errors use stable categories.

### Phase 3 checkpoint

- [ ] Application and TUI code can be developed against the fake backend.
- [ ] No UI module imports the concrete `nmcli` adapter.

## 7. Phase 4 — `nmcli` parsing foundation

### 4.1 Establish output format strategy

For every query command:

- [ ] Select explicit fields.
- [ ] Use terse machine-readable output where appropriate.
- [ ] Decide whether escaping is enabled or disabled per command.
- [ ] Document the delimiter and escaping rules.
- [ ] Set locale to a stable value.
- [ ] Capture representative fixture outputs from supported NetworkManager versions.

### 4.2 Implement escaped-field parser

- [ ] Parse escaped separators correctly.
- [ ] Parse escaped backslashes correctly.
- [ ] Preserve empty fields.
- [ ] Detect dangling or malformed escape sequences.
- [ ] Reject unexpected field counts with a parse error.
- [ ] Never translate malformed output into an empty result.

Test fixtures must include:

- [ ] SSID containing a colon.
- [ ] SSID containing a backslash.
- [ ] Profile name containing a colon.
- [ ] Empty optional fields.
- [ ] Non-ASCII SSID text.
- [ ] Hidden or blank SSID.
- [ ] Malformed lines.

### 4.3 Implement scalar parsers

- [ ] Boolean values.
- [ ] Integer signal values with range validation.
- [ ] Frequency.
- [ ] Channel where supplied or derived.
- [ ] UUID.
- [ ] IPv4 and IPv6 addresses.
- [ ] DNS lists.
- [ ] Device and connection states.

### 4.4 Implement security parser

- [ ] Parse access-point security capability fields.
- [ ] Normalize open networks.
- [ ] Detect WEP and mark unsupported.
- [ ] Detect WPA personal.
- [ ] Detect WPA2 personal.
- [ ] Detect WPA3 personal.
- [ ] Detect mixed personal modes.
- [ ] Detect enterprise modes and mark unsupported.
- [ ] Treat unknown combinations conservatively.
- [ ] Add fixture-driven tests for every class.

### Phase 4 checkpoint

- [ ] Parser behavior is completely independent of live Wi-Fi hardware.
- [ ] Malformed output always produces a visible parse failure.
- [ ] Escaped and unusual SSIDs are covered by tests.

## 8. Phase 5 — NetworkManager `nmcli` adapter: read operations

### 5.1 Backend availability checks

Implement and test:

- [ ] Find `nmcli` in `PATH`.
- [ ] Read `nmcli` and NetworkManager version information.
- [ ] Detect NetworkManager unavailable state.
- [ ] Detect permission or D-Bus access failures.
- [ ] Return structured backend status.

Do not infer that NetworkManager is healthy merely because the `nmcli` executable exists.

### 5.2 Read general networking and radio state

- [ ] Read NetworkManager general state.
- [ ] Read Wi-Fi radio enabled state.
- [ ] Distinguish disabled from unavailable.
- [ ] Capture hardware-enabled state where available.
- [ ] Preserve unknown state explicitly.

### 5.3 List Wi-Fi devices

- [ ] Query explicit device fields.
- [ ] Include interface, type, state, connection, managed state, and relevant identifiers.
- [ ] Filter to Wi-Fi devices only after parsing.
- [ ] Distinguish no device from parser or command failure.
- [ ] Identify active Wi-Fi device.
- [ ] Add multi-adapter fixtures and tests.

### 5.4 Request scans

- [ ] Request a scan for a selected device.
- [ ] Use a bounded timeout.
- [ ] Classify rate-limited, unavailable, disabled, blocked, and authorization failures.
- [ ] Do not treat a successful scan request as proof that results changed.

### 5.5 List access points

- [ ] Query explicit fields including device, active state, SSID, BSSID, signal, frequency, and security.
- [ ] Parse every row strictly.
- [ ] Retain individual BSSIDs.
- [ ] Exclude blank SSIDs from normal visible entries.
- [ ] Mark unsupported security modes.
- [ ] Preserve active AP identity.
- [ ] Add fixtures for duplicate SSIDs and mixed security.

### 5.6 List saved Wi-Fi profiles

- [ ] Query explicit profile fields.
- [ ] Select Wi-Fi profiles without depending on translated display text.
- [ ] Read profile UUID, name, type, interface binding, auto-connect, and SSID.
- [ ] Read security type using additional profile queries if necessary.
- [ ] Avoid an unbounded subprocess-per-profile implementation; define and test a bounded strategy.
- [ ] Preserve profiles with duplicate names or duplicate SSIDs as distinct UUIDs.

### 5.7 Read active connection details

- [ ] Identify the active Wi-Fi profile and device.
- [ ] Read SSID and BSSID.
- [ ] Read IPv4 addresses.
- [ ] Read IPv6 addresses.
- [ ] Read gateway.
- [ ] Read DNS servers.
- [ ] Preserve partial details without claiming the whole connection is healthy.
- [ ] Distinguish no active Wi-Fi connection from command failure.

### 5.8 Test read operations

- [ ] Use fake process runner for exact command assertions.
- [ ] Use recorded fixture outputs.
- [ ] Test older and newer NetworkManager output variants where available.
- [ ] Test malformed output.
- [ ] Test nonzero exits.
- [ ] Test timeout.
- [ ] Test missing fields.
- [ ] Test multi-adapter state.

### Phase 5 checkpoint

- [ ] A complete read-only application snapshot can be built from `nmcli`.
- [ ] Every command and parser has fixture-driven tests.
- [ ] Read failures do not appear as valid empty state.

## 9. Phase 6 — Network grouping and selection policy

### 6.1 Group access points for display

- [ ] Group compatible APs by SSID and security class.
- [ ] Do not group open and secured networks together merely because SSIDs match.
- [ ] Do not group incompatible personal and enterprise modes.
- [ ] Retain all member BSSIDs.
- [ ] Select strongest signal for display.
- [ ] Mark group connected when the active BSSID belongs to it.

### 6.2 Associate saved profiles

- [ ] Match profiles conservatively by SSID and compatible security.
- [ ] Preserve all matching profile UUIDs.
- [ ] Define deterministic preference when multiple profiles are usable.
- [ ] Prefer the active profile when connected.
- [ ] Do not silently choose an interface-restricted profile for a different adapter.
- [ ] Surface ambiguity to the application service when a safe deterministic choice is unavailable.

### 6.3 Implement sorting

Sort by:

1. Connected network.
2. Saved supported networks in range.
3. Other supported networks.
4. Unsupported networks.
5. Descending signal within each class.
6. Stable display-name ordering as final tie-breaker.

### 6.4 Test grouping policy

- [ ] Same SSID, multiple BSSIDs.
- [ ] Same SSID, open and WPA2.
- [ ] Same SSID, WPA2 and enterprise.
- [ ] Multiple saved profiles.
- [ ] Active weak AP and stronger inactive AP.
- [ ] Hidden SSIDs.
- [ ] Invalid display text.

### Phase 6 checkpoint

- [ ] The UI can consume a stable list of user-facing network groups.
- [ ] No unsafe or ambiguous security downgrade occurs during grouping.

## 10. Phase 7 — `nmcli` adapter: mutating operations

### 7.1 Set Wi-Fi radio state

- [ ] Enable Wi-Fi through NetworkManager.
- [ ] Disable Wi-Fi through NetworkManager.
- [ ] Verify resulting radio state.
- [ ] Distinguish software-disabled from hardware-blocked state.
- [ ] Classify authorization failure.
- [ ] Test state verification mismatch.

### 7.2 Activate saved profile

- [ ] Activate by profile UUID, not ambiguous display name.
- [ ] Restrict to the selected device where appropriate.
- [ ] Use a bounded timeout.
- [ ] Refresh and verify active profile UUID and device.
- [ ] Classify rejected or missing stored secrets.
- [ ] Do not repeatedly retry without user action.

### 7.3 Connect to a visible open network

- [ ] Use selected SSID and optional BSSID/device constraints.
- [ ] Do not provide empty or guessed password fields.
- [ ] Respect auto-connect preference.
- [ ] Verify active state after command completion.
- [ ] Create or identify the resulting profile deterministically.

### 7.4 Connect to a visible personal secured network

- [ ] Validate supported security before execution.
- [ ] Require a nonempty password unless activating a saved profile.
- [ ] Pass the password using the safest practical `nmcli` mechanism selected during implementation.
- [ ] Mark password material as sensitive in the process runner.
- [ ] Apply auto-connect preference to the resulting profile.
- [ ] Verify active profile, device, and connection state.
- [ ] Ensure password never appears in logs or errors.

### 7.5 Connect to hidden network

- [ ] Validate nonempty SSID.
- [ ] Validate security class.
- [ ] Support open hidden networks.
- [ ] Support personal secured hidden networks.
- [ ] Reject enterprise, WEP, and unknown security.
- [ ] Apply auto-connect preference.
- [ ] Verify resulting state.

### 7.6 Disconnect

- [ ] Disconnect the selected active Wi-Fi device or connection deterministically.
- [ ] Do not disconnect unrelated devices.
- [ ] Refresh and verify the target connection is inactive.
- [ ] Preserve prior state and show an error if verification fails.

### 7.7 Delete saved profile

- [ ] Delete strictly by UUID.
- [ ] Never delete all profiles sharing an SSID by default.
- [ ] Verify that the selected UUID is absent afterward.
- [ ] Preserve other profiles with the same name or SSID.
- [ ] Classify authorization and not-found failures.

### 7.8 Change auto-connect

- [ ] Modify strictly by UUID.
- [ ] Verify the updated profile value.
- [ ] Distinguish command success from verification success.

### 7.9 Map mutation errors

Use command exit information, stderr, device state, active connection state, and NetworkManager reason codes where available to classify:

- [ ] Wrong password.
- [ ] Missing secret.
- [ ] No network in range.
- [ ] Association failure.
- [ ] DHCP/IP failure.
- [ ] Authorization failure.
- [ ] Wi-Fi disabled.
- [ ] Radio blocked.
- [ ] Timeout.
- [ ] User cancellation.
- [ ] Unknown backend failure.

Do not claim a more specific cause than the available evidence supports.

### 7.10 Test all mutations with fake process runner

For every operation, test:

- [ ] Exact arguments.
- [ ] Success and state verification.
- [ ] Command failure.
- [ ] Timeout.
- [ ] Cancellation.
- [ ] Verification mismatch.
- [ ] Secret redaction.
- [ ] Duplicate profile handling.
- [ ] Multi-adapter isolation.

### Phase 7 checkpoint

- [ ] The backend supports the complete version 0.1 operation set.
- [ ] All successful mutations are state-verified.
- [ ] All failures are structured and visible.

## 11. Phase 8 — Application service and coherent state

### 8.1 Implement application service

Responsibilities:

- [ ] Own the selected adapter.
- [ ] Build coherent snapshots.
- [ ] Orchestrate refreshes.
- [ ] Group access points.
- [ ] Associate saved profiles.
- [ ] Serialize mutating operations.
- [ ] Publish operation progress.
- [ ] Preserve last valid data on refresh failure.
- [ ] Expose backend-independent methods to the TUI.

### 8.2 Implement startup orchestration

- [ ] Check platform.
- [ ] Check backend status.
- [ ] Read radio state.
- [ ] Discover devices.
- [ ] Select adapter.
- [ ] Read current connection.
- [ ] Request scan when valid.
- [ ] Read APs and profiles.
- [ ] Publish initial snapshot.

A failure in one optional detail query must not erase otherwise valid state. A failure in a required query must be visible.

### 8.3 Implement adapter selection policy

- [ ] Honor explicit `--interface` selection.
- [ ] Prefer active Wi-Fi device when no interface is specified.
- [ ] Otherwise prefer the only managed usable Wi-Fi device.
- [ ] If multiple viable devices remain, require a user selection in the UI.
- [ ] Never silently move an active operation to another adapter.

### 8.4 Implement refresh generations

- [ ] Assign generation identifiers to refreshes.
- [ ] Discard stale results explicitly.
- [ ] Prevent a slow old scan from overwriting a newer connection state.
- [ ] Test overlapping refreshes.

### 8.5 Implement mutation ownership

- [ ] Permit one mutating operation per selected device at a time.
- [ ] Reject or queue duplicate connect operations deliberately.
- [ ] Disable conflicting UI actions while mutation is active.
- [ ] Expose cancellation where safe.
- [ ] Refresh state after every mutation, including failed or cancelled operations where state may have changed.

### 8.6 Implement connection workflow policy

- [ ] Prefer compatible saved profile when deterministic.
- [ ] Ask UI for credentials when no usable saved secret exists.
- [ ] Do not automatically delete or replace a failed saved profile.
- [ ] Do not downgrade security.
- [ ] Do not retry indefinitely.
- [ ] Return a clear next action after authentication rejection.

### 8.7 Implement resilient snapshot publication

- [ ] Publish complete snapshots atomically.
- [ ] Preserve last-known network list if rescan fails.
- [ ] Attach a warning or error to the preserved snapshot.
- [ ] Mark stale data visibly when appropriate.
- [ ] Never replace valid data with empty defaults due to an exception.

### 8.8 Add service tests

Test:

- [ ] Initial startup success.
- [ ] No backend.
- [ ] No adapter.
- [ ] Wi-Fi disabled.
- [ ] Multiple adapters.
- [ ] Refresh failure with preserved state.
- [ ] Overlapping refreshes.
- [ ] Connect success.
- [ ] Connect failure.
- [ ] Stale operation result.
- [ ] Cancellation.
- [ ] Backend restart.

### Phase 8 checkpoint

- [ ] A headless service test can execute every user workflow using the fake backend.
- [ ] State remains coherent across failures and concurrent refreshes.

## 12. Phase 9 — TUI shell and main screen

### 9.1 Establish Textual application structure

Create clear modules for:

- [ ] Application class.
- [ ] Main screen.
- [ ] Reusable network-list widget.
- [ ] Status/header widget.
- [ ] Details panel.
- [ ] Footer/help bindings.
- [ ] Notification and error presentation.

### 9.2 Implement startup and loading states

Display distinct states for:

- [ ] Checking NetworkManager.
- [ ] Discovering adapters.
- [ ] Scanning.
- [ ] Loading saved profiles.
- [ ] Ready.

The TUI must remain responsive during all startup operations.

### 9.3 Implement main network list

Each row must provide:

- [ ] Connected marker.
- [ ] SSID.
- [ ] Signal representation.
- [ ] Security marker.
- [ ] Saved marker where useful.
- [ ] Unsupported marker.

Requirements:

- [ ] Support keyboard selection.
- [ ] Support mouse selection where available.
- [ ] Preserve selected network across refresh when identity still exists.
- [ ] Choose a sensible selection when the selected network disappears.
- [ ] Do not render hidden blank SSIDs as ordinary rows.

### 9.4 Implement responsive layout

- [ ] Full layout for normal terminal widths.
- [ ] Compact layout for narrow terminals.
- [ ] Vertical scrolling for short terminals.
- [ ] No critical control may become permanently inaccessible after resize.
- [ ] Test resize behavior.

### 9.5 Implement main actions

- [ ] Connect or open selected network.
- [ ] Disconnect active connection.
- [ ] Refresh.
- [ ] Open details.
- [ ] Open hidden-network dialog.
- [ ] Open saved-networks screen.
- [ ] Toggle Wi-Fi.
- [ ] Quit.

### 9.6 Implement empty and unavailable states

Create dedicated UI for:

- [ ] No `nmcli`.
- [ ] NetworkManager unavailable.
- [ ] No Wi-Fi adapter.
- [ ] Adapter unmanaged.
- [ ] Wi-Fi disabled.
- [ ] Hardware or software block.
- [ ] No networks found.
- [ ] Scan failed while old data remains visible.

### 9.7 Add main-screen pilot tests

- [ ] Keyboard navigation.
- [ ] Mouse selection where Textual testing supports it.
- [ ] Refresh binding.
- [ ] Preserved selection.
- [ ] Empty states.
- [ ] Narrow terminal.
- [ ] Unsupported network rendering.
- [ ] Color-independent markers.

### Phase 9 checkpoint

- [ ] The user can inspect nearby networks and current connection state through a stable TUI.
- [ ] No connection mutation is required yet to validate this phase.

## 13. Phase 10 — Connection dialogs and progress

### 10.1 Secured-network password dialog

Include:

- [ ] SSID display.
- [ ] Obscured password field.
- [ ] Show-password toggle.
- [ ] Auto-connect checkbox enabled by default.
- [ ] Connect button.
- [ ] Cancel button.

Validation:

- [ ] Reject empty password for a new secured network.
- [ ] Do not trim or modify password text unexpectedly.
- [ ] Clear sensitive widget state when dialog closes.
- [ ] Do not include password in Textual messages, logs, snapshots, or test snapshots.

### 10.2 Open-network confirmation

- [ ] Clearly identify the network as open.
- [ ] Permit connection or cancellation.
- [ ] Do not imply encryption or privacy.

### 10.3 Saved-profile activation behavior

- [ ] Activate directly when a deterministic saved profile exists.
- [ ] Show progress.
- [ ] On missing or rejected secrets, offer retry with password.
- [ ] Do not hide that the saved profile failed.

### 10.4 Unsupported-network dialog

- [ ] Explain that the security method is unsupported.
- [ ] Show detected class when safe and useful.
- [ ] Do not offer an unsafe attempt button.

### 10.5 Connection progress dialog or panel

- [ ] Display target SSID.
- [ ] Display current friendly stage.
- [ ] Keep TUI responsive.
- [ ] Disable duplicate connect action.
- [ ] Allow cancellation where supported.
- [ ] Distinguish cancel from failure.

### 10.6 Success behavior

- [ ] Close progress UI.
- [ ] Refresh state.
- [ ] Confirm active connection.
- [ ] Show success notification.
- [ ] Display IP address when available.

### 10.7 Failure dialog

- [ ] Friendly summary.
- [ ] Suggested next action when available.
- [ ] Retry button only when retry is meaningful.
- [ ] Cancel or close button.
- [ ] Expandable redacted technical details.
- [ ] Preserve the last valid network list behind the dialog.

### 10.8 Add connection-flow pilot tests

- [ ] New secured network success.
- [ ] Password visibility toggle.
- [ ] Password rejection and retry.
- [ ] Open network.
- [ ] Saved profile success.
- [ ] Saved profile missing secret.
- [ ] Network disappears.
- [ ] DHCP failure.
- [ ] Timeout.
- [ ] Cancellation.
- [ ] Unsupported security.
- [ ] Secret absent from captured test output.

### Phase 10 checkpoint

- [ ] A user can connect to supported visible networks entirely through the TUI.
- [ ] Failure causes are visible and credentials remain protected.

## 14. Phase 11 — Disconnect, Wi-Fi toggle, saved networks, hidden networks

### 11.1 Disconnect workflow

- [ ] Show disconnect action only when meaningful.
- [ ] Identify the active network.
- [ ] Execute through application service.
- [ ] Show progress.
- [ ] Verify state after completion.
- [ ] Show visible error on failure.

### 11.2 Wi-Fi toggle workflow

- [ ] Show current radio state.
- [ ] Confirm before disabling an active connection.
- [ ] Enable through NetworkManager.
- [ ] Disable through NetworkManager.
- [ ] Refresh and verify.
- [ ] Distinguish hardware block from software state.

### 11.3 Saved-networks screen

Display:

- [ ] Profile display name.
- [ ] SSID.
- [ ] Auto-connect state.
- [ ] Active state.
- [ ] Interface restriction where relevant.

Actions:

- [ ] Connect.
- [ ] Forget.
- [ ] Toggle auto-connect.
- [ ] View details.
- [ ] Return.

### 11.4 Forget confirmation

- [ ] Identify exact profile name and UUID context where helpful.
- [ ] Delete one UUID only.
- [ ] Require explicit confirmation.
- [ ] Verify deletion.
- [ ] Keep unrelated same-SSID profiles.

### 11.5 Hidden-network dialog

Fields:

- [ ] SSID.
- [ ] Security type.
- [ ] Password when required.
- [ ] Show-password toggle.
- [ ] Auto-connect.

Validation:

- [ ] Reject blank SSID.
- [ ] Reject unsupported security.
- [ ] Require password for secured personal mode.
- [ ] Clear secrets after completion or cancellation.

### 11.6 Add workflow pilot tests

- [ ] Disconnect success and failure.
- [ ] Disable with active connection confirmation.
- [ ] Enable Wi-Fi.
- [ ] Hardware block.
- [ ] Saved-profile activation.
- [ ] Auto-connect update.
- [ ] Forget one duplicate profile.
- [ ] Hidden open network.
- [ ] Hidden secured network.
- [ ] Hidden-network validation errors.

### Phase 11 checkpoint

- [ ] Every version 0.1 user-facing mutation is available through the TUI.

## 15. Phase 12 — Details, diagnostics, and CLI behavior

### 12.1 Connection details view

Show available values for:

- [ ] Interface.
- [ ] Device state.
- [ ] SSID.
- [ ] BSSID.
- [ ] Signal.
- [ ] Security.
- [ ] IPv4.
- [ ] IPv6.
- [ ] Gateway.
- [ ] DNS.
- [ ] Profile name.
- [ ] UUID.

- [ ] Clearly mark unavailable values.
- [ ] Never display secrets.

### 12.2 Technical error details

- [ ] Make details expandable rather than default.
- [ ] Include operation name, stable category, exit code, reason code, and redacted stderr where available.
- [ ] Avoid displaying raw tracebacks in normal mode.
- [ ] Ensure diagnostic details remain useful without secrets.

### 12.3 CLI options

Implement:

- [ ] `--version`
- [ ] `--debug`
- [ ] `--interface <name>`
- [ ] `--no-mouse` if the final Textual integration needs it
- [ ] `--help`

Behavior:

- [ ] Unknown option returns nonzero.
- [ ] Requested unavailable interface returns a clear error.
- [ ] Debug mode does not weaken secret redaction.

### 12.4 Debug logging

- [ ] Use XDG state or cache directory conventions.
- [ ] Include version and timing metadata.
- [ ] Include redacted backend command descriptions.
- [ ] Include operation and state transitions.
- [ ] Rotate or bound logs.
- [ ] Handle unwritable log directory without crashing the networking UI.
- [ ] Show a visible warning if requested debug logging cannot be enabled.

### 12.5 Add tests

- [ ] Details rendering.
- [ ] Missing detail values.
- [ ] CLI parsing.
- [ ] Invalid interface.
- [ ] Debug logging redaction.
- [ ] Unwritable debug path.

### Phase 12 checkpoint

- [ ] Normal users receive simple messages and troubleshooters can retrieve redacted technical information.

## 16. Phase 13 — Robustness and lifecycle hardening

### 13.1 Application shutdown

- [ ] Cancel outstanding scans and refreshes.
- [ ] Decide and document behavior for an active connection operation.
- [ ] Reap child processes.
- [ ] Clear ephemeral secret state.
- [ ] Exit with an appropriate status.

### 13.2 NetworkManager restart handling

- [ ] Detect backend loss during runtime.
- [ ] Preserve last valid snapshot with a stale/offline indication.
- [ ] Disable invalid mutations.
- [ ] Retry status checks only with bounded backoff.
- [ ] Recover cleanly when NetworkManager returns.
- [ ] Do not spin in a tight retry loop.

### 13.3 Adapter removal and insertion

- [ ] Handle selected adapter removal.
- [ ] Cancel or fail owned operations explicitly.
- [ ] Prompt selection when another adapter exists.
- [ ] Detect a newly inserted adapter on refresh.

### 13.4 Terminal lifecycle

- [ ] Handle terminal resize.
- [ ] Handle suspend/resume where practical.
- [ ] Restore terminal state after controlled exceptions.
- [ ] Avoid leaving cursor or alternate-screen state corrupted.

### 13.5 Operation timeout policy

Define explicit defaults for:

- [ ] Status query.
- [ ] Device/profile query.
- [ ] Scan request.
- [ ] Connect.
- [ ] Disconnect.
- [ ] Radio toggle.
- [ ] Profile modification.

- [ ] Document why each timeout is reasonable.
- [ ] Make retry decisions explicit.
- [ ] Never retry a password automatically after rejection.

### 13.6 Exception boundaries

- [ ] Add narrow exception boundaries at process, backend, service, and UI layers.
- [ ] Convert known exceptions to structured errors.
- [ ] Record unexpected exceptions with redaction.
- [ ] Keep unexpected errors visible.
- [ ] Do not continue a mutation after an invariant violation.

### 13.7 Add robustness tests

- [ ] Quit during scan.
- [ ] Quit during connect.
- [ ] Backend disappears during refresh.
- [ ] Backend disappears during connect.
- [ ] Adapter disappears.
- [ ] Overlapping user actions.
- [ ] Slow stale refresh.
- [ ] Terminal resize during modal dialog.
- [ ] Unexpected parser exception.
- [ ] Unexpected service exception.

### Phase 13 checkpoint

- [ ] Runtime disruptions do not produce silent state corruption or leaked child processes.

## 17. Phase 14 — Packaging, installation, and documentation

### 14.1 Complete README

Add:

- [ ] Screenshots or terminal captures without real private network identifiers.
- [ ] Installation from source.
- [ ] Installation with `pipx`.
- [ ] Development setup.
- [ ] Basic usage.
- [ ] Keyboard shortcuts.
- [ ] Supported security modes.
- [ ] Unsupported features.
- [ ] NetworkManager requirement.
- [ ] Polkit and authorization behavior.
- [ ] Troubleshooting.
- [ ] Privacy and credential handling.

### 14.2 Add troubleshooting guide

Create `docs/TROUBLESHOOTING.md` covering:

- [ ] `nmcli` missing.
- [ ] NetworkManager stopped.
- [ ] No adapter found.
- [ ] Device unmanaged.
- [ ] Wi-Fi disabled.
- [ ] `rfkill` block.
- [ ] Authorization denied.
- [ ] Incorrect password.
- [ ] DHCP failure.
- [ ] Captive portals.
- [ ] Enterprise Wi-Fi limitation.
- [ ] Collecting redacted debug logs.

### 14.3 Add architecture document

Create `docs/ARCHITECTURE.md` covering:

- [ ] Layer boundaries.
- [ ] Domain models.
- [ ] Backend contract.
- [ ] Process safety.
- [ ] State snapshot model.
- [ ] Concurrency and generation handling.
- [ ] Credential lifecycle.
- [ ] Error classification.
- [ ] Rationale for `nmcli` first and D-Bus later.

### 14.4 Add security document

Create `docs/SECURITY.md` covering:

- [ ] Threat model.
- [ ] Password handling.
- [ ] Logging redaction.
- [ ] Privilege model.
- [ ] No-root-TUI requirement.
- [ ] No-shell requirement.
- [ ] Unsupported fallback policy.
- [ ] Vulnerability reporting.

### 14.5 Build and install validation

- [ ] Build wheel.
- [ ] Build source distribution.
- [ ] Install wheel in a clean virtual environment.
- [ ] Verify `wifi-tui --version`.
- [ ] Verify TUI launch.
- [ ] Verify package contains required non-code assets.
- [ ] Verify no test fixtures or secrets are accidentally packaged.

### Phase 14 checkpoint

- [ ] A new user can install, launch, operate, and troubleshoot the project from repository documentation.

## 18. Phase 15 — Automated acceptance test completion

### 15.1 Unit coverage completion

Ensure complete coverage for:

- [ ] Parsers.
- [ ] Security classification.
- [ ] Grouping.
- [ ] Sorting.
- [ ] Models.
- [ ] Error mapping.
- [ ] Redaction.
- [ ] Application state transitions.
- [ ] Operation serialization.
- [ ] Refresh generations.

### 15.2 Fake-backend workflow suite

Automate end-to-end service/TUI scenarios:

- [ ] Normal startup.
- [ ] No adapter.
- [ ] Wi-Fi disabled.
- [ ] Empty scan.
- [ ] Open network success.
- [ ] Secured network success.
- [ ] Saved profile success.
- [ ] Password rejection.
- [ ] Missing secret.
- [ ] DHCP failure.
- [ ] Network disappears.
- [ ] Timeout.
- [ ] Cancellation.
- [ ] Authorization denial.
- [ ] NetworkManager restart.
- [ ] Multiple adapters.
- [ ] Duplicate SSIDs.
- [ ] Duplicate profiles.
- [ ] Hidden network.
- [ ] Forget profile.

### 15.3 Fake-`nmcli` integration suite

- [ ] Exact read commands.
- [ ] Exact mutation commands.
- [ ] Locale control.
- [ ] Escaping behavior.
- [ ] Timeout behavior.
- [ ] Nonzero exits.
- [ ] malformed output.
- [ ] Secret redaction.
- [ ] State verification queries.

### 15.4 Quality gates

- [ ] Tests pass.
- [ ] Required coverage threshold passes.
- [ ] Ruff formatting passes.
- [ ] Ruff lint passes.
- [ ] Static type checking passes.
- [ ] Package build passes.
- [ ] No secret-like test values appear in generated logs or snapshots.
- [ ] No `shell=True` exists.
- [ ] No direct networking-file writes exist.
- [ ] No broad exception handler silently suppresses a failure.

### Phase 15 checkpoint

- [ ] All automated version 0.1 acceptance behavior passes in CI without touching real Wi-Fi hardware.

## 19. Phase 16 — Manual hardware validation

Create `tests/manual/V01_ACCEPTANCE.md` and record results with:

- Distribution and version.
- NetworkManager version.
- Python version.
- Terminal emulator.
- Wi-Fi adapter and driver.
- Test date.
- Pass/fail result.
- Redacted notes.

### 16.1 Platform coverage

Validate on at least:

- [ ] Ubuntu or Debian.
- [ ] Fedora or Arch Linux.

### 16.2 Core workflows

- [ ] Startup as normal user.
- [ ] Nearby networks displayed.
- [ ] Current network identified.
- [ ] Rescan.
- [ ] WPA2 personal connection.
- [ ] WPA3 personal connection when available.
- [ ] Open network connection where safely available.
- [ ] Saved credential reconnect.
- [ ] Wrong password.
- [ ] Disconnect.
- [ ] Forget one profile.
- [ ] Hidden network.
- [ ] Wi-Fi disable and enable.

### 16.3 Edge cases

- [ ] `rfkill` block.
- [ ] Adapter unplug and reinsert where hardware permits.
- [ ] Multiple adapters where available.
- [ ] Duplicate SSID across multiple access points.
- [ ] Weak network disappearing during connection.
- [ ] DHCP failure where a controlled test network is available.
- [ ] Terminal resize.
- [ ] SSH session.
- [ ] NetworkManager restart.

### 16.4 Security validation

- [ ] Inspect normal logs for password leakage.
- [ ] Inspect debug logs for password leakage.
- [ ] Trigger command failure and inspect errors.
- [ ] Trigger timeout and inspect errors.
- [ ] Trigger cancellation and inspect errors.
- [ ] Confirm no root-owned project files are created during normal use.
- [ ] Confirm no direct network configuration files are modified by the application.

### Phase 16 checkpoint

- [ ] Manual acceptance evidence exists for the supported platform matrix.
- [ ] Any known failures are documented rather than hidden.

## 20. Phase 17 — Version 0.1 release readiness

### 17.1 Final specification audit

Review every section of `docs/SPEC.md` and mark each requirement as:

- [ ] Implemented and tested.
- [ ] Explicitly deferred with owner approval.
- [ ] Not applicable with documented rationale.

No requirement may be silently omitted.

### 17.2 Final unsafe-fallback audit

Search and review for:

- [ ] `shell=True`.
- [ ] shell command concatenation.
- [ ] `sudo` invocation.
- [ ] direct writes under `/etc/NetworkManager`.
- [ ] direct writes to `wpa_supplicant` configuration.
- [ ] ConnMan fallback.
- [ ] unbounded retry loops.
- [ ] ignored subprocess exit codes.
- [ ] broad `except Exception` handlers.
- [ ] parser exceptions converted to empty collections.
- [ ] success returned before state verification.
- [ ] password-bearing logging.
- [ ] ambiguous profile deletion by name or SSID.

Document every intentional exception and justify it.

### 17.3 Final failure-visibility audit

Verify visible handling for:

- [ ] Backend unavailable.
- [ ] Adapter unavailable.
- [ ] Wi-Fi disabled.
- [ ] Radio blocked.
- [ ] Authorization failure.
- [ ] Authentication failure.
- [ ] Missing secrets.
- [ ] Network disappearance.
- [ ] DHCP failure.
- [ ] Timeout.
- [ ] Cancellation.
- [ ] Parse error.
- [ ] Verification mismatch.
- [ ] Unexpected exception.

### 17.4 Release artifacts

- [ ] Update version.
- [ ] Update changelog.
- [ ] Finalize README status.
- [ ] Build clean artifacts.
- [ ] Verify artifact contents.
- [ ] Tag release.
- [ ] Publish release notes.

### Version 0.1 completion gate

Version 0.1 is complete only when:

- [ ] All acceptance criteria in `SPEC.md` pass.
- [ ] All required automated checks pass.
- [ ] Manual validation is recorded.
- [ ] No known credential leak exists.
- [ ] No dangerous or silent fallback exists.
- [ ] Known limitations are documented.

## 21. Deferred backlog after version 0.1

These items must not be mixed into version 0.1 without revising the specification:

- [ ] Direct NetworkManager D-Bus backend.
- [ ] WPA-Enterprise and 802.1X.
- [ ] Captive-portal detection and browser integration.
- [ ] Hotspot creation.
- [ ] Static IP and DNS editing.
- [ ] Additional networking backends.
- [ ] Internationalization.
- [ ] Theme configuration.
- [ ] Distribution-native packages.
- [ ] Automated release publishing.
