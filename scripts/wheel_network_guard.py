from __future__ import annotations

from collections import Counter
from contextlib import AbstractContextManager
import _socket
import json
import os
from pathlib import Path
import socket
import sys
from types import TracebackType
from typing import Any, Callable, NoReturn


NETWORK_ATTEMPT_ENV = "NORNYX_NETWORK_ATTEMPT_LOG"


class NetworkAccessDenied(RuntimeError):
    """Raised before a Python socket operation can reach the network."""


_ACTIVE_GUARD: NetworkGuard | None = None
_AUDIT_HOOK_INSTALLED = False
_PERSISTENT_GUARD: NetworkGuard | None = None


def _local_socket_families() -> frozenset[int]:
    return frozenset(
        int(value)
        for name in ("AF_UNIX", "AF_LOCAL")
        if (value := getattr(socket, name, None)) is not None
    )


_LOCAL_SOCKET_FAMILIES = _local_socket_families()
_DNS_AUDIT_EVENTS = frozenset(
    {
        "socket.getaddrinfo",
        "socket.gethostbyaddr",
        "socket.gethostbyname",
        "socket.getnameinfo",
    }
)
_SOCKET_OPERATION_AUDIT_EVENTS = frozenset(
    {"socket.bind", "socket.connect", "socket.sendmsg", "socket.sendto"}
)


def _family_name(family: object) -> str:
    try:
        return socket.AddressFamily(int(family)).name
    except (TypeError, ValueError):
        return repr(family)


def _audit_hook(event: str, args: tuple[object, ...]) -> None:
    guard = _ACTIVE_GUARD
    if guard is None:
        return

    if event == "socket.__new__":
        family = args[1] if len(args) > 1 else None
        try:
            numeric_family = int(family)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            numeric_family = None
        if numeric_family in _LOCAL_SOCKET_FAMILIES:
            return
        guard.deny("socket.socket", family=_family_name(family))

    if event in _DNS_AUDIT_EVENTS:
        guard.deny(event, arguments=args)

    if event not in _SOCKET_OPERATION_AUDIT_EVENTS:
        return
    candidate = args[0] if args else None
    if guard._is_local_socket(candidate):
        return
    address = args[-1] if len(args) > 1 else None
    guard.deny(event, address=address)


def _ensure_audit_hook() -> None:
    global _AUDIT_HOOK_INSTALLED
    if _AUDIT_HOOK_INSTALLED:
        return
    sys.addaudithook(_audit_hook)
    _AUDIT_HOOK_INSTALLED = True


class NetworkGuard(AbstractContextManager["NetworkGuard"]):
    """Record and reject Python network operations before they reach the OS."""

    def __init__(self, attempt_log: str | os.PathLike[str]) -> None:
        self.attempt_log = Path(attempt_log)
        self._restorations: list[tuple[object, str, object]] = []
        self._installed = False

    def record(self, operation: str, **details: object) -> dict[str, str]:
        entry = {
            "operation": operation,
            **{key: repr(value) for key, value in sorted(details.items())},
        }
        self.attempt_log.parent.mkdir(parents=True, exist_ok=True)
        with self.attempt_log.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(entry, sort_keys=True) + "\n")
        return entry

    def deny(self, operation: str, **details: object) -> NoReturn:
        entry = self.record(operation, **details)
        raise NetworkAccessDenied(f"network disabled during wheel smoke: {entry!r}")

    def _patch(self, owner: object, name: str, replacement: object) -> None:
        original = getattr(owner, name)
        setattr(owner, name, replacement)
        self._restorations.append((owner, name, original))

    def _is_local_socket(self, candidate: object) -> bool:
        family = getattr(candidate, "family", None)
        try:
            return int(family) in _LOCAL_SOCKET_FAMILIES
        except (TypeError, ValueError):
            return False

    def install(self) -> NetworkGuard:
        global _ACTIVE_GUARD
        if self._installed:
            return self
        if _ACTIVE_GUARD is not None:
            raise RuntimeError("a wheel network guard is already active")
        _ensure_audit_hook()

        original_connect = socket.socket.connect
        original_connect_ex = socket.socket.connect_ex
        original_sendto = socket.socket.sendto
        guard = self

        def connect(candidate: object, address: object) -> Any:
            if guard._is_local_socket(candidate):
                return original_connect(candidate, address)  # type: ignore[arg-type]
            guard.deny("socket.connect", address=address)

        def connect_ex(candidate: object, address: object) -> Any:
            if guard._is_local_socket(candidate):
                return original_connect_ex(candidate, address)  # type: ignore[arg-type]
            guard.deny("socket.connect_ex", address=address)

        def sendto(candidate: object, data: object, *args: object) -> Any:
            if guard._is_local_socket(candidate):
                return original_sendto(candidate, data, *args)  # type: ignore[arg-type]
            address = args[-1] if args else None
            guard.deny("socket.sendto", address=address)

        def create_connection(address: object, *args: object, **kwargs: object) -> Any:
            guard.deny("socket.create_connection", address=address)

        def getaddrinfo(host: object, port: object, *args: object, **kwargs: object) -> Any:
            guard.deny("socket.getaddrinfo", host=host, port=port)

        try:
            self._patch(socket.socket, "connect", connect)
            self._patch(socket.socket, "connect_ex", connect_ex)
            self._patch(socket.socket, "sendto", sendto)
            if hasattr(socket.socket, "sendmsg"):
                original_sendmsg = socket.socket.sendmsg

                def sendmsg(candidate: object, buffers: object, *args: object) -> Any:
                    if guard._is_local_socket(candidate):
                        return original_sendmsg(candidate, buffers, *args)  # type: ignore[arg-type]
                    address = args[-1] if args else None
                    guard.deny("socket.sendmsg", address=address)

                self._patch(socket.socket, "sendmsg", sendmsg)
            self._patch(socket, "create_connection", create_connection)
            self._patch(socket, "getaddrinfo", getaddrinfo)
            _ACTIVE_GUARD = self
            self._installed = True
        except Exception:
            self.uninstall()
            raise
        return self

    def uninstall(self) -> None:
        global _ACTIVE_GUARD
        if _ACTIVE_GUARD is self:
            _ACTIVE_GUARD = None
        while self._restorations:
            owner, name, original = self._restorations.pop()
            setattr(owner, name, original)
        self._installed = False

    def __enter__(self) -> NetworkGuard:
        return self.install()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.uninstall()


