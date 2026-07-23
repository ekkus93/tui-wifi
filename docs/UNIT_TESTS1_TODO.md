# tui-wifi Unit Test Expansion 1 TODO

This document is the authoritative implementation and completion checklist for the first
major unit-test expansion after the version 0.1 implementation. The work is organized by
risk rather than raw line coverage: false success, unverified NetworkManager mutations,
stale state publication, leaked child processes, and credential disclosure are the primary
concerns.

## Completion status

- [x] Implemented directly on `master`.
- [x] Verified from a fresh archive of current `master`.
- [x] 191 automated tests pass without touching the host's real Wi-Fi state.
- [x] Global branch-aware coverage is 94.07%, above the enforced 90% floor.
- [x] All safety-critical per-module branch-coverage gates pass.
- [x] Black formatting passes.
- [x] Ruff passes with `select = ["ALL"]`.
- [x] Mypy passes in strict mode.
- [x] Pytest warnings remain errors.
- [x] Wheel and source-distribution build validation passes.
- [x] The built wheel installs in a clean virtual environment and passes `pip check`.
- [x] No lint, typing, or warning suppressions were added.

## 1. Non-negotiable test rules

- [x] Do not weaken Ruff, Mypy, pytest warning handling, Black, or CI.
- [x] Do not add `noqa`, `type: ignore`, per-file ignores, disabled lint families,
  blanket warning filters, or ignored type errors.
- [x] Do not run real `nmcli` mutations from ordinary tests or CI.
- [x] Do not require NetworkManager, a Wi-Fi adapter, or a particular host network state.
- [x] Use deterministic fakes, exact command fixtures, and Textual's test pilot.
- [x] Use `tests.assertions.verify` instead of bare assertions.
- [x] Coordinate concurrency with `asyncio.Event` and explicit gates, not arbitrary sleeps.
- [x] Verify returned values and relevant side effects, including commands, timeouts,
  sensitive indexes, call ordering, snapshots, lock release, and secret clearing.
- [x] Verify typed failures and exact `ErrorCategory` values instead of generic exceptions.
- [x] Keep synthetic credentials out of logs, exception text, and command representations.
- [x] Keep test helpers typed and shared only where they reduce meaningful duplication.

## 2. Test infrastructure

- [x] Add `tests/factories.py` with typed factories for access points, devices, profiles,
  active connections, logical groups, backend states, and application snapshots.
- [x] Add `tests/nmcli_fixtures.py` with exact machine-readable command builders and safe
  process-result fixtures.
- [x] Add `tests/tui/helpers.py` for deterministic Textual settling and stable text access.
- [x] Add `scripts/check_critical_coverage.py` with structured JSON parsing and explicit
  failure messages.
- [x] Add tests for the critical-coverage checker itself, including success, threshold
  regression, malformed reports, missing modules, and command exit statuses.
- [x] Extend `FakeProcessRunner` to retain complete `ProcessRequest` objects while keeping
  invocation diagnostics redacted.
- [x] Preserve exact command matching and fail immediately on unexpected or missing calls.
- [x] Add coverage output and generated coverage/build directories to `.gitignore`.

## 3. NetworkManager mutation tests

### 3.1 Visible connection commands

- [x] Verify an open network emits no password argument or sensitive indexes.
- [x] Verify personal-network passwords are placed at the exact expected argument index.
- [x] Verify sensitive values are absent from redacted command metadata.
- [x] Verify single-BSSID pinning emits one `bssid` argument.
- [x] Verify absent BSSID pinning emits no `bssid` argument.
- [x] Verify the configured connection timeout is used.
- [x] Verify `autoconnect=True` emits no profile modification.
- [x] Verify `autoconnect=False` modifies only the verified newly active UUID.
- [x] Verify the connection result is re-read and returned rather than inferred from exit
  status.

### 3.2 Hidden connection commands

