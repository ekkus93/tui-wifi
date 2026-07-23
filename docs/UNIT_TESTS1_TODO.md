# tui-wifi Unit Test Expansion 1 TODO

This document is the authoritative implementation checklist for the first major unit-test
coverage expansion after the version 0.1 implementation. It focuses on the code paths where
a false success, unverified state transition, stale state publication, process leak, or
credential leak would be most damaging.

The checklist is intentionally organized by risk rather than by raw line coverage. Increasing
the total percentage is useful, but the primary goal is to prove the behavior of every
safety-critical branch.

## 1. Current baseline

- [x] The existing automated suite contains 46 passing tests.
- [x] The current measured total coverage is approximately 76%.
- [x] Black formatting, the complete Ruff rule set, strict Mypy, and warnings-as-errors are
  enforced by CI.
- [x] Existing tests do not touch the host's real Wi-Fi state.
- [x] The highest-priority coverage gaps are currently concentrated in:
  - `src/tui_wifi/backends/nmcli_mutations.py`
  - `src/tui_wifi/backends/nmcli_profiles.py`
  - `src/tui_wifi/backends/nmcli_core.py`
  - `src/tui_wifi/services/wifi.py`
  - `src/tui_wifi/process/runner.py`
  - the Textual workflows excluded from normal coverage accounting

## 2. Non-negotiable test rules

- [ ] Do not weaken Ruff, Mypy, pytest warning handling, Black, or the existing CI workflow.
- [ ] Do not add `noqa`, `type: ignore`, per-file ignores, disabled lint families, warning
  filters, or blanket exception handling to make tests pass.
- [ ] Do not run real `nmcli` mutations from ordinary unit or CI tests.
- [ ] Do not depend on the host having NetworkManager, a Wi-Fi adapter, or a particular
  network configuration.
- [ ] Use `FakeProcessRunner`, `FakeWifiBackend`, purpose-built deterministic fakes, and
  Textual's test pilot.
- [ ] Use the repository's `tests.assertions.verify` helper instead of bare `assert`, because
  the complete Ruff security rule set rejects bare assertions.
- [ ] Do not use arbitrary sleeps to coordinate concurrency tests. Use `asyncio.Event`,
  futures, barriers, or deterministic fake hooks.
- [ ] Every test must verify both the returned result and the relevant side effect:
  - exact command arguments
  - timeout value
  - sensitive argument indexes
  - backend call ordering
  - resulting snapshot
  - operation lifecycle
  - lock release
  - secret clearing
- [ ] Every expected failure test must verify the specific typed exception or
  `ErrorCategory`; generic exception matching is not sufficient.
- [ ] Test credentials must be synthetic and must never be written to logs, exception text,
  command representations, or committed snapshots.
- [ ] New helper APIs must be typed and reusable; do not duplicate large command-response
  fixtures across many tests.
- [ ] Keep each test focused on one behavior. A test may verify several related outcomes of
  one operation, but should not combine unrelated workflows.

## 3. Planned test file organization

Create or expand the following files. Existing files may be split when doing so improves
clarity, but do not create thin files containing only one trivial test.

- [ ] Create `tests/unit/test_nmcli_mutations.py`.
- [ ] Create `tests/unit/test_nmcli_profiles.py`.
- [ ] Expand `tests/unit/test_nmcli.py` for `NmcliCore` status, radio, device, scan, and error
  translation behavior.
- [ ] Expand `tests/unit/test_service.py` for ordinary service behavior.
- [ ] Create `tests/unit/test_service_concurrency.py` for generation ordering, cancellation,
  mutation serialization, and lock-release tests.
- [ ] Expand `tests/unit/test_process.py` for process edge cases and secret-safe stdin.
- [ ] Expand `tests/tui/test_app.py` or create focused files under `tests/tui/` for major
  dialogs and workflows.
- [ ] Create a shared helper module only when at least two test modules need it. Preferred
  locations:
  - `tests/factories.py` for typed model factories
  - `tests/nmcli_fixtures.py` for reusable machine-readable output and command builders
  - `tests/async_helpers.py` for deterministic concurrency fakes
- [ ] Add package `__init__.py` files where required by the strict test package layout.

## 4. Phase 0: baseline capture and test infrastructure

### 4.1 Record the starting state

- [ ] Run the complete existing gate before adding tests:

  ```bash
  black --check .
  ruff check .
  mypy src/tui_wifi
  pytest -m 'not real_network'
  ```

- [ ] Record the starting per-module branch coverage locally for comparison.
- [ ] Confirm that all existing tests pass before changing production code.
- [ ] Do not change production behavior merely to make it easier to test unless the change
  also improves the design and retains identical externally visible behavior.

### 4.2 Add typed model factories

- [ ] Add factory helpers for frequently constructed objects, using keyword arguments:
  - `AccessPoint`
  - `WifiDevice`
  - `SavedProfile`
  - `ActiveWifiConnection`
  - `NetworkGroup`
  - `BackendStatus`
- [ ] Give every factory conservative defaults representing a normal WPA2 personal network.
- [ ] Allow each field relevant to a test to be overridden explicitly.
- [ ] Do not hide important setup. A test concerning a UUID, interface, security class, or
  active state must set that value visibly.
- [ ] Add direct unit tests for any nontrivial factory logic. Simple constructors do not need
  tests of their own.

### 4.3 Improve deterministic process fixtures

- [ ] Add helpers that build expected `nmcli` command tuples without silently normalizing or
  reordering arguments.
