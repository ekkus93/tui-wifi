"""Apply the final known strict-lint fixes."""

from __future__ import annotations

from pathlib import Path


def replace_exact(path: str, old: str, new: str, *, expected: int = 1) -> None:
    """Replace an exact string and fail if the repository differs from expectations."""
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        message = f"{path}: expected {expected} occurrences, found {count}: {old!r}"
        raise RuntimeError(message)
    target.write_text(text.replace(old, new), encoding="utf-8")


def write(path: str, content: str) -> None:
    """Write one complete UTF-8 source file."""
    Path(path).write_text(content, encoding="utf-8")


def repair_source_calls() -> None:
    """Align all source call sites with keyword-only boolean APIs."""
    replace_exact(
        "src/tui_wifi/backends/fake.py",
        'WifiDevice("wlan0", DeviceState.DISCONNECTED, True)',
        'WifiDevice(interface="wlan0", state=DeviceState.DISCONNECTED, managed=True)',
    )
    replace_exact(
        "src/tui_wifi/backends/nmcli_mutations.py",
        "await self.set_profile_autoconnect(active.uuid, False)",
        "await self.set_profile_autoconnect(active.uuid, enabled=False)",
        expected=2,
    )
    replace_exact(
        "src/tui_wifi/services/wifi.py",
        "await self.backend.set_wifi_radio_state(enabled)",
        "await self.backend.set_wifi_radio_state(enabled=enabled)",
    )
    replace_exact(
        "src/tui_wifi/services/wifi.py",
        "await self.backend.set_profile_autoconnect(uuid, enabled)",
        "await self.backend.set_profile_autoconnect(uuid, enabled=enabled)",
    )
    replace_exact(
        "src/tui_wifi/ui/screens/saved.py",
        "self._set_autoconnect(profile_uuid, not profile.autoconnect)",
        "self._set_autoconnect(profile_uuid, enabled=not profile.autoconnect)",
    )
    replace_exact(
        "src/tui_wifi/ui/screens/saved.py",
        "await self.service.set_profile_autoconnect(uuid, enabled)",
        "await self.service.set_profile_autoconnect(uuid, enabled=enabled)",
    )


def write_cli_tests() -> None:
    """Write CLI tests without local imports or type suppressions."""
    write(
        "tests/unit/test_cli.py",
        '''"""Verify command-line behavior."""

from __future__ import annotations

import pytest

from tests.assertions import verify
from tui_wifi import cli


def test_cli_interface_and_debug_options() -> None:
    """Verify interface, debug, and mouse command-line options."""
    args = cli.build_parser().parse_args(["--interface", "wlan1", "--debug", "--no-mouse"])
    verify(args.interface == "wlan1")
    verify(args.debug is True)
    verify(args.no_mouse is True)


def test_cli_rejects_unknown_option() -> None:
    """Verify unknown command-line options fail visibly."""
    with pytest.raises(SystemExit) as caught:
        cli.build_parser().parse_args(["--not-real"])
    verify(caught.value.code != 0)


def test_main_runs_app_and_propagates_mouse_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify main constructs the app with resolved command-line settings."""
    calls: dict[str, object] = {}

    class FakeApp:
        """Record construction and run arguments for the CLI test."""

        def __init__(self, **kwargs: object) -> None:
            """Record application constructor arguments."""
            calls["kwargs"] = kwargs

        def run(self, *, mouse: bool = True) -> None:
            """Record the resolved mouse setting."""
            calls["mouse"] = mouse

    monkeypatch.setattr(cli, "WifiTuiApp", FakeApp)

    verify(cli.main(["--interface", "wlan0", "--no-mouse"]) == 0)
    verify(calls["mouse"] is False)
    verify(
        calls["kwargs"]
        == {
            "preferred_interface": "wlan0",
            "mouse_enabled": False,
            "startup_warning": None,
        },
    )
''',
    )


