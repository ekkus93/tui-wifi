"""Provide nmcli core functionality."""

from __future__ import annotations

import shutil

from tui_wifi.backends.parsing import (
    frequency_to_channel,
    parse_bool,
    parse_device_state,
    parse_nm_state,
    parse_optional_int,
    parse_security,
    parse_signal,
    split_escaped,
)
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import (
    AccessPoint,
    BackendAvailability,
    BackendStatus,
    DeviceState,
    WifiDevice,
    WifiRadioState,
)
from tui_wifi.process import (
    ProcessMissingExecutable,
    ProcessNonZeroExit,
    ProcessRequest,
    ProcessRunner,
    ProcessTimeout,
)


class NmcliCore:
    """Represent NmcliCore."""

    STATUS_TIMEOUT = 5.0
    QUERY_TIMEOUT = 10.0
    SCAN_TIMEOUT = 20.0
    CONNECT_TIMEOUT = 50.0
    MUTATION_TIMEOUT = 20.0
    PROFILE_DETAIL_LIMIT = 128

    def __init__(self, runner: ProcessRunner, nmcli_path: str | None = None) -> None:
        """Initialize the instance."""
        self._runner = runner
        self._nmcli_path = nmcli_path

    def _resolve_nmcli(self) -> str:
        """Perform resolve nmcli."""
        path = self._nmcli_path or shutil.which("nmcli")
        if not path:
            raise WifiError(ErrorCategory.MISSING_NMCLI)
        return path

    async def _run(
        self,
        args: tuple[str, ...],
        *,
        timeout_seconds: float,
        sensitive_arg_indexes: frozenset[int] = frozenset(),
    ) -> str:
        """Perform run."""
        request = ProcessRequest(
            executable=self._resolve_nmcli(),
            args=args,
            timeout=timeout_seconds,
            sensitive_arg_indexes=sensitive_arg_indexes,
        )
        try:
            result = await self._runner.run(request)
        except ProcessMissingExecutable as exc:
            raise WifiError(ErrorCategory.MISSING_NMCLI, operation="nmcli") from exc
        except ProcessTimeout as exc:
            raise WifiError(ErrorCategory.TIMEOUT, operation="nmcli") from exc
        except ProcessNonZeroExit as exc:
            stderr = exc.result.stderr if exc.result else ""
            exit_code = exc.result.exit_code if exc.result else None
            raise self._classify_command_error(stderr, exit_code, "nmcli") from exc
        return result.stdout

    @staticmethod
    def _classify_command_error(stderr: str, exit_code: int | None, operation: str) -> WifiError:
        """Perform classify command error."""
        lower = stderr.lower()
        if any(
            token in lower
            for token in ("not authorized", "permission denied", "insufficient privileges")
        ):
            category = ErrorCategory.AUTHORIZATION_DENIED
        elif any(
            token in lower
            for token in ("secrets were required", "no secrets", "property is missing")
        ):
            category = ErrorCategory.MISSING_SECRETS
        elif any(
            token in lower for token in ("wrong password", "authentication", "802.1x supplicant")
        ):
            category = ErrorCategory.AUTHENTICATION_REJECTED
        elif any(
            token in lower
            for token in ("no network with ssid", "not found", "network could not be found")
        ):
            category = ErrorCategory.NETWORK_UNAVAILABLE
        elif "dhcp" in lower or "ip configuration" in lower:
            category = ErrorCategory.IP_CONFIGURATION_FAILED
        elif any(
            token in lower
            for token in ("networkmanager is not running", "could not connect: no such file")
        ):
            category = ErrorCategory.NETWORK_MANAGER_UNAVAILABLE
        elif "wifi is disabled" in lower or "wireless is disabled" in lower:
            category = ErrorCategory.WIFI_DISABLED
        elif "rfkill" in lower or "hardware switch" in lower:
            category = ErrorCategory.RADIO_BLOCKED
        else:
            category = ErrorCategory.COMMAND_FAILURE
        return WifiError(
            category,
            technical_details=stderr.strip() or "nmcli returned a nonzero exit status",
            exit_code=exit_code,
            operation=operation,
        )

    async def check_status(self) -> BackendStatus:
        """Perform check status."""
        try:
            executable = self._resolve_nmcli()
        except WifiError:
            return BackendStatus(BackendAvailability.MISSING_EXECUTABLE)
        try:
            version = (await self._run(("--version",), timeout_seconds=self.STATUS_TIMEOUT)).strip()
            state_output = await self._run(
                ("-t", "-e", "yes", "-f", "STATE", "general"),
                timeout_seconds=self.STATUS_TIMEOUT,
            )
            nm_state = parse_nm_state(state_output.strip())
            radio = await self.get_wifi_radio_state()
            return BackendStatus(
                BackendAvailability.AVAILABLE,
                network_manager_state=nm_state,
                wifi_radio=radio,
                nmcli_version=version,
                technical_details=f"nmcli={executable}",
            )
        except WifiError as exc:
            availability = (
                BackendAvailability.UNAUTHORIZED
                if exc.category == ErrorCategory.AUTHORIZATION_DENIED
                else BackendAvailability.UNAVAILABLE
            )
            return BackendStatus(availability, technical_details=exc.diagnostic_text())

    async def get_wifi_radio_state(self) -> WifiRadioState:
        """Perform get wifi radio state."""
        output = await self._run(
            ("-t", "-e", "yes", "-f", "WIFI,WIFI-HW", "radio"),
            timeout_seconds=self.STATUS_TIMEOUT,
        )
        software_text, hardware_text = split_escaped(output.strip(), 2)
        software_enabled = parse_bool(software_text)
        hardware_enabled = parse_bool(hardware_text)
        if not hardware_enabled:
            return WifiRadioState.HARDWARE_BLOCKED
        return WifiRadioState.ENABLED if software_enabled else WifiRadioState.DISABLED

    async def set_wifi_radio_state(self, enabled: bool) -> WifiRadioState:
        """Perform set wifi radio state."""
        await self._run(
            ("radio", "wifi", "on" if enabled else "off"),
            timeout_seconds=self.MUTATION_TIMEOUT,
        )
        state = await self.get_wifi_radio_state()
        expected = WifiRadioState.ENABLED if enabled else WifiRadioState.DISABLED
        if state != expected:
            raise WifiError(
                ErrorCategory.VERIFICATION_FAILURE,
                technical_details=f"expected radio={expected.value}, observed={state.value}",
                operation="set_wifi_radio_state",
            )
        return state

    async def list_wifi_devices(self) -> tuple[WifiDevice, ...]:
        """Perform list wifi devices."""
        output = await self._run(
            ("-t", "-e", "yes", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"),
            timeout_seconds=self.QUERY_TIMEOUT,
        )
        devices: list[WifiDevice] = []
        for line in output.splitlines():
            if not line:
                continue
            interface, device_type, state_text, connection = split_escaped(line, 4)
            if device_type not in {"wifi", "802-11-wireless"}:
                continue
            state = parse_device_state(state_text)
            devices.append(
                WifiDevice(
                    interface=interface,
                    state=state,
                    managed=state != DeviceState.UNMANAGED,
                    active_connection=None if connection in {"", "--"} else connection,
                ),
            )
        return tuple(devices)

    async def request_scan(self, interface: str) -> None:
        """Perform request scan."""
        await self._run(
            ("device", "wifi", "rescan", "ifname", interface),
            timeout_seconds=self.SCAN_TIMEOUT,
        )

    async def list_access_points(self, interface: str) -> tuple[AccessPoint, ...]:
        """Perform list access points."""
        output = await self._run(
            (
                "-t",
                "-e",
                "yes",
                "-f",
                "IN-USE,SSID,BSSID,SIGNAL,FREQ,SECURITY",
                "device",
                "wifi",
                "list",
                "ifname",
                interface,
                "--rescan",
                "no",
            ),
            timeout_seconds=self.QUERY_TIMEOUT,
        )
        access_points: list[AccessPoint] = []
        for line in output.splitlines():
            if not line:
                continue
            active, ssid, bssid, signal_text, frequency_text, security_text = split_escaped(line, 6)
            if not ssid:
                continue
            frequency = parse_optional_int(frequency_text)
            access_points.append(
                AccessPoint(
                    ssid=ssid.encode("utf-8", errors="surrogateescape"),
                    display_ssid=ssid,
                    bssid=bssid,
                    signal=parse_signal(signal_text),
                    frequency=frequency,
                    channel=frequency_to_channel(frequency),
                    security=parse_security(security_text),
                    active=active.strip() in {"*", "yes"},
                    device=interface,
                ),
            )
        return tuple(access_points)