def load_attempts(path: str | os.PathLike[str]) -> list[dict[str, str]]:
    attempt_log = Path(path)
    if not attempt_log.is_file():
        return []
    return [
        json.loads(line)
        for line in attempt_log.read_text(encoding="utf-8").splitlines()
        if line
    ]


def _expect_denied(operation: Callable[[], object]) -> None:
    try:
        operation()
    except NetworkAccessDenied:
        return
    raise AssertionError("network-guard self-test operation was not rejected")


def run_self_test(attempt_log: str | os.PathLike[str]) -> list[dict[str, str]]:
    """Exercise every guarded primitive without performing network I/O."""

    path = Path(attempt_log)
    path.unlink(missing_ok=True)
    fake_socket = type("FakeNetworkSocket", (), {"family": socket.AF_INET})()
    with NetworkGuard(path):
        _expect_denied(lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        _expect_denied(lambda: socket.socket(socket.AF_INET6, socket.SOCK_DGRAM))
        _expect_denied(
            lambda: socket.socket.connect(fake_socket, ("127.0.0.1", 9))
        )
        _expect_denied(
            lambda: socket.socket.connect_ex(fake_socket, ("127.0.0.1", 9))
        )
        _expect_denied(
            lambda: socket.socket.sendto(fake_socket, b"probe", ("127.0.0.1", 9))
        )
        if hasattr(socket.socket, "sendmsg"):
            _expect_denied(
                lambda: socket.socket.sendmsg(
                    fake_socket,
                    [b"probe"],
                    [],
                    0,
                    ("127.0.0.1", 9),
                )
            )
        _expect_denied(lambda: socket.getaddrinfo("example.invalid", 443))
        _expect_denied(lambda: _socket.getaddrinfo("127.0.0.1", 9))
        _expect_denied(lambda: socket.gethostbyname("127.0.0.1"))
        _expect_denied(lambda: socket.gethostbyname_ex("127.0.0.1"))
        _expect_denied(lambda: socket.gethostbyaddr("127.0.0.1"))
        _expect_denied(lambda: socket.getnameinfo(("127.0.0.1", 9), 0))
        _expect_denied(lambda: socket.create_connection(("127.0.0.1", 9)))

    attempts = load_attempts(path)
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
    if hasattr(socket.socket, "sendmsg"):
        expected["socket.sendmsg"] = 1
    observed = Counter(item.get("operation") for item in attempts)
    if observed != expected:
        raise AssertionError(
            f"network-guard self-test mismatch: expected {expected!r}, observed {observed!r}"
        )
    return attempts


def install_from_environment() -> NetworkGuard | None:
    global _PERSISTENT_GUARD
    attempt_log = os.environ.get(NETWORK_ATTEMPT_ENV)
    if not attempt_log:
        return None
    if _PERSISTENT_GUARD is None:
        _PERSISTENT_GUARD = NetworkGuard(attempt_log).install()
    return _PERSISTENT_GUARD
