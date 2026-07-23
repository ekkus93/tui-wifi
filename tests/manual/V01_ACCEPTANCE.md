# Version 0.1 Manual Acceptance Record

Do not include Wi-Fi passwords or unredacted private identifiers.

## Environment

- Distribution/version:
- NetworkManager version:
- Python version:
- Terminal emulator:
- Wi-Fi adapter/driver:
- Test date:
- Tester:

## Core workflows

- [ ] Starts as a normal user
- [ ] Nearby networks and current connection are accurate
- [ ] Rescan
- [ ] WPA2 personal connection
- [ ] WPA3 personal connection, when available
- [ ] Open test network
- [ ] Saved credential reconnect
- [ ] Wrong-password error
- [ ] Disconnect
- [ ] Forget exactly one saved profile
- [ ] Hidden open/personal network
- [ ] Wi-Fi disable/enable

## Edge and security checks

- [ ] rfkill block
- [ ] Adapter removal/reinsertion
- [ ] Multiple adapters
- [ ] Duplicate SSID/BSSIDs
- [ ] Network disappears during connection
- [ ] Controlled DHCP failure
- [ ] Terminal resize and SSH
- [ ] NetworkManager restart
- [ ] No password in normal/debug logs or failure details
- [ ] No root-owned project files
- [ ] No direct network configuration file changes

## Result

- Overall pass/fail:
- Redacted notes:
