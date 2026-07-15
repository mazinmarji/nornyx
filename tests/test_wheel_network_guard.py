from __future__ import annotations

from collections import Counter
import _socket
from pathlib import Path
import socket

import pytest

from scripts.wheel_network_guard import (
    NetworkAccessDenied,
    NetworkGuard,
    load_attempts,
    run_self_test,
)


def test_network_guard_self_test_records_and_rejects_every_primitive(
    tmp_path: Path,
) -> None:
    attempt_log = tmp_path / "self-test.jsonl"
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex
    original_sendto = socket.socket.sendto
    original_sendmsg = getattr(socket.socket, "sendmsg", None)
    original_create_connection = socket.create_connection
    original_getaddrinfo = socket.getaddrinfo

    attempts = run_self_test(attempt_log)

    expected = Counter(
        {
            "socket.socket": 2,
            "socket.connect": 1,
            "socket.connect_ex": 1,
            "socket.sendto": 1,
            "socket.getaddrinfo": 2,
            "socket.gethostbyaddr": 1,
            "socket.gethostbyname": 2,
            "socket.getnameinfo": 1,
            "socket.create_connection": 1,
        }
    )
    if original_sendmsg is not None:
        expected["socket.sendmsg"] = 1
    assert Counter(item["operation"] for item in attempts) == expected
    assert attempts == load_attempts(attempt_log)
    assert socket.socket.connect is original_connect
    assert socket.socket.connect_ex is original_connect_ex
    assert socket.socket.sendto is original_sendto
    assert getattr(socket.socket, "sendmsg", None) is original_sendmsg
    assert socket.create_connection is original_create_connection
    assert socket.getaddrinfo is original_getaddrinfo


def test_network_guard_denies_constructor_aliases_before_socket_creation(
    tmp_path: Path,
) -> None:
    attempt_log = tmp_path / "constructors.jsonl"
    constructors = (
        lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
        lambda: socket.SocketType(socket.AF_INET6, socket.SOCK_DGRAM),
        lambda: _socket.socket(),
    )

    with NetworkGuard(attempt_log):
        for constructor in constructors:
            with pytest.raises(NetworkAccessDenied, match="socket.socket"):
                constructor()

    attempts = load_attempts(attempt_log)
    assert [item["operation"] for item in attempts] == ["socket.socket"] * 3
    assert "AF_INET" in attempts[0]["family"]
    assert "AF_INET6" in attempts[1]["family"]
    assert attempts[2]["family"] == "'-1'"


def test_network_guard_self_test_log_is_separate_from_product_log(
    tmp_path: Path,
) -> None:
    self_test_log = tmp_path / "self-test.jsonl"
    product_log = tmp_path / "product.jsonl"

    assert run_self_test(self_test_log)
    assert load_attempts(product_log) == []


def test_network_guard_denies_low_level_and_legacy_dns_before_resolution(
    tmp_path: Path,
) -> None:
    attempt_log = tmp_path / "dns.jsonl"
    operations = (
        lambda: _socket.getaddrinfo("127.0.0.1", 9),
        lambda: socket.gethostbyname("127.0.0.1"),
        lambda: socket.gethostbyname_ex("127.0.0.1"),
        lambda: socket.gethostbyaddr("127.0.0.1"),
        lambda: socket.getnameinfo(("127.0.0.1", 9), 0),
    )

    with NetworkGuard(attempt_log):
        for operation in operations:
            with pytest.raises(NetworkAccessDenied):
                operation()

    assert Counter(item["operation"] for item in load_attempts(attempt_log)) == {
        "socket.getaddrinfo": 1,
        "socket.gethostbyname": 2,
        "socket.gethostbyaddr": 1,
        "socket.getnameinfo": 1,
    }


def test_network_guard_audit_fallback_denies_cached_socket_methods(
    tmp_path: Path,
) -> None:
    attempt_log = tmp_path / "cached-methods.jsonl"
    cached_connect = socket.socket.connect
    cached_connect_ex = socket.socket.connect_ex
    cached_bind = socket.socket.bind
    cached_sendto = socket.socket.sendto
    cached_sendmsg = getattr(socket.socket, "sendmsg", None)
    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tcp.close()
    udp.close()

    operations = [
        lambda: cached_bind(tcp, ("127.0.0.1", 0)),
        lambda: cached_connect(tcp, ("127.0.0.1", 9)),
        lambda: cached_connect_ex(tcp, ("127.0.0.1", 9)),
        lambda: cached_sendto(udp, b"probe", ("127.0.0.1", 9)),
    ]
    if cached_sendmsg is not None:
        operations.append(
            lambda: cached_sendmsg(udp, [b"probe"], [], 0, ("127.0.0.1", 9))
        )

    with NetworkGuard(attempt_log):
        for operation in operations:
            with pytest.raises(NetworkAccessDenied):
                operation()

    expected = Counter(
        {
            "socket.bind": 1,
            "socket.connect": 2,
            "socket.sendto": 1,
        }
    )
    if cached_sendmsg is not None:
        expected["socket.sendmsg"] = 1
    assert Counter(item["operation"] for item in load_attempts(attempt_log)) == expected