- [ ] Add a helper to construct `ProcessResult` values with explicit stdout, stderr, exit
  code, timeout flags, and cancellation flags.
- [ ] Ensure `FakeProcessRunner.assert_finished()` remains mandatory at the end of each
  command-sequence test.
- [ ] Add a way to inspect the queued or observed `ProcessRequest` so tests can verify:
  - `timeout`
  - `sensitive_arg_indexes`
  - fixed executable path
  - argument ordering
- [ ] Do not expose raw secrets from helper representations.

### 4.4 Add deterministic asynchronous fakes

- [ ] Implement a small test-only backend or hook mechanism that can pause selected backend
  methods on `asyncio.Event` objects.
- [ ] Support separate events for "method entered" and "method may continue".
- [ ] Record concurrent call count and maximum observed concurrency.
- [ ] Record exact backend call order.
- [ ] Ensure a test failure cannot leave a pending task or unreleased event.
- [ ] Add cleanup in `finally` blocks when a test creates background tasks.

## 5. Phase 1: `nmcli_mutations.py` tests

This phase is the highest priority because it covers commands that change network state and
then decide whether the operation succeeded.

### 5.1 Visible open-network connection

- [ ] Add `test_connect_visible_open_network_uses_no_password_argument`.
- [ ] Queue the exact successful `nmcli device wifi connect` command.
- [ ] Verify the command includes the SSID and interface.
- [ ] Verify no `password` argument is present.
- [ ] Verify `sensitive_arg_indexes` is empty.
- [ ] Queue active-connection verification responses.
- [ ] Verify the returned `ActiveWifiConnection` matches the requested SSID and interface.
- [ ] Verify all queued commands were consumed.

### 5.2 Visible WPA2 connection and credential protection

- [ ] Add `test_connect_visible_personal_network_marks_password_sensitive`.
- [ ] Use a synthetic `SecretValue`.
- [ ] Verify the exact password argument position is listed in `sensitive_arg_indexes`.
- [ ] Verify the process request's redacted command does not contain the credential.
- [ ] Verify connection verification succeeds.
- [ ] Verify no command or exception representation leaks the credential.

### 5.3 BSSID pinning

- [ ] Add `test_connect_visible_network_includes_requested_bssid`.
- [ ] Verify `bssid <address>` appears exactly once and in the expected command location.
- [ ] Verify the BSSID is not treated as sensitive.
- [ ] Add a companion test proving the argument is omitted when `request.bssid` is `None`.

### 5.4 Auto-connect disabled after connection

- [ ] Add `test_connect_visible_network_disables_autoconnect_after_verified_connection`.
- [ ] Queue the connection command, active-connection query, profile modification command,
  and profile verification query.
- [ ] Verify auto-connect modification happens only after the active connection is verified.
- [ ] Verify the profile UUID returned by the active connection is used.
- [ ] Verify the stored profile is re-read and matches `enabled=False`.
- [ ] Add `test_connect_visible_network_does_not_modify_autoconnect_when_enabled`.

### 5.5 Visible-connection security rejection

- [ ] Add parameterized coverage for unsupported security classes:
  - WEP
  - Enterprise
  - Unknown
- [ ] Verify `UNSUPPORTED_SECURITY` is raised before the process runner is called.
- [ ] Add `test_connect_visible_personal_network_requires_password`.
- [ ] Verify `MISSING_SECRETS` is raised before the process runner is called.
- [ ] Add an open-network test confirming a password is not required.

### 5.6 Hidden-network connection

- [ ] Add `test_connect_hidden_open_network_uses_hidden_yes`.
- [ ] Add `test_connect_hidden_personal_network_marks_password_sensitive`.
- [ ] Verify the exact `hidden yes` arguments.
- [ ] Verify the same post-connect active-state validation used for visible networks.
- [ ] Verify `autoconnect=False` triggers profile modification and verification.
- [ ] Add `test_connect_hidden_network_rejects_blank_ssid`.
- [ ] Verify a blank SSID fails before any process call.
- [ ] Add unsupported-security and missing-password hidden-network tests.

### 5.7 Saved-profile activation

- [ ] Add `test_activate_saved_profile_uses_uuid_and_interface`.
- [ ] Verify the exact `connection up uuid ... ifname ...` command.
- [ ] Verify the connection is re-read and its UUID and interface match.
- [ ] Add a verification-failure test for a different returned UUID.
- [ ] Add a verification-failure test for a different returned interface.

### 5.8 Active-state verification matrix

Add focused tests for `_verify_active` through public mutation methods or, when clearer, as
unit tests of the protected method using a concrete backend instance.

- [ ] No active connection returned.
- [ ] Active connection is on a different interface.
- [ ] Active connection UUID differs from the expected UUID.
- [ ] Active connection SSID differs from the expected SSID.
- [ ] UUID check omitted when the expected UUID is `None`.
- [ ] SSID check omitted when the expected SSID is `None`.
- [ ] Successful verification returns the exact active connection object.
- [ ] Each failure must assert `ErrorCategory.VERIFICATION_FAILURE` and meaningful technical
  details.

### 5.9 Disconnect verification

- [ ] Add `test_disconnect_uses_bounded_wait_and_interface`.
- [ ] Verify the exact command and mutation timeout.
- [ ] Verify success when no active connection remains.
- [ ] Verify success when a different interface remains active.
- [ ] Add `test_disconnect_fails_when_requested_interface_remains_active`.
- [ ] Verify the failure category and technical details.

### 5.10 Delete-profile verification