def write_service_tests() -> None:
    """Write service tests with explicit imports and keyword arguments."""
    write(
        "tests/unit/test_service.py",
        '''"""Verify Wi-Fi service behavior."""

from __future__ import annotations

import asyncio

import pytest

from tests.assertions import verify
from tui_wifi.backends.base import DisconnectRequest, SavedProfileRequest
from tui_wifi.backends.fake import FakeWifiBackend
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import (
    AccessPoint,
    DeviceState,
    NetworkGroup,
    SavedProfile,
    SecurityClass,
    WifiDevice,
)
from tui_wifi.secrets import SecretValue
from tui_wifi.services.wifi import WifiService


def sample_ap() -> AccessPoint:
    """Return a representative secured access point."""
    return AccessPoint(
        ssid=b"Home",
        display_ssid="Home",
        bssid="00:11:22:33:44:55",
        signal=88,
        frequency=2412,
        channel=1,
        security=SecurityClass.WPA2_PERSONAL,
        active=False,
        device="wlan0",
    )


def test_startup_connect_disconnect_and_radio() -> None:
    """Verify the primary startup, connection, and radio workflow."""

    async def scenario() -> None:
        """Run the asynchronous service workflow."""
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (sample_ap(),)
        service = WifiService(backend)
        snapshot = await service.startup()
        verify(snapshot.selected_device == "wlan0")
        verify(snapshot.networks[0].display_ssid == "Home")
        password = SecretValue("test-only-password")
        connected = await service.connect_network(snapshot.networks[0], password=password)
        verify(connected.active_connection is not None)
        verify(password.reveal() == "")
        disconnected = await service.disconnect()
        verify(disconnected.active_connection is None)
        disabled = await service.set_wifi_enabled(enabled=False)
        verify(disabled.status.wifi_radio.value == "disabled")

    asyncio.run(scenario())


def test_refresh_failure_preserves_last_valid_state() -> None:
    """Verify failed refreshes preserve the last coherent state."""

    async def scenario() -> None:
        """Run a refresh that fails after a valid startup."""
        backend = FakeWifiBackend()
        backend.access_points["wlan0"] = (sample_ap(),)
        service = WifiService(backend)
        first = await service.startup()
        backend.failures["list_access_points"] = WifiError(ErrorCategory.COMMAND_FAILURE)
        second = await service.refresh()
        verify(second.networks == first.networks)
        verify(second.stale is True)
        verify(second.error)

    asyncio.run(scenario())


def test_explicit_missing_interface_is_visible() -> None:
    """Verify a requested missing interface produces a visible error."""

    async def scenario() -> None:
        """Start a service with an unavailable preferred interface."""
        service = WifiService(FakeWifiBackend(), preferred_interface="missing0")
        snapshot = await service.startup()
        verify(snapshot.error == "Wi-Fi interface 'missing0' is unavailable.")

    asyncio.run(scenario())


def test_unsupported_connection_is_rejected_before_backend() -> None:
    """Verify unsupported security never reaches the backend."""

    async def scenario() -> None:
        """Attempt an unsupported enterprise connection."""
        backend = FakeWifiBackend()
        service = WifiService(backend)
        await service.startup()
        group = NetworkGroup(
            identity="corp",
            display_ssid="Corp",
            security=SecurityClass.ENTERPRISE,
            signal=80,
            connected=False,
            supported=False,
        )
        with pytest.raises(WifiError) as caught:
            await service.connect_network(group)
        verify(caught.value.category == ErrorCategory.UNSUPPORTED_SECURITY)
        verify(not any(call[0] == "connect_visible_network" for call in backend.calls))

    asyncio.run(scenario())


def test_fake_backend_saved_profile_workflows() -> None:
    """Verify saved-profile activation, update, deletion, and disconnect."""

    async def scenario() -> None:
        """Run saved-profile operations against the fake backend."""
        backend = FakeWifiBackend()
        profile = SavedProfile(
            name="Home",
            uuid="00000000-0000-0000-0000-000000000099",
            ssid="Home",
            interface_name=None,
            autoconnect=True,
            security=SecurityClass.WPA2_PERSONAL,
        )
        backend.profiles = (profile,)
        active = await backend.activate_saved_profile(
            SavedProfileRequest(profile.uuid, "wlan0"),
        )
        verify(active.uuid == profile.uuid)
        changed = await backend.set_profile_autoconnect(profile.uuid, enabled=False)
        verify(changed.autoconnect is False)
        await backend.delete_saved_profile(profile.uuid)
        verify(backend.profiles == ())
        await backend.disconnect(DisconnectRequest("wlan0", active.uuid))
        verify(await backend.get_connection_details() is None)

    asyncio.run(scenario())


def test_multiple_idle_adapters_require_explicit_selection() -> None:
    """Verify multiple idle adapters require an explicit interface choice."""

    async def scenario() -> None:
        """Start with two managed disconnected adapters."""
        backend = FakeWifiBackend()
        backend.devices = (
            WifiDevice(interface="wlan0", state=DeviceState.DISCONNECTED, managed=True),
            WifiDevice(interface="wlan1", state=DeviceState.DISCONNECTED, managed=True),
        )
        snapshot = await WifiService(backend).startup()
        verify(snapshot.error is not None)
        verify("Multiple Wi-Fi adapters" in snapshot.error)

    asyncio.run(scenario())
''',
    )


