# nmcli fixtures

Fixture-oriented parser tests use synthetic values so CI never queries the runner's real
NetworkManager instance. Add new fixtures only after removing private SSIDs, BSSIDs,
addresses, and all credentials.
