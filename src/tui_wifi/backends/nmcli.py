from __future__ import annotations

from tui_wifi.backends.nmcli_core import NmcliCore
from tui_wifi.backends.nmcli_mutations import NmcliMutationsMixin
from tui_wifi.backends.nmcli_profiles import NmcliProfilesMixin


class NmcliWifiBackend(NmcliMutationsMixin, NmcliProfilesMixin, NmcliCore):
    """NetworkManager backend using strict, machine-readable nmcli operations."""