def write_process_tests() -> None:
    """Write process tests with explicit credential names and exception matching."""
    write(
        "tests/unit/test_process.py",
        '''"""Verify asynchronous process execution."""

from __future__ import annotations

import asyncio
import sys

import pytest

from tests.assertions import verify
from tui_wifi.process import (
    AsyncProcessRunner,
    ProcessNonZeroExitError,
    ProcessRequest,
    ProcessTimeoutError,
)

_EXPECTED_EXIT_CODE = 7


def test_process_success_and_no_shell_interpretation() -> None:
    """Verify arguments are passed without shell interpretation."""

    async def scenario() -> None:
        """Run a successful child process."""
        result = await AsyncProcessRunner().run(
            ProcessRequest(
                sys.executable,
                ("-c", "import sys; print(sys.argv[1])", "$(touch /tmp/not-run)"),
                timeout=5,
            ),
        )
        verify(result.stdout.strip() == "$(touch /tmp/not-run)")
        verify(result.exit_code == 0)

    asyncio.run(scenario())


def test_process_nonzero_keeps_stdout_and_stderr_separate() -> None:
    """Verify unsuccessful output streams remain separate."""

    async def scenario() -> None:
        """Run a child process that exits unsuccessfully."""
        request = ProcessRequest(
            sys.executable,
            ("-c", "import sys; print('out'); print('err', file=sys.stderr); raise SystemExit(7)"),
            timeout=5,
        )
        with pytest.raises(ProcessNonZeroExitError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.result is not None)
        verify(caught.value.result.stdout.strip() == "out")
        verify(caught.value.result.stderr.strip() == "err")
        verify(caught.value.result.exit_code == _EXPECTED_EXIT_CODE)

    asyncio.run(scenario())


def test_process_output_redacts_sensitive_argument_values() -> None:
    """Verify echoed sensitive arguments are removed from all diagnostics."""

    async def scenario() -> None:
        """Run a child process that echoes a protected argument."""
        test_credential = "credential-that-must-not-leak"
        request = ProcessRequest(
            sys.executable,
            (
                "-c",
                "import sys; print(sys.argv[1]); print(sys.argv[1], file=sys.stderr); "
                "raise SystemExit(9)",
                test_credential,
            ),
            timeout=5,
            sensitive_arg_indexes=frozenset({2}),
        )
        with pytest.raises(ProcessNonZeroExitError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.result is not None)
        verify(test_credential not in caught.value.result.stdout)
        verify(test_credential not in caught.value.result.stderr)
        verify("<redacted>" in caught.value.result.stdout)
        verify("<redacted>" in caught.value.result.stderr)
        verify(test_credential not in repr(caught.value.result.command))

    asyncio.run(scenario())


def test_process_timeout_redacts_sensitive_metadata() -> None:
    """Verify timeout diagnostics retain no protected argument value."""

    async def scenario() -> None:
        """Run a child process beyond its deadline."""
        request = ProcessRequest(
            sys.executable,
            ("-c", "import time; time.sleep(10)", "test-credential-value"),
            timeout=0.02,
            sensitive_arg_indexes=frozenset({2}),
        )
        with pytest.raises(ProcessTimeoutError) as caught:
            await AsyncProcessRunner().run(request)
        verify(caught.value.result is not None)
        verify("test-credential-value" not in repr(caught.value.result.command))

    asyncio.run(scenario())


def test_sensitive_argument_indexes_must_be_valid() -> None:
    """Verify invalid sensitive argument indexes fail immediately."""
    with pytest.raises(ValueError, match="out of range"):
        ProcessRequest("command", ("only",), sensitive_arg_indexes=frozenset({1}))
''',
    )


