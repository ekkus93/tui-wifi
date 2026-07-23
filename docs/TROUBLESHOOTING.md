# Troubleshooting

## `nmcli` is missing

Install NetworkManager's command-line package for your distribution. Confirm `nmcli
--version` works, then restart `tui-wifi`.

## NetworkManager is unavailable

Confirm the NetworkManager service is installed and running. Systems managed only by
ConnMan, direct `iwd`, or raw `wpa_supplicant` are not supported in version 0.1.

## No adapter is found

Check `nmcli device status` and the kernel driver/firmware for the wireless adapter. An
unmanaged adapter must be configured for NetworkManager before `tui-wifi` can use it.

## Wi-Fi is disabled or blocked

Use the in-app Wi-Fi toggle for a software-disabled radio. For a blocked radio, inspect
`rfkill list` and clear the software block or hardware switch. The application will not
pretend a hardware block was cleared.

## Authorization denied

The TUI must not be run wholesale as root. Check the user's Polkit authorization for
NetworkManager operations.

## Incorrect password or missing secret

Retry and enter the password. `tui-wifi` does not repeatedly submit a rejected saved
secret or automatically delete the saved profile.

## Connected but no IP address

This usually indicates DHCP or IP configuration failure rather than a rejected password.
Check the access point's DHCP service and whether the network has exhausted its address
pool.

## Captive portals

`tui-wifi` can join an open or personal Wi-Fi network, but it does not automate hotel,
airport, or café portal logins. Open a browser after connecting.

## Enterprise Wi-Fi

WPA-Enterprise, PEAP, TTLS, EAP-TLS, and certificate enrollment are deliberately
unsupported in version 0.1.

## Redacted debug logs

Run `tui-wifi --debug`. Logs are placed under `$XDG_STATE_HOME/tui-wifi/debug.log` or
`~/.local/state/tui-wifi/debug.log`. Passwords should be redacted, but review private
network names and addresses before sharing.