- [ ] Add `test_delete_saved_profile_uses_uuid`.
- [ ] Verify the profile list is re-read after deletion.
- [ ] Verify success when the UUID is absent.
- [ ] Add `test_delete_saved_profile_fails_when_profile_still_exists`.
- [ ] Verify `VERIFICATION_FAILURE` rather than silently accepting the command exit status.

### 5.11 Auto-connect mutation verification

- [ ] Parameterize enabled and disabled values.
- [ ] Verify `yes` and `no` are emitted correctly.
- [ ] Verify the profile is re-read after modification.
- [ ] Verify the returned profile is the verified stored profile.
- [ ] Add failure coverage when the profile disappears.
- [ ] Add failure coverage when the stored value does not match the request.

### 5.12 Mutation test completion gate

- [ ] Every public method in `NmcliMutationsMixin` has success and failure coverage.
- [ ] Every state verification branch is exercised.
- [ ] Every password-bearing command verifies sensitive argument indexes.
- [ ] No test relies on the host's real `nmcli`.
- [ ] Target at least 90% branch coverage for `nmcli_mutations.py`, with every remaining
  uncovered branch reviewed and documented as unreachable or deliberately integration-only.

## 6. Phase 2: `nmcli_profiles.py` tests

### 6.1 Saved-profile list filtering

- [ ] Add a test containing Wi-Fi, Ethernet, bridge, and VPN profile summary rows.
- [ ] Verify only `wifi` and `802-11-wireless` rows trigger detail queries.
- [ ] Verify non-Wi-Fi UUIDs are never queried for wireless details.
- [ ] Verify output ordering is preserved unless production code intentionally defines a
  different order.

### 6.2 Profile detail parsing

- [ ] Test a complete WPA2 profile with SSID, key management, interface, and auto-connect.
- [ ] Test a complete WPA3 SAE profile.
- [ ] Test a mixed WPA2/WPA3 profile.
- [ ] Test an open profile using blank or `none` key management.
- [ ] Test an enterprise profile.
- [ ] Test unknown key management.
- [ ] Verify the profile `active` flag from summary device values:
  - blank
  - `--`
  - actual interface name
- [ ] Verify an empty SSID is represented as `None`.
- [ ] Verify an empty interface name is represented as `None`.

### 6.3 Partial detail output

- [ ] Test only an SSID line being returned.
- [ ] Test SSID and key-management lines only.
- [ ] Test a missing interface line.
- [ ] Test a missing detail-level auto-connect line.
- [ ] Verify summary-level auto-connect is used as the fallback.
- [ ] Test extra trailing lines and decide whether they are ignored or rejected according to
  the current parser contract.

### 6.4 Invalid summary and UUID data

- [ ] Test a malformed summary field count.
- [ ] Test an invalid UUID.
- [ ] Verify a typed `PARSE_FAILURE` is raised.
- [ ] Verify no detail query is attempted after UUID validation fails.

### 6.5 Bounded profile enumeration

- [ ] Add a test with exactly `PROFILE_DETAIL_LIMIT` rows and verify it is accepted.
- [ ] Add a test with `PROFILE_DETAIL_LIMIT + 1` rows and verify it fails before issuing
  detail queries.
- [ ] Verify `COMMAND_FAILURE`, the user-facing summary, and bounded technical details.
- [ ] Avoid constructing a huge hand-written string; generate deterministic rows in the test.

### 6.6 Profile security classification matrix

- [ ] Parameterize all supported spellings and combinations currently recognized by
  `profile_security`.
- [ ] Include case and surrounding whitespace variants.
- [ ] Include:
  - empty
  - `none`
  - `wpa-psk`
  - `sae`
  - combined `sae` and `wpa-psk`
  - `wpa-eap`
  - `ieee8021x`
  - unknown values
- [ ] Verify enterprise detection takes precedence over personal-token detection where the
  input contains multiple tokens.

### 6.7 No active connection

- [ ] Add `test_get_active_wifi_connection_returns_none_without_activated_device`.
- [ ] Include disconnected, unavailable, and unmanaged devices.
- [ ] Verify no device-detail or SSID-profile query is issued.

### 6.8 Active connection detail parsing

- [ ] Test a complete active connection with:
  - profile name
  - UUID
  - state
  - multiple IPv4 addresses
  - IPv4 gateway
  - multiple IPv4 DNS entries
  - multiple IPv6 addresses
  - IPv6 gateway
  - multiple IPv6 DNS entries
  - SSID query result
- [ ] Verify repeated machine-readable keys are preserved in order.
- [ ] Verify missing gateways become `None`.
- [ ] Verify a blank SSID becomes `None`.
- [ ] Verify profile name falls back to the device's active connection name.
- [ ] Verify profile name falls back to an empty string only when both sources are absent.

### 6.9 Active UUID failure cases

- [ ] Add a test where `GENERAL.CON-UUID` is absent.
- [ ] Add a test where the UUID is present but invalid.
- [ ] Verify both failures are typed parse failures.
- [ ] Verify the SSID profile query is not issued when UUID validation cannot succeed.

### 6.10 Profile test completion gate

- [ ] Every branch in saved-profile filtering and partial detail fallback is covered.
- [ ] Active IPv4 and IPv6 aggregation is covered.
- [ ] Limit enforcement is covered at and above the boundary.
- [ ] Target at least 85% branch coverage for `nmcli_profiles.py`.

## 7. Phase 3: `WifiService` behavior and concurrency tests

### 7.1 Subscription lifecycle

