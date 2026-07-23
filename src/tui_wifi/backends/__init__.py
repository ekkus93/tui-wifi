# Copyright (c) 2026 Phillip Chin
"""Provide the backends package."""

from tui_wifi.backends.base import WifiBackend
from tui_wifi.backends.nmcli import NmcliWifiBackend

__all__ = ["NmcliWifiBackend", "WifiBackend"]
