"""Test-only local HTTP/1.1 server over real TCP sockets (OHB2-LARGE-FILE-REAL-HTTP).

The investigation OHB2-LARGE-FILE-DOWNLOAD-INTEGRATION-TEST-INVESTIGATION showed that
`httpx.MockTransport` with `stream=` does NOT enforce `Content-Length`: a response that
declares a large length but transmits fewer bytes is accepted as a complete success in
the mock, while a real socket raises a protocol error. So truncation / premature-close /
chunked-termination behaviour MUST be exercised over an actual TCP connection.

This module binds a raw socket to 127.0.0.1 on an OS-assigned port and answers each
accepted connection with the exact bytes the test wants to put on the wire. It is
test-only and never touches production code, Telegram, OpenHands, or the live database.

Nothing here validates `Content-Length` at the application level; these helpers exist to
let the HTTP transport (httpcore/httpx) do its job and to observe the resulting behaviour.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from typing import Callable, Iterable

__all__ = [
    "Request",
    "Router",
    "RealHTTPServer",
    "http_response",
    "json_response",
    "chunked_response",
    "truncated_response",
    "close_delimited_response",
    "chunk_header",
    "chunk_body",
    "chunk_terminator",
]

Responder = Callable[["Request"], "bytes | Iterable[bytes] | None"]


class Request:
    """A parsed request head (method, path incl. query, lower-cased headers)."""

    def __init__(self, method: str, path: str, headers: dict[str, str]) -> None:
        self.method = method
        self.path = path
        self.headers = headers

    @property
    def route_path(self) -> str:
        return self.path.split("?", 1)[0]

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Request({self.method} {self.path})"

    @classmethod
    def parse(cls, head: bytes) -> "Request | None":
        try:
            text = head.decode("latin-1")
        except Exception:  # noqa: BLE001 - malformed request head
            return None
        lines = text.split("\r\n")
        if not lines or not lines[0]:
            return None
        parts = lines[0].split(" ")
        if len(parts) < 2:
            return None
        method, path = parts[0], parts[1]
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if not line or ":" not in line:
                continue
            name, _, value = line.partition(":")
            headers[name.strip().lower()] = value.strip()
        return cls(method, path, headers)


# --------------------------------------------------------------------- builders
def http_response(
    status: int,
    *,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
    reason: str = "OK",
) -> bytes:
    """Build a raw HTTP/1.1 response with `Connection: close`.

    `Content-Length` is added only when neither it nor `Transfer-Encoding` was given, so
    callers can declare a length that deliberately disagrees with `body` (truncation).
    """
    hdrs = dict(headers or {})
    hdrs.setdefault("Connection", "close")
    if "Content-Length" not in hdrs and "Transfer-Encoding" not in hdrs:
        hdrs["Content-Length"] = str(len(body))
    lines = [f"HTTP/1.1 {status} {reason}"]
    lines.extend(f"{name}: {value}" for name, value in hdrs.items())
    head = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    return head + body


def json_response(obj, *, status: int = 200, headers: dict[str, str] | None = None) -> bytes:
    """Raw 200 response whose body is `json.dumps(obj)` with an exact Content-Length."""
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    return http_response(status, headers=hdrs, body=body)


def chunked_response(
    chunks: list[bytes], *, terminate: bool = True, status: int = 200,
    headers: dict[str, str] | None = None,
) -> bytes:
    """Raw chunked response. `terminate=False` omits the final 0-length chunk."""
    hdrs = {"Transfer-Encoding": "chunked"}
    if headers:
        hdrs.update(headers)
    head = http_response(status, headers=hdrs, body=b"")
    # http_response already appended the header terminator; rebuild body separately.
    body = b"".join(b"%x\r\n%s\r\n" % (len(chunk), chunk) for chunk in chunks)
    if terminate:
        body += b"0\r\n\r\n"
    return head + body


def truncated_response(
    declared_length: int, partial_body: bytes, *, status: int = 200,
    headers: dict[str, str] | None = None,
) -> bytes:
    """Response that declares `declared_length` but sends only `partial_body` bytes.

    The server closes the socket right after, so the client sees a premature close.
    """
    hdrs = {"Content-Length": str(declared_length)}
    if headers:
        hdrs.update(headers)
    return http_response(status, headers=hdrs, body=partial_body)


def close_delimited_response(body: bytes, *, status: int = 200,
                             headers: dict[str, str] | None = None) -> bytes:
    """Response with no Content-Length and no Transfer-Encoding (body ends at EOF)."""
    hdrs = {"Connection": "close"}
    if headers:
        hdrs.update(headers)
    lines = [f"HTTP/1.1 {status} OK"]
    lines.extend(f"{name}: {value}" for name, value in hdrs.items())
    head = ("\r\n".join(lines) + "\r\n\r\n").encode("latin-1")
    return head + body


def chunk_header(*, status: int = 200, headers: dict[str, str] | None = None) -> bytes:
    """Just the response head for a chunked response (no body yet)."""
    hdrs = {"Transfer-Encoding": "chunked"}
    if headers:
        hdrs.update(headers)
    return http_response(status, headers=hdrs, body=b"")


def chunk_body(data: bytes) -> bytes:
    """One chunked-transfer data chunk (length-prefixed)."""
    return b"%x\r\n%s\r\n" % (len(data), data)


def chunk_terminator() -> bytes:
    """The final zero-length chunk that terminates a chunked response."""
    return b"0\r\n\r\n"


class Router:
    """Maps request paths (or predicates) to responders; 404 otherwise.

    A responder returns either raw response bytes or an iterable of byte chunks that are
    sent in order (used to emit a valid header followed by a stalling body).
    """

    def __init__(self) -> None:
        self._routes: list[tuple[object, Responder]] = []

    def add(self, matcher, responder) -> "Router":
        if callable(responder) and not isinstance(responder, (bytes, bytearray)):
            fn: Responder = responder  # type: ignore[assignment]
        else:
            payload = bytes(responder)

            def fn(_request, _payload=payload) -> bytes:  # noqa: ANN001
                return _payload

        self._routes.append((matcher, fn))
        return self

    def __call__(self, request: Request):
        for matcher, responder in self._routes:
            if callable(matcher):
                if matcher(request):
                    return responder(request)
            elif request.route_path == matcher:
                return responder(request)
        return http_response(
            404, headers={"Content-Type": "application/json"}, body=b'{"detail":"not found"}',
            reason="Not Found",
        )


class RealHTTPServer:
    """Real HTTP/1.1 server on 127.0.0.1 with an OS-assigned port.

    `responder(request)` returns the raw response bytes to send, or `None` to send
    nothing and wait (used to simulate an upstream that never answers).
    """

    def __init__(self, responder: Responder | None = None) -> None:
        self.responder: Responder = responder or (
            lambda _request: http_response(204, body=b"")
        )
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(16)
        self._sock.settimeout(0.2)
        self.host, self.port = self._sock.getsockname()

        self._lock = threading.Lock()
        self.requests: list[Request] = []
        self.open_connections = 0
        self.peer_closed = 0
        self._conns: set[socket.socket] = set()
        self._threads: list[threading.Thread] = []
        self._closed = False
        # Set by `shutdown()`; responders that stall (cancellation/timeout tests) should
        # wait on this so their handler threads unblock promptly during teardown.
        self.stop_event = threading.Event()

        self._accept_thread = threading.Thread(target=self._serve, daemon=True)
        self._accept_thread.start()

    # ------------------------------------------------------------------ public
    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    @property
    def request_count(self) -> int:
        with self._lock:
            return len(self.requests)

    def wait_connections_closed(self, timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self.open_connections == 0:
                    return True
            time.sleep(0.01)
        with self._lock:
            return self.open_connections == 0

    def wait_peer_closed(self, count: int = 1, timeout: float = 5.0) -> bool:
        """Wait until at least `count` connections observed a peer-side EOF (client closed)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                if self.peer_closed >= count:
                    return True
            time.sleep(0.01)
        with self._lock:
            return self.peer_closed >= count

    def shutdown(self) -> None:
        with self._lock:
            self._closed = True
            conns = list(self._conns)
        self.stop_event.set()
        try:
            self._sock.close()
        except OSError:
            pass
        for conn in conns:
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                conn.close()
            except OSError:
                pass
        if self._accept_thread.is_alive():
            self._accept_thread.join(timeout=2.0)
        for thread in list(self._threads):
            if thread.is_alive():
                thread.join(timeout=2.0)

    def __enter__(self) -> "RealHTTPServer":
        return self

    def __exit__(self, *_exc) -> None:
        self.shutdown()

    # ----------------------------------------------------------------- internal
    def _serve(self) -> None:
        while True:
            with self._lock:
                if self._closed:
                    return
            try:
                conn, _addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with self._lock:
                if self._closed:
                    try:
                        conn.close()
                    except OSError:
                        pass
                    return
                self._conns.add(conn)
                self.open_connections += 1
            thread = threading.Thread(target=self._handle, args=(conn,), daemon=True)
            with self._lock:
                self._threads.append(thread)
            thread.start()

    def _handle(self, conn: socket.socket) -> None:
        try:
            head = self._read_head(conn)
            request = Request.parse(head) if head else None
            if request is not None:
                with self._lock:
                    self.requests.append(request)
                response = self.responder(request)
                if isinstance(response, (bytes, bytearray)):
                    conn.sendall(bytes(response))
                elif response is not None:
                    for part in response:
                        conn.sendall(part)
            self._drain(conn)
        except Exception:  # noqa: BLE001 - a test server must never raise into the suite
            pass
        finally:
            try:
                conn.close()
            except OSError:
                pass
            with self._lock:
                self._conns.discard(conn)
                self.open_connections -= 1

    @staticmethod
    def _read_head(conn: socket.socket) -> bytes:
        conn.settimeout(5.0)
        buf = bytearray()
        while b"\r\n\r\n" not in buf:
            try:
                data = conn.recv(65536)
            except (socket.timeout, OSError):
                break
            if not data:
                break
            buf += data
            if len(buf) > 65536:
                break
        return bytes(buf)

    def _drain(self, conn: socket.socket) -> None:
        """Read until the peer closes (EOF) or a short deadline passes.

        Kept short so teardown is fast; it only feeds the `peer_closed` counter.
        """
        deadline = time.monotonic() + 0.5
        conn.settimeout(0.1)
        while time.monotonic() < deadline:
            try:
                data = conn.recv(65536)
            except socket.timeout:
                continue
            except OSError:
                return
            if data == b"":
                with self._lock:
                    self.peer_closed += 1
                return