- [ ] Add a test proving subscribers receive each published coherent snapshot.
- [ ] Verify unsubscribing stops future notifications.
- [ ] Verify calling the unsubscribe callback twice is harmless.
- [ ] Verify one listener unsubscribing does not remove other listeners.
- [ ] Verify publication uses a stable listener snapshot when a listener modifies
  subscriptions during its callback.

### 7.2 Platform guard

- [ ] Add a test for non-Linux startup using `monkeypatch` on `sys.platform`.
- [ ] Verify no backend method is called.
- [ ] Verify the snapshot contains the explicit Linux-only error.
- [ ] Verify the operation does not appear successful.

### 7.3 Backend status translation

Parameterize status availability values and verify the resulting structured service error.

- [ ] `MISSING_EXECUTABLE` maps to `MISSING_NMCLI`.
- [ ] `UNAUTHORIZED` maps to `AUTHORIZATION_DENIED`.
- [ ] Other unavailable states map to `NETWORK_MANAGER_UNAVAILABLE`.
- [ ] Verify the last valid state is preserved when status becomes unavailable after a
  successful refresh.

### 7.4 Adapter selection policy

- [ ] Preferred managed adapter is selected when present.
- [ ] Preferred adapter missing produces a visible `NO_ADAPTER` error.
- [ ] An activated managed adapter is preferred over disconnected adapters.
- [ ] A single managed disconnected adapter is selected.
- [ ] Unmanaged adapters are ignored.
- [ ] No managed adapters produces `selected_device=None` without inventing a device.
- [ ] Multiple idle managed adapters produce an explicit ambiguity error.
- [ ] Verify interface names in ambiguity messages are sorted deterministically.

### 7.5 Radio-state refresh behavior

- [ ] When Wi-Fi is enabled, selected-device access points are listed.
- [ ] When Wi-Fi is disabled, access-point listing is skipped.
- [ ] When Wi-Fi is hardware blocked, access-point listing is skipped.
- [ ] Saved profiles and active connection state are still loaded when scanning is skipped.
- [ ] No adapter means scan and access-point calls are skipped.

### 7.6 Scan warning behavior

- [ ] Add `test_scan_request_failure_becomes_warning_and_refresh_continues`.
- [ ] Make `request_scan` raise a typed `WifiError`.
- [ ] Verify access points are still listed afterward.
- [ ] Verify the resulting snapshot is not stale merely because the scan request failed.
- [ ] Verify the warning contains the friendly summary.
- [ ] Verify the operation phase is succeeded when the remaining refresh succeeds.

### 7.7 Refresh failure preservation

- [ ] Parameterize failures from each major read stage:
  - status
  - radio state
  - device list
  - active connection
  - saved profiles
  - access points
- [ ] Verify the previous coherent state remains intact.
- [ ] Verify `stale=True` only when previous device or network state exists.
- [ ] Verify the generation advances and the failed operation is visible.
- [ ] Verify the error and guidance fields are populated from `WifiError`.

### 7.8 Refresh generation ordering

- [ ] Add a deterministic test with two overlapping refreshes.
- [ ] Pause the first refresh after it has captured its generation.
- [ ] Allow the second refresh to complete and publish newer data.
- [ ] Resume the first refresh with different older data.
- [ ] Verify the first refresh does not overwrite the second snapshot.
- [ ] Verify the final generation belongs to the second refresh.
- [ ] Verify listeners do not receive the stale candidate as the final state.

### 7.9 Close behavior

- [ ] Add a test proving `close()` prevents new refresh backend calls.
- [ ] Verify `refresh()` after close returns the current snapshot unchanged.
- [ ] Verify repeated `close()` calls are harmless.
- [ ] Decide and test the behavior of an already-running refresh when `close()` is called.
  Keep the result explicit; do not silently assume cancellation.

### 7.10 Saved-profile connection path

- [ ] When a group has exactly one saved UUID and no new password, verify the service calls
  `activate_saved_profile`.
- [ ] Verify `connect_visible_network` is not called in that path.
- [ ] When a password is supplied, verify a new visible connection request is used.
- [ ] When there are zero or multiple saved UUIDs, verify the visible connection path is
  used.

### 7.11 BSSID selection policy

- [ ] A group with exactly one member BSSID passes that BSSID to the backend.
- [ ] A group with multiple member BSSIDs passes `None` rather than selecting arbitrarily.
- [ ] A group with no BSSID passes `None`.

### 7.12 Password clearing guarantees

- [ ] Visible connection success clears the supplied `SecretValue`.
- [ ] Visible connection backend failure clears the supplied `SecretValue`.
- [ ] Visible connection cancellation clears the supplied `SecretValue`.
- [ ] Hidden connection success clears the supplied `SecretValue`.
- [ ] Hidden connection backend failure clears the supplied `SecretValue`.
- [ ] Hidden connection cancellation clears the supplied `SecretValue`.
- [ ] Verify clearing occurs even if the subsequent refresh fails.

### 7.13 Hidden connection service behavior

- [ ] Verify the selected interface, SSID, security, password, and auto-connect flag are
  forwarded exactly.
- [ ] Verify no hidden connection starts without a selected interface.
- [ ] Verify unsupported security is rejected at the correct layer.
- [ ] Verify operation target and message identify a hidden connection attempt.

### 7.14 Disconnect no-op and mutation

- [ ] If there is no active connection, `disconnect()` returns the same snapshot and makes no
  backend call.
