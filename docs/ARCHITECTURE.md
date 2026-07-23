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

## Why `nmcli` first

`nmcli` is widely available with NetworkManager and gives users and developers a command
surface they can independently reproduce. The backend protocol keeps D-Bus viable later;
a D-Bus implementation can replace the adapter without changing the service or TUI.
