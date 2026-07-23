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
- Hardware acceptance validation remains pending and is tracked in
  `tests/manual/V01_ACCEPTANCE.md`.