- [ ] If active, verify the request includes device and UUID.
- [ ] Verify the post-disconnect refresh occurs only after the mutation returns.
- [ ] Verify a backend failure publishes a failed disconnect operation.

### 7.15 Radio, delete, and auto-connect mutations

For each service mutation:

- [ ] Verify the running operation kind, target, and message.
- [ ] Verify the exact backend method and arguments.
- [ ] Verify refresh occurs after success.
- [ ] Verify failure is published with the original snapshot data preserved.
- [ ] Verify the mutation lock is released after failure.

Additionally:

- [ ] Enabling Wi-Fi refreshes with `request_scan=True`.
- [ ] Disabling Wi-Fi refreshes without requesting a scan.
- [ ] Profile deletion uses the requested UUID.
- [ ] Auto-connect update forwards the keyword-only enabled value.

### 7.16 Mutation lifecycle

- [ ] Add direct tests for operation phase transitions:
  - running
  - failed
  - cancelled
- [ ] Verify successful mutations are followed by the refresh operation rather than leaving
  a stale mutation-running snapshot.
- [ ] Verify `WifiError` sets error and guidance.
- [ ] Verify `asyncio.CancelledError` sets the cancelled phase and does not become a generic
  failure.
- [ ] Verify unexpected exceptions are not swallowed or converted into success.

### 7.17 Mutation serialization

- [ ] Start two mutation tasks concurrently using a backend that pauses the first mutation.
- [ ] Verify the second backend mutation does not enter while the first owns the lock.
- [ ] Release the first and verify the second then proceeds.
- [ ] Verify maximum concurrent backend mutations is one.
- [ ] Verify call order is deterministic.

### 7.18 Lock release after interruption

- [ ] Backend raises `WifiError`; verify a later mutation can acquire the lock.
- [ ] Backend mutation is cancelled; verify a later mutation can acquire the lock.
- [ ] Backend raises an unexpected exception; verify the lock is still released and the
  exception propagates.
- [ ] Do not inspect private lock internals as the sole proof. Start a subsequent mutation
  and verify it completes.

### 7.19 Service test completion gate

- [ ] All adapter-selection branches are covered.
- [ ] Older refresh generations are proven unable to overwrite newer state.
- [ ] Every mutation is tested for success and typed failure.
- [ ] Cancellation and lock-release behavior are covered.
- [ ] Password clearing is proven on success, failure, cancellation, and refresh failure.
- [ ] Target at least 85% branch coverage for `services/wifi.py`.

## 8. Phase 4: `nmcli_core.py` tests

### 8.1 Executable resolution

- [ ] Explicit `nmcli_path` is used without consulting `PATH`.
- [ ] `shutil.which("nmcli")` result is used when no explicit path is supplied.
- [ ] Missing executable raises or reports `MISSING_NMCLI` as appropriate.
- [ ] Use `monkeypatch` rather than depending on the runner environment.

### 8.2 Process error translation

- [ ] `ProcessMissingExecutableError` maps to `MISSING_NMCLI`.
- [ ] `ProcessTimeoutError` maps to `TIMEOUT`.
- [ ] `ProcessNonZeroExitError` uses captured stderr and exit code.
- [ ] Nonzero failure without a result uses safe defaults.
- [ ] Verify the original process exception is retained as the cause.

### 8.3 Command-error classification matrix

Parameterize representative stderr text for every category:

- [ ] authorization denied
- [ ] missing secrets
- [ ] authentication rejected
- [ ] network unavailable
- [ ] DHCP/IP configuration failure
- [ ] NetworkManager unavailable
- [ ] Wi-Fi disabled
- [ ] radio/rfkill blocked
- [ ] unknown command failure

For each row:

- [ ] Verify case-insensitive matching.
- [ ] Verify the exact `ErrorCategory`.
- [ ] Verify exit code and operation are preserved.
- [ ] Verify technical details contain sanitized stderr.
- [ ] Verify blank stderr produces the fallback diagnostic.

### 8.4 `check_status()` outcomes

- [ ] Successful status includes availability, NetworkManager state, radio state, version,
  and executable details.
- [ ] Missing executable returns `MISSING_EXECUTABLE` without calling the runner.
- [ ] Authorization failure returns `UNAUTHORIZED`.
- [ ] Timeout, parse, and generic command failures return `UNAVAILABLE`.
- [ ] Technical details remain diagnostic but contain no secret values.

### 8.5 Radio parsing

- [ ] Software enabled and hardware enabled returns `ENABLED`.
- [ ] Software disabled and hardware enabled returns `DISABLED`.
- [ ] Hardware disabled returns `HARDWARE_BLOCKED` regardless of software value.
- [ ] Malformed field count raises a parse failure.
- [ ] Invalid boolean values raise a parse failure.

### 8.6 Radio mutation verification

- [ ] Enabling emits `radio wifi on`.
- [ ] Disabling emits `radio wifi off`.
- [ ] The radio state is re-read after the mutation.
- [ ] Matching state succeeds.
- [ ] Mismatched state raises `VERIFICATION_FAILURE` with expected and observed values.

### 8.7 Device parsing

- [ ] Parse connected, disconnected, unavailable, unmanaged, and unknown Wi-Fi states.
- [ ] Ignore Ethernet and other non-Wi-Fi devices.
- [ ] Convert blank and `--` connection names to `None`.
- [ ] Preserve escaped colons in connection names.
- [ ] Verify unmanaged devices have `managed=False`.
- [ ] Malformed rows fail visibly rather than being silently skipped.

### 8.8 Scan request

