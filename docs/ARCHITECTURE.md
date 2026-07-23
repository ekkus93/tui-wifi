# Architecture

## Layers

`tui-wifi` has six intentionally separate layers:

1. Textual screens, dialogs, and widgets render immutable application snapshots.
2. `WifiService` owns adapter selection, refresh generations, mutation serialization,
   and last-valid-state preservation.
3. `WifiBackend` is the backend-independent operation contract.
4. `NmcliWifiBackend` constructs and verifies NetworkManager operations.
5. `ProcessRunner` executes bounded asynchronous subprocesses without a shell.
6. Domain models and structured errors carry data between layers.

The UI never parses `nmcli` output or constructs commands. The backend never imports
Textual.

## Process and parsing safety

Every command uses an executable plus an argument tuple. `shell=True` is prohibited.
The process runner forces `LC_ALL=C`, captures stdout and stderr separately, applies a
bounded timeout, terminates and reaps children, and retains redacted diagnostics.

Query commands select explicit fields and use `nmcli -t -e yes`. The parser implements
NetworkManager's backslash escaping for colons and backslashes. Wrong field counts,
dangling escapes, malformed integers, invalid UUIDs, and invalid addresses are parse
failures rather than empty data.

## State model

`ApplicationSnapshot` is an atomic view of backend status, radio state, adapters,
visible network groups, saved profiles, active connection, operation, and errors.
Refreshes have monotonically increasing generations. A late refresh cannot overwrite a
newer snapshot. If a refresh fails, the previous valid state remains visible and is
marked stale.

Only one mutating operation runs at a time. Connection, disconnection, radio, deletion,
and auto-connect operations are verified by reading NetworkManager state afterward.
Command exit status alone is not considered success.

## Network grouping

Access points are grouped only when SSID and normalized security class match. Open and
secured networks with the same SSID remain distinct. The connected network sorts first,
then saved supported networks, other supported networks, and unsupported networks.
Each group retains its member BSSIDs and compatible saved-profile UUIDs.

## Credential lifecycle

Password widgets are obscured by default and cleared when dismissed. `SecretValue`
redacts normal string representations. Sensitive process arguments are replaced in
recorded command metadata, and stderr/stdout redaction applies before diagnostics are
exposed. Passwords are not stored in application snapshots or configuration files.
NetworkManager remains responsible for persistent secrets.

## Testing architecture

Ordinary automated tests never invoke the host's real NetworkManager mutation commands.
`FakeProcessRunner` validates exact executable and argument ordering while retaining the
full `ProcessRequest` for timeout and secret-index assertions. `FakeWifiBackend` and
purpose-built deterministic derivatives provide coherent state, typed failures, and
explicit `asyncio.Event` barriers for refresh-generation and mutation-lock tests.

Tests are organized around behavior and risk rather than only line coverage:

- backend mutation tests assert the exact command and then prove state verification;
- profile and core tests feed strict machine-readable `nmcli` fixtures;
- service tests prove stale-result rejection, password clearing, cancellation, and lock release;
- process tests prove child cleanup, UTF-8 rejection, and credential redaction;
- Textual pilot tests verify dialogs, confirmations, saved profiles, shortcuts, and layout.

Coverage.py JSON is checked by `scripts/check_critical_coverage.py`. The global floor
prevents broad regression, while per-module branch floors protect the five
safety-critical modules from being hidden by high coverage elsewhere. UI modules remain
outside the numeric metric because framework-driven lifecycle lines are noisy; their
behavior is verified directly through Textual's pilot harness.

## Why `nmcli` first

`nmcli` is widely available with NetworkManager and gives users and developers a command
surface they can independently reproduce. The backend protocol keeps D-Bus viable later;
a D-Bus implementation can replace the adapter without changing the service or TUI.