- [x] Verify hidden open networks emit `hidden yes` without a password.
- [x] Verify hidden personal-network passwords are redacted at the exact index.
- [x] Verify hidden `autoconnect=False` performs a post-verification profile update.
- [x] Reject a blank hidden SSID before process execution.
- [x] Reject unsupported hidden security before process execution.
- [x] Reject personal hidden security without a password before process execution.

### 3.3 Security validation

- [x] Reject WEP, enterprise, and unknown visible security before calling `nmcli`.
- [x] Reject personal security without required credentials.
- [x] Permit open security without credentials.
- [x] Verify invalid requests leave the fake process queue untouched.

### 3.4 Active-state verification

- [x] Reject a successful command when no active Wi-Fi connection exists.
- [x] Reject a connection active on the wrong interface.
- [x] Reject an active connection with the wrong UUID.
- [x] Reject an active connection with the wrong SSID.
- [x] Verify optional UUID and SSID checks can be omitted without altering identity.
- [x] Verify each failure contains actionable technical details.

### 3.5 Disconnect, delete, and auto-connect

- [x] Verify disconnect uses a bounded wait and the exact requested interface.
- [x] Accept disconnect only when the requested interface is no longer active.
- [x] Reject false-success disconnect when that interface remains active.
- [x] Verify profile deletion targets UUID rather than profile name.
- [x] Verify deletion re-reads profiles and rejects a retained UUID.
- [x] Verify auto-connect emits `yes` and `no` exactly.
- [x] Verify auto-connect returns the re-read stored profile.
- [x] Reject auto-connect success when the profile disappears.
- [x] Reject auto-connect success when the stored value does not match.

## 4. Saved-profile and active-connection parsing tests

- [x] Filter Ethernet, VPN, bridge, and other non-Wi-Fi summaries.
- [x] Preserve Wi-Fi profile order while issuing details only for wireless rows.
- [x] Cover `wifi` and `802-11-wireless` profile types.
- [x] Validate every profile UUID before detail lookup.
- [x] Reject malformed summary field counts.
- [x] Accept exactly the bounded profile-detail limit.
- [x] Reject one row above the bound before issuing detail queries.
- [x] Cover WPA2, WPA3, mixed personal, open, enterprise, and unknown key management.
- [x] Cover active and inactive saved profiles.
- [x] Cover present and absent interface constraints.
- [x] Cover blank and present SSIDs.
- [x] Cover missing detail lines and summary auto-connect fallback.
- [x] Cover extra detail lines without shifting defined fields.
- [x] Return `None` when no device is activated.
- [x] Parse repeated IPv4 and IPv6 addresses and DNS values in order.
- [x] Parse optional gateways and profile-name fallbacks.
- [x] Reject active devices missing `GENERAL.CON-UUID`.
- [x] Reject invalid active UUIDs before querying the profile SSID.
- [x] Use the validated UUID for subsequent commands and returned models.

## 5. Core nmcli tests

### 5.1 Executable and process translation

- [x] Verify an explicit executable path bypasses PATH lookup.
- [x] Verify PATH lookup is used when no explicit path is supplied.
- [x] Report missing `nmcli` without attempting a process.
- [x] Translate missing-executable, timeout, and nonzero-exit failures into typed Wi-Fi
  errors while retaining exception causes.
- [x] Preserve safe stderr, exit code, and operation metadata.
- [x] Cover authorization, missing secrets, authentication rejection, unavailable network,
  DHCP/IP failure, NetworkManager unavailable, disabled Wi-Fi, rfkill, and unknown errors.

### 5.2 Status and radio

- [x] Verify successful status reports version, NetworkManager state, radio state, and
  resolved executable.
- [x] Map authorization and generic command failures to explicit backend availability.
- [x] Convert malformed status output into unavailable status rather than false success.
- [x] Cover software enabled, software disabled, hardware blocked, and both-disabled radio
  combinations.
- [x] Reject malformed radio field counts and booleans.
- [x] Verify radio mutation uses the correct command and timeout.
- [x] Re-read radio state after mutation.
- [x] Reject a successful radio command whose observed state does not match.

### 5.3 Devices and access points