- [ ] Verify exact rescan command, interface, and scan timeout.
- [ ] Verify backend errors propagate as typed Wi-Fi errors.

### 8.9 Access-point parsing

- [ ] Parse active and inactive access points.
- [ ] Parse escaped SSID and BSSID fields.
- [ ] Parse open, WPA, WPA2, WPA3, mixed, enterprise, WEP, and unknown security.
- [ ] Parse known 2.4 GHz, 5 GHz, and 6 GHz channels.
- [ ] Preserve unknown frequency with `channel=None`.
- [ ] Omit rows with blank SSIDs according to the current visible-network policy.
- [ ] Parse blank signal as `None`.
- [ ] Reject out-of-range signal values.
- [ ] Reject malformed field counts.
- [ ] Verify `--rescan no` is always present so listing does not hide an implicit scan.

### 8.10 Core test completion gate

- [ ] Every error-classification category is covered.
- [ ] Status availability mapping is covered.
- [ ] Radio mutation verification is covered.
- [ ] Device and access-point parser failure paths are covered.
- [ ] Target at least 85% branch coverage for `nmcli_core.py`.

## 9. Phase 5: `process/runner.py` tests

### 9.1 Timeout validation

- [ ] Zero timeout raises `ValueError` before spawning a process.
- [ ] Negative timeout raises `ValueError` before spawning a process.
- [ ] Verify the error message is stable enough for callers but does not expose arguments.

### 9.2 Environment construction

- [ ] Verify `LC_ALL=C` and `LANG=C` are always present.
- [ ] Verify unrelated parent environment values are inherited.
- [ ] Verify explicit request environment values are merged.
- [ ] Decide and test whether request values may override locale values. Preserve the current
  intended contract explicitly.
- [ ] Do not mutate `os.environ` during construction.

### 9.3 Missing executable

- [ ] Invoke a guaranteed-nonexistent executable name.
- [ ] Verify `ProcessMissingExecutableError`.
- [ ] Verify the request is retained with a redacted command.
- [ ] Verify there is no fabricated `ProcessResult`.

### 9.4 Generic spawn failure

- [ ] Monkeypatch `asyncio.create_subprocess_exec` to raise `OSError` with synthetic text.
- [ ] Verify `ProcessSpawnError`.
- [ ] Verify any sensitive value present in the OS error text is redacted.
- [ ] Verify the original `OSError` is retained as the cause.

### 9.5 Standard input

- [ ] Verify ordinary stdin is delivered byte-for-byte to a child process.
- [ ] Verify `stdin=None` does not create unnecessary input behavior.
- [ ] Add a child that echoes stdin to stdout and stderr.

### 9.6 Sensitive stdin redaction

- [ ] With `sensitive_stdin=True`, verify echoed stdin is removed from stdout.
- [ ] Verify it is removed from stderr.
- [ ] Verify it is absent from exception text and representations.
- [ ] Verify the redaction marker is present.
- [ ] Verify empty sensitive stdin does not create an empty-string redaction bug.

### 9.7 Combined argument and stdin redaction

- [ ] Supply one sensitive argument and sensitive stdin in the same request.
- [ ] Echo both through stdout and stderr.
- [ ] Verify both values are removed independently.
- [ ] Verify non-sensitive neighboring text is preserved.

### 9.8 Invalid UTF-8

- [ ] Run a child that writes invalid UTF-8 bytes to stdout.
- [ ] Run a child that writes invalid UTF-8 bytes to stderr.
- [ ] Verify `ProcessSpawnError` is raised in each case.
- [ ] Verify no partially decoded unsafe output is returned.

### 9.9 Cancellation

- [ ] Start a long-running child process.
- [ ] Cancel the runner task after the child has started.
- [ ] Verify `ProcessCancelledError`.
- [ ] Verify `result.cancelled=True` and `result.timed_out=False`.
- [ ] Verify command metadata is redacted.
- [ ] Verify the child is no longer running after the test.
- [ ] Ensure cancellation does not leave a zombie process.

### 9.10 Terminate-to-kill escalation

- [ ] Use a controlled fake process object or a child that ignores termination.
- [ ] Verify `_stop` first requests termination.
- [ ] Verify it waits only for the bounded termination timeout.
- [ ] Verify it escalates to `kill` when required.
- [ ] Verify it waits for the killed process to be reaped.
- [ ] Keep this test deterministic and fast by using a fake process where practical.

### 9.11 Timeout result details

- [ ] Verify `timed_out=True` and `cancelled=False`.
- [ ] Verify the exit code is the real return code when available, otherwise `-1`.
- [ ] Verify stdout and stderr are empty for the current interrupted-result contract.
- [ ] Verify duration is nonnegative.
- [ ] Verify sensitive command values remain redacted.

### 9.12 Nonzero result and return-code edge cases

- [ ] Verify positive nonzero exits raise `ProcessNonZeroExitError`.
- [ ] Verify negative signal-style return codes are preserved.
- [ ] Verify successful exit code zero returns a result.
- [ ] Verify stdout and stderr remain separate.

### 9.13 Process test completion gate

- [ ] Missing executable, generic spawn failure, timeout, cancellation, invalid UTF-8, and
  nonzero exit are all covered.
- [ ] Termination escalation is covered deterministically.
- [ ] Argument and stdin secrets are proven absent from every diagnostic surface.
- [ ] Target at least 90% branch coverage for `process/runner.py`.

## 10. Phase 6: Textual workflow tests

