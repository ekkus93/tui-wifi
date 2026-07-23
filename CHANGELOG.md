# Changelog

## 0.1.0 - 2026-07-22

- Added a Textual Wi-Fi TUI for NetworkManager-managed Linux systems.
- Added strict `nmcli` parsing, asynchronous bounded subprocess execution, and
  credential-safe diagnostics.
- Added visible, saved, and hidden network workflows; radio control; details;
  coherent state refresh; fake backend; tests; CI/CD; and project documentation.
- Added tagged-release automation that persists wheel and source assets only for a
  matching `v<version>` tag.
- Hardened subprocess diagnostics so credential-bearing arguments are redacted even if
  a child process echoes them to stdout or stderr.
- Added Python 3.10 support and CI coverage across Python 3.10 through 3.13.
- Added compatibility for NetworkManager 1.36 indexed IP properties and literal IPv6
  values in terse `nmcli` output.
- Added compatibility for NetworkManager 1.36 access-point frequencies that include an
  explicit `MHz` unit.
- Renamed the installed command to `tui-wifi` to match the project name.
- Hardware acceptance validation remains pending and is tracked in
  `tests/manual/V01_ACCEPTANCE.md`.