def write_parsing_tests() -> None:
    """Write parser tests without local imports."""
    write(
        "tests/unit/test_parsing.py",
        '''"""Verify strict NetworkManager output parsing."""

from __future__ import annotations

import pytest

from tests.assertions import verify
from tui_wifi.backends.parsing import (
    frequency_to_channel,
    parse_bool,
    parse_device_state,
    parse_ip_values,
    parse_nm_state,
    parse_optional_int,
    parse_security,
    parse_signal,
    split_escaped,
    validate_uuid,
)
from tui_wifi.errors import ErrorCategory, WifiError
from tui_wifi.models import DeviceState, NetworkManagerState, SecurityClass

_CHANNEL_14 = 14
_CHANNEL_36 = 36
_SIGNAL_75 = 75
_FREQUENCY_5180 = 5180


def test_split_escaped_colon_and_backslash() -> None:
    """Verify escaped separators and backslashes are decoded."""
    verify(
        split_escaped(r"Cafe\:West:path\\name::", 4)
        == [
            "Cafe:West",
            r"path\name",
            "",
            "",
        ],
    )


def test_split_escaped_rejects_dangling_escape() -> None:
    """Verify a dangling escape fails parsing."""
    with pytest.raises(WifiError) as caught:
        split_escaped("bad\\")
    verify(caught.value.category == ErrorCategory.PARSE_FAILURE)


def test_split_escaped_rejects_wrong_field_count() -> None:
    """Verify an unexpected field count fails parsing."""
    with pytest.raises(WifiError):
        split_escaped("one:two", 3)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("yes", True), ("disabled", False), ("1", True), ("0", False)],
)
def test_parse_bool(raw: str, *, expected: bool) -> None:
    """Verify supported NetworkManager boolean spellings."""
    verify(parse_bool(raw) is expected)


def test_parse_signal_validates_range() -> None:
    """Verify signal values are optional and range checked."""
    verify(parse_signal("") is None)
    verify(parse_signal("75") == _SIGNAL_75)
    with pytest.raises(WifiError):
        parse_signal("101")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("--", SecurityClass.OPEN),
        ("WEP", SecurityClass.WEP),
        ("WPA1", SecurityClass.WPA_PERSONAL),
        ("WPA2", SecurityClass.WPA2_PERSONAL),
        ("WPA3 SAE", SecurityClass.WPA3_PERSONAL),
        ("WPA2 WPA3 SAE", SecurityClass.MIXED_PERSONAL),
        ("WPA2 802.1X", SecurityClass.ENTERPRISE),
        ("mystery", SecurityClass.UNKNOWN),
    ],
)
def test_security_classification(raw: str, expected: SecurityClass) -> None:
    """Verify security modes are classified without unsafe downgrades."""
    verify(parse_security(raw) == expected)


def test_frequency_to_channel() -> None:
    """Verify supported Wi-Fi frequencies map to channels."""
    verify(frequency_to_channel(2412) == 1)
    verify(frequency_to_channel(2484) == _CHANNEL_14)
    verify(frequency_to_channel(5180) == _CHANNEL_36)
    verify(frequency_to_channel(5955) == 1)
    verify(frequency_to_channel(1234) is None)


def test_validate_uuid() -> None:
    """Verify connection UUID validation and normalization."""
    value = "00000000-0000-0000-0000-000000000001"
    verify(validate_uuid(value) == value)
    with pytest.raises(WifiError):
        validate_uuid("not-a-uuid")


def test_additional_scalar_and_state_parsers() -> None:
    """Verify integer, state, and IP-address parsing."""
    verify(parse_optional_int("") is None)
    verify(parse_optional_int("5180") == _FREQUENCY_5180)
    verify(parse_device_state("connected") == DeviceState.ACTIVATED)
    verify(parse_device_state("future-state") == DeviceState.UNKNOWN)
    verify(parse_nm_state("connected (global)") == NetworkManagerState.CONNECTED_GLOBAL)
    verify(parse_nm_state("future-state") == NetworkManagerState.UNKNOWN)
    verify(
        parse_ip_values(["192.0.2.1/24", "", "2001:db8::1/64"])
        == (
            "192.0.2.1/24",
            "2001:db8::1/64",
        ),
    )
    with pytest.raises(WifiError):
        parse_optional_int("not-int")
    with pytest.raises(WifiError):
        parse_ip_values(["not-an-address"])
''',
    )