UI code is currently omitted from the ordinary coverage calculation. Keep it omitted during
this phase unless counting it produces stable, meaningful metrics. The requirement is
behavioral coverage through Textual pilot tests, not an inflated percentage.

### 10.1 Main-screen states

- [ ] Loading/running operation message is visible.
- [ ] Backend error is visible.
- [ ] Warning is visible when no error exists.
- [ ] No-adapter state is visible.
- [ ] Disabled-radio state is visible.
- [ ] Hardware-blocked state is visible.
- [ ] Empty-network state is visible.
- [ ] Connected summary includes SSID/profile and addresses.
- [ ] Stale state is visibly marked.

### 10.2 Action enablement

- [ ] Connect is disabled when no network is available.
- [ ] Disconnect and details are disabled without an active connection.
- [ ] Mutation buttons are disabled while an operation is running.
- [ ] Wi-Fi button label reflects enabled versus disabled state.

### 10.3 Password dialog workflow

- [ ] Selecting a secured personal network opens the password dialog.
- [ ] Password is obscured by default.
- [ ] Show-password control changes display behavior without logging the value.
- [ ] Auto-connect control is forwarded correctly.
- [ ] Submit triggers one connection operation.
- [ ] Cancel triggers no backend mutation.
- [ ] Backend authentication failure displays the friendly error.

### 10.4 Open-network confirmation

- [ ] Selecting an open network shows an explicit warning.
- [ ] Confirm connects without a password.
- [ ] Cancel performs no mutation.

### 10.5 Unsupported-security behavior

- [ ] Enterprise, WEP, and unknown security show an unsupported dialog.
- [ ] No password dialog is shown.
- [ ] No backend connection method is called.

### 10.6 Hidden-network workflow

- [ ] Open hidden network submission forwards SSID and open security.
- [ ] Personal hidden network submission requires and forwards a password.
- [ ] Blank SSID validation is visible.
- [ ] Cancel performs no mutation.
- [ ] Failure displays the friendly summary and does not close silently.

### 10.7 Disconnect and radio confirmations

- [ ] Disconnect requires confirmation.
- [ ] Confirm invokes disconnect once.
- [ ] Cancel invokes nothing.
- [ ] Disabling Wi-Fi requires confirmation.
- [ ] Enabling Wi-Fi does not use a destructive confirmation unless the current design says
  otherwise.
- [ ] Failure is displayed explicitly.

### 10.8 Saved-network screen

- [ ] Profiles render with name, SSID, auto-connect, active status, and interface.
- [ ] Connect activates the selected UUID on the selected interface.
- [ ] Forget requires confirmation and deletes only the selected UUID.
- [ ] Auto-connect toggle sends the inverse current value.
- [ ] Empty selection shows a user-facing message.
- [ ] No selected adapter prevents connection with a visible explanation.
- [ ] Backend failures remain on screen and are not silently discarded.

### 10.9 Selection persistence and refresh

- [ ] Refresh preserves the selected logical network when it remains present.
- [ ] Selection falls back safely when the network disappears.
- [ ] Duplicate SSIDs with different security classes remain distinct rows.
- [ ] A table lookup failure does not crash the application or get hidden by a broad catch.

### 10.10 Keyboard and responsive behavior

- [ ] Test the documented keyboard shortcuts for refresh, connect, disconnect, hidden
  network, saved networks, details, Wi-Fi toggle, and quit where practical.
- [ ] Test a compact terminal width and verify the compact breakpoint class is active.
- [ ] Test a normal-width terminal and verify the normal layout is restored.

### 10.11 TUI test completion gate

- [ ] Every destructive action has confirm and cancel tests.
- [ ] Every major dialog has success and typed-failure tests.
- [ ] Unsupported security cannot reach the backend.
- [ ] Tests use only `FakeWifiBackend` or a deterministic derivative.
- [ ] No UI test touches real NetworkManager state.

## 11. Phase 7: coverage and CI integration

### 11.1 Review coverage configuration

- [ ] Keep branch coverage enabled.
- [ ] Do not exclude additional production modules to improve the percentage.
- [ ] Review the existing omissions for UI, `app.py`, `__main__.py`, and the backend protocol.
- [ ] Retain UI omissions only if pilot tests provide the meaningful behavioral verification
  and counting UI lines remains noisy or misleading.
- [ ] Document the rationale for every retained omission in `pyproject.toml` comments or the
  test documentation.

### 11.2 Raise the global gate only after tests exist

- [ ] Do not raise `--cov-fail-under` before the new test suite is stable.
- [ ] After completing Phases 1 through 5, measure total branch coverage.
- [ ] Raise the global threshold from 70% to a value below the measured stable result, leaving
  a small margin for harmless line movement while preventing major regressions.
- [ ] Preferred minimum target: 85% total measured coverage for the modules currently counted.
- [ ] Do not treat the global threshold as a substitute for the per-module completion gates.

### 11.3 Add optional per-module enforcement if maintainable

- [ ] Evaluate whether a small script can enforce minimum coverage for the five critical
  modules from coverage JSON output.
- [ ] If added, keep it simple, typed, tested, and checked into the repository.
- [ ] Suggested initial module gates:
  - `nmcli_mutations.py`: 90%
  - `nmcli_profiles.py`: 85%
  - `nmcli_core.py`: 85%
  - `services/wifi.py`: 85%
  - `process/runner.py`: 90%
- [ ] Do not add a fragile parser for human-readable coverage output.
- [ ] Prefer `coverage json` and structured JSON parsing.

