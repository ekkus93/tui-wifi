"""Verify secret storage and redaction."""

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
