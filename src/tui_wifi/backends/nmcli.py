from __future__ import annotations

from tui_wifi.backends.nmcli_mutations import NmcliMutationsMixin


class NmcliWifiBackend(NmcliMutationsMixin):
    """NetworkManager backend using strict, machine-readable nmcli operations."""