- [x] Parse activated, disconnected, unavailable, unmanaged, and unknown device states.
- [x] Filter non-Wi-Fi devices.
- [x] Preserve escaped connection names.
- [x] Reject malformed device rows.
- [x] Verify explicit scan command, interface, and timeout.
- [x] Propagate typed scan failures.
- [x] Verify access-point listing explicitly uses `--rescan no`.
- [x] Cover open, WPA1, WPA2, WPA3, mixed, enterprise, WEP, and unknown security.
- [x] Cover 2.4 GHz, channel 14, 5 GHz, 6 GHz, and unknown frequency mappings.
- [x] Cover active markers, escaped SSIDs, blank SSID omission, absent signals, invalid
  signals, and malformed field counts.

## 6. Service behavior tests

- [x] Verify listener publication, callback-safe iteration, and idempotent unsubscribe.
- [x] Verify non-Linux startup fails before backend access.
- [x] Translate missing executable, unauthorized, unavailable, and unknown backend status.
- [x] Preserve last valid state and mark it stale after every read-stage failure.
- [x] Keep first-load failure non-stale when no meaningful state exists.
- [x] Convert scan-request failure into a warning while retaining coherent results.
- [x] Verify disabled and hardware-blocked radio states skip scans but still load profiles
  and active state.
- [x] Verify no-adapter refresh skips scan and access-point calls.
- [x] Cover preferred adapter, missing preferred adapter, active adapter preference, sole
  managed adapter, unmanaged adapters, no adapters, and multiple-adapter ambiguity.
- [x] Verify ambiguous interface messages are deterministic and sorted.
- [x] Verify one saved UUID without a password activates the saved profile.
- [x] Verify passwords, no UUIDs, or multiple UUIDs use the visible-connect path.
- [x] Verify one BSSID is pinned and multiple BSSIDs are never chosen arbitrarily.
- [x] Clear visible and hidden passwords after success, typed mutation failure, and refresh
  failure.
- [x] Forward every hidden-network field exactly.
- [x] Fail before mutation when no interface is selected.
- [x] Verify idle disconnect is a no-op and active disconnect uses the exact request.
- [x] Verify Wi-Fi enable/disable, profile deletion, and auto-connect values are forwarded
  exactly and followed by refresh.
- [x] Verify profile lookup success and absence.
- [x] Verify `close()` is idempotent and prevents future refresh backend calls.

## 7. Service concurrency and lifecycle tests

- [x] Add deterministic refresh-generation barriers with `asyncio.Event`.
- [x] Prove a late older refresh cannot overwrite a newer snapshot.
- [x] Prove closing during an in-flight refresh follows the explicit current contract.
- [x] Prove two mutations never enter the backend concurrently.
- [x] Verify ordered running-state publication for serialized mutations.
- [x] Verify typed mutation failure publishes failed state, guidance, and error.
- [x] Verify the mutation lock is released after typed failure.
- [x] Verify cancellation publishes `CANCELLED`, clears credentials, and releases the lock.
- [x] Verify unexpected internal exceptions propagate and still release the lock.
- [x] Verify hidden-network cancellation clears its password.
- [x] Repeat the concurrency suite many times to detect nondeterminism.
- [x] Run tests in reverse collection order to detect shared-state coupling.

## 8. Process runner tests

- [x] Reject zero and negative timeouts before spawning.
- [x] Verify deterministic locale defaults, inherited environment, explicit overrides, and
  parent-environment immutability.
- [x] Verify missing executables and generic spawn failures are typed and redacted.
- [x] Verify stdin delivery and no-input behavior.
- [x] Redact sensitive stdin from successful and failed stdout/stderr.
- [x] Verify empty sensitive stdin does not trigger empty-string replacement.
- [x] Redact sensitive arguments and stdin simultaneously while preserving neighboring text.
- [x] Reject invalid UTF-8 from stdout and stderr without exposing partial output.
- [x] Verify cancellation terminates and reaps the child with explicit cancelled metadata.
- [x] Verify a child ignoring terminate is escalated to kill and reaped.
- [x] Verify timeout metadata, duration, flags, exit code, and redacted command.
- [x] Preserve positive and signal-style nonzero exit codes.
- [x] Preserve separate stdout and stderr on success and failure.
- [x] Reject invalid sensitive argument indexes immediately.