### 11.4 CI matrix validation

- [ ] Run all tests on Python 3.11, 3.12, and 3.13.
- [ ] Ensure warnings remain errors on every Python version.
- [ ] Ensure the Textual pilot tests run in CI rather than being skipped because a declared
  dependency is missing.
- [ ] Ensure ordinary CI does not upload persistent package or coverage assets.
- [ ] Ensure release assets remain restricted to matching `v*` tags.

### 11.5 Quality gates

Run and require all of the following:

```bash
black --check .
ruff check .
mypy src/tui_wifi
pytest -m 'not real_network'
python -m build
```

- [ ] `python -m pip check` succeeds in a clean environment after installing the wheel.
- [ ] No warning appears in test, build, or package-install output.
- [ ] No new lint or typing suppression exists.
- [ ] No test is skipped unexpectedly.
- [ ] Any intentional skip has a precise, documented environmental reason.

## 12. Phase 8: review for test quality and false confidence

### 12.1 Mutation safety review

- [ ] Confirm every mutating backend command is asserted exactly.
- [ ] Confirm every mutating backend method re-verifies resulting state in tests.
- [ ] Confirm tests fail if verification calls are removed.
- [ ] Confirm tests fail if a command's interface, UUID, SSID, BSSID, or auto-connect value is
  incorrect.

### 12.2 Secret-safety review

- [ ] Search test output and failure messages for every synthetic credential value.
- [ ] Intentionally make one credential-redaction test fail locally and confirm pytest does
  not print the raw secret through object representations.
- [ ] Restore the test immediately after validation.
- [ ] Confirm passwords are cleared by the service on all exit paths.

### 12.3 Failure-visibility review

- [ ] Confirm no test accepts a generic successful return when post-operation state is wrong.
- [ ] Confirm typed errors preserve user-facing summary, guidance, operation, exit code, and
  safe technical details where applicable.
- [ ] Confirm unknown exceptions propagate rather than becoming a quiet fallback.
- [ ] Confirm scan failure remains a warning only because access-point listing continues and
  the final state is coherent.

### 12.4 Concurrency review

- [ ] Run concurrency tests repeatedly to detect nondeterminism.
- [ ] Use a local loop such as:

  ```bash
  for run in $(seq 1 50); do
      pytest -q tests/unit/test_service_concurrency.py || exit 1
  done
  ```

- [ ] Verify no pending-task, unclosed-loop, or resource warnings appear.
- [ ] Verify cancellation tests clean up child tasks and processes in `finally` blocks.

### 12.5 Test independence review

- [ ] Randomize or reverse test order locally and confirm the suite remains green.
- [ ] Confirm no test depends on another test's fake queues, global state, environment,
  working directory, or event loop.
- [ ] Confirm monkeypatches are scoped to the test.
- [ ] Confirm temporary files use pytest-provided temporary directories.

## 13. Documentation updates

- [ ] Update `README.md` only if developer commands or the enforced coverage threshold change.
- [ ] Update `docs/TODO.md` to mark this unit-test expansion complete when all release gates
  below pass.
- [ ] Add a brief testing architecture section to `docs/ARCHITECTURE.md` if new shared fake or
  concurrency infrastructure is introduced.
- [ ] Document why ordinary tests never invoke the host's real `nmcli` mutation commands.
- [ ] Do not reference any generated report or companion file that is not committed at the
  exact path named.

## 14. Final acceptance criteria

This TODO is complete only when all of the following are true:

- [ ] All Phase 1 mutation tests are implemented and green.
- [ ] All Phase 2 profile tests are implemented and green.
- [ ] All Phase 3 service and concurrency tests are implemented and green.
- [ ] All Phase 4 core backend tests are implemented and green.
- [ ] All Phase 5 process tests are implemented and green.
- [ ] The major Phase 6 Textual workflows are implemented and green.
- [ ] Python 3.11, 3.12, and 3.13 CI jobs pass.
- [ ] Black passes with no formatting differences.
- [ ] Ruff passes with the complete rule set and no suppressions.
- [ ] Mypy passes in strict mode with no module exemptions.
- [ ] Pytest emits no warnings.
- [ ] The wheel and source distribution build and install cleanly.
- [ ] The critical module coverage gates are met or exceeded.
- [ ] Total measured coverage reaches the stable threshold selected in Phase 7.
- [ ] No test touches real Wi-Fi hardware or changes the host's network state.
- [ ] No credential appears in command metadata, captured output, exceptions, logs, or pytest
  failure output.
- [ ] No unsafe fallback, silent failure, unverified success, stale-state overwrite, leaked
  process, leaked task, or unreleased mutation lock remains untested.
- [ ] `docs/UNIT_TESTS1_TODO.md` is updated with completed checkboxes as implementation
  progresses.

## 15. Recommended implementation order

Implement in this order to maximize risk reduction and minimize helper churn:

1. Phase 0 shared typed fixtures and deterministic asynchronous controls.
2. Phase 1 `nmcli_mutations.py` tests.
3. Phase 2 `nmcli_profiles.py` tests.
4. Phase 4 `nmcli_core.py` tests.
5. Phase 3 ordinary `WifiService` tests.
6. Phase 3 service concurrency, cancellation, and serialization tests.
7. Phase 5 process runner edge-case and credential tests.
8. Phase 6 Textual pilot tests.
9. Phase 7 coverage gates and CI threshold updates.
10. Phase 8 final safety, nondeterminism, and test-independence review.
11. Documentation updates and final acceptance validation.
