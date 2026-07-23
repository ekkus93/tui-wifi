# Security

## Threat model

The primary risks are credential disclosure, shell injection, unintended privileged
execution, deleting the wrong profile, security downgrade, and reporting success after a
partial networking failure.

## Controls

- The TUI runs as the normal user. It never asks for or stores a sudo password.
- NetworkManager and Polkit authorize privileged changes.
- Subprocesses use argument arrays and never a shell.
- No direct writes are made to NetworkManager, `wpa_supplicant`, or distribution network
  configuration files.
- Passwords are obscured, ephemeral, and redacted from string representations,
  diagnostics, logs, test snapshots, and process metadata.
- Unsupported or uncertain security is rejected. The program never retries as open or
  with weaker security.
- Saved profiles are changed or deleted strictly by UUID.
- Mutations are followed by state verification.
- Errors preserve redacted stderr and stable categories; they are not converted into
  empty or successful states.

## Debug logs

`--debug` writes a bounded rotating log under the XDG state directory. Debug mode does
not weaken redaction. Do not publish logs without reviewing network names, addresses,
and other environment-specific metadata.

## Reporting vulnerabilities

Open a private security advisory in the GitHub repository when possible. Do not include
real Wi-Fi passwords, private certificates, or unredacted debug logs in public issues.

## `nmcli` process visibility

For a newly created personal Wi-Fi profile, the documented `nmcli device wifi connect`
interface accepts the password as an argument. `tui-wifi` redacts that argument from all
application-owned diagnostics, but a sufficiently privileged local process inspector may
observe the transient command line while `nmcli` runs. A future D-Bus backend can remove
this limitation. Saved-profile activation does not resend a password through the TUI.