## 9. Textual behavior tests

### 9.1 Dialogs

- [x] Verify password obscuring, show-password toggle, required validation, auto-connect,
  submission, cancellation, and field clearing.
- [x] Verify hidden-network SSID/password validation, open and personal modes,
  show-password, auto-connect, submission, and cancellation.
- [x] Verify confirmation cancel/confirm results.
- [x] Verify message details and dismissal.

### 9.2 Main screen

- [x] Verify operation, error, warning, no-adapter, disabled, blocked, empty, and normal
  message priority.
- [x] Verify connected summary, IP display, and stale marker.
- [x] Verify action enablement and labels for idle, connected, busy, enabled, and disabled
  states.
- [x] Verify secured, open, unsupported, and multiple-saved-profile routing.
- [x] Verify confirmed connection executes once.
- [x] Verify authentication failure remains visible and executes once.
- [x] Verify enterprise, WEP, and unknown security never reach password or backend mutation.
- [x] Verify refresh, hidden, saved, details, disconnect, and Wi-Fi workflows and shortcuts.
- [x] Verify destructive cancellation performs no backend mutation.
- [x] Verify selection persistence across reordering and fallback when a row disappears.
- [x] Verify duplicate SSIDs with different security remain distinct.
- [x] Verify lookup failure produces no stale selection.
- [x] Verify compact and normal responsive breakpoints.

### 9.3 Saved profiles

- [x] Render profile name, SSID, auto-connect, active state, and interface.
- [x] Verify auto-connect inversion targets the selected UUID.
- [x] Verify forget cancel and confirm behavior.
- [x] Verify saved connection uses the selected UUID and interface.
- [x] Verify empty selection, missing adapter, and backend failures are visible.

## 10. Coverage and CI enforcement

- [x] Raise the global branch-aware coverage floor to 90%.
- [x] Generate `coverage.json` during every test run.
- [x] Enforce 90% branch coverage for `nmcli_mutations.py`.
- [x] Enforce 85% branch coverage for `nmcli_profiles.py`.
- [x] Enforce 85% branch coverage for `nmcli_core.py`.
- [x] Enforce 85% branch coverage for `services/wifi.py`.
- [x] Enforce 90% branch coverage for `process/runner.py`.
- [x] Fail explicitly if a required module or structured coverage field is missing.
- [x] Run the structured coverage check on Python 3.11, 3.12, and 3.13 CI jobs.
- [x] Keep Textual modules outside the numeric metric while enforcing their behavior with
  pilot tests.
- [x] Do not upload ordinary CI coverage or package artifacts.
- [x] Keep release assets restricted to matching version tags.

## 11. Documentation

- [x] Document deterministic testing architecture in `docs/ARCHITECTURE.md`.
- [x] Document the 90% global and safety-critical branch gates in `README.md`.
- [x] Document the local validation commands.
- [x] Explain why framework-driven UI lifecycle lines are excluded from numeric coverage.
- [x] Preserve the rule that behavioral UI tests are mandatory despite that exclusion.

## 12. Final acceptance gate

- [x] All new tests pass from a fresh checkout.
- [x] All existing tests remain passing.
- [x] Black reports no formatting differences.
- [x] Ruff reports no warnings or errors with every rule family enabled.
- [x] Strict Mypy reports no source errors.
- [x] Pytest reports no warnings.
- [x] Global coverage is at least 90%.
- [x] Every critical-module branch floor passes.
- [x] Tests do not touch the host's real Wi-Fi state.
- [x] No credential appears in captured output, diagnostics, or command representations.
- [x] No unsafe fallback, silent failure, or unverified mutation success was introduced.
- [x] Wheel and source distribution build successfully.
- [x] The wheel installs and passes `pip check` in a clean virtual environment.