def write_secret_tests() -> None:
    """Write secret tests without local imports."""
    write(
        "tests/unit/test_secrets.py",
        '''"""Verify secret storage and redaction."""

from __future__ import annotations

from tests.assertions import verify
from tui_wifi.process import ProcessRequest
from tui_wifi.secrets import SecretValue, redact_arguments, redact_text


def test_secret_never_formats_as_plaintext() -> None:
    """Verify secret objects never render their plaintext value."""
    secret = SecretValue("correct horse battery staple")
    verify("correct" not in str(secret))
    verify("correct" not in repr(secret))
    verify(secret.reveal() == "correct horse battery staple")
    secret.clear()
    verify(secret.reveal() == "")


def test_argument_and_text_redaction() -> None:
    """Verify argument and free-text redaction removes protected values."""
    args = ("connect", "Example", "password", "very-secret")
    verify(redact_arguments(args, frozenset({3}))[-1] == "<redacted>")
    text = redact_text(
        "password=very-secret psk other-secret",
        ("very-secret", "other-secret"),
    )
    verify("very-secret" not in text)
    verify("other-secret" not in text)


def test_process_request_repr_hides_raw_arguments_and_stdin() -> None:
    """Verify process request representations hide arguments and standard input."""
    request = ProcessRequest(
        "nmcli",
        ("device", "wifi", "connect", "Home", "password", "top-secret"),
        stdin="stdin-secret",
        sensitive_arg_indexes=frozenset({5}),
    )
    rendered = repr(request)
    verify("top-secret" not in rendered)
    verify("stdin-secret" not in rendered)
''',
    )


def repair_small_tests() -> None:
    """Correct remaining boolean constructor calls and formatting."""
    replace_exact(
        "tests/unit/test_grouping.py",
        "return AccessPoint(ssid.encode(), ssid, bssid, signal, 2412, 1, security, active, \"wlan0\")",
        "return AccessPoint(\n"
        "        ssid=ssid.encode(),\n"
        "        display_ssid=ssid,\n"
        "        bssid=bssid,\n"
        "        signal=signal,\n"
        "        frequency=2412,\n"
        "        channel=1,\n"
        "        security=security,\n"
        "        active=active,\n"
        "        device=\"wlan0\",\n"
        "    )",
    )
    replace_exact(
        "tests/unit/test_grouping.py",
        "        True,\n        SecurityClass.WPA2_PERSONAL,",
        "        autoconnect=True,\n        security=SecurityClass.WPA2_PERSONAL,",
    )
    replace_exact(
        "tests/tui/test_app.py",
        "                False,\n                \"wlan0\",",
        "                active=False,\n                device=\"wlan0\",",
    )
    replace_exact(
        "tests/unit/test_logging.py",
        "    tmp_path: Path, monkeypatch: pytest.MonkeyPatch\n",
        "    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,\n",
    )


def main() -> None:
    """Apply all final known lint fixes."""
    repair_source_calls()
    write_cli_tests()
    write_service_tests()
    write_process_tests()
    write_parsing_tests()
    write_secret_tests()
    repair_small_tests()


if __name__ == "__main__":
    main()
