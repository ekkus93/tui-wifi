from __future__ import annotations

from tui_wifi.secrets import SecretValue, redact_arguments, redact_text


def test_secret_never_formats_as_plaintext() -> None:
    secret = SecretValue("correct horse battery staple")
    assert "correct" not in str(secret)
    assert "correct" not in repr(secret)
    assert secret.reveal() == "correct horse battery staple"
    secret.clear()
    assert secret.reveal() == ""


def test_argument_and_text_redaction() -> None:
    args = ("connect", "Example", "password", "very-secret")
    assert redact_arguments(args, frozenset({3}))[-1] == "<redacted>"
    text = redact_text(
        "password=very-secret psk other-secret",
        ("very-secret", "other-secret"),
    )
    assert "very-secret" not in text
    assert "other-secret" not in text


def test_process_request_repr_hides_raw_arguments_and_stdin() -> None:
    from tui_wifi.process import ProcessRequest

    request = ProcessRequest(
        "nmcli",
        ("device", "wifi", "connect", "Home", "password", "top-secret"),
        stdin="stdin-secret",
        sensitive_arg_indexes=frozenset({5}),
    )
    rendered = repr(request)
    assert "top-secret" not in rendered
    assert "stdin-secret" not in rendered
