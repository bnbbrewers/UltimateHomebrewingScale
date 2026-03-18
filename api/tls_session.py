"""
Persistent-TLS HTTP client for memory-constrained MicroPython boards.

The TLS handshake requires ~40 KB of contiguous C-heap for X.509 certificate
parsing.  On devices where LVGL icons fragment the IDF heap after boot, every
new handshake risks MBEDTLS_ERR_X509_ALLOC_FAILED.

This module keeps a single TLS socket alive across HTTP requests (HTTP/1.1
keep-alive) so the expensive handshake only happens once — ideally at boot,
when the C-heap is still clean and contiguous.
"""

import gc
import time
import socket
import ssl

try:
    import config as _config
    _DEBUG = getattr(_config, "DEBUG", False)
except Exception:
    _DEBUG = False


class TlsSession:

    def __init__(self, host, port=443):
        self._host = host
        self._port = port
        self._sock = None

    @property
    def is_connected(self):
        return self._sock is not None

    # ── connection lifecycle ───────────────────────────────────────

    def connect(self):
        """Open a fresh TLS connection.  Call early while the C-heap is clean."""
        self.close()
        gc.collect()
        info = socket.getaddrinfo(self._host, self._port, 0, socket.SOCK_STREAM)[0]
        raw = socket.socket(info[0], socket.SOCK_STREAM)
        raw.settimeout(15)
        try:
            raw.connect(info[-1])
            self._sock = ssl.wrap_socket(raw, server_hostname=self._host)
        except Exception:
            raw.close()
            raise

    def close(self):
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    # ── public request API ─────────────────────────────────────────

    def get(self, path, headers=None, retries=3):
        """
        HTTP GET over the persistent connection.

        Returns (status_code: int, body: bytes).
        Reconnects transparently when the kept-alive socket has been closed
        by the server (idle timeout) or by a network hiccup.
        """
        last_exc = None
        for attempt in range(retries):
            try:
                if not self.is_connected:
                    gc.collect()
                    self.connect()
                return self._do_get(path, headers)
            except Exception as exc:
                last_exc = exc
                if _DEBUG:
                    print("[TLS] attempt {} failed: {}".format(attempt + 1, exc))
                self.close()
                gc.collect()
                if attempt < retries - 1:
                    time.sleep_ms(500 * (attempt + 1))
        raise last_exc

    # ── HTTP/1.1 implementation ────────────────────────────────────

    def _do_get(self, path, headers):
        req = "GET {} HTTP/1.1\r\nHost: {}\r\nConnection: keep-alive\r\n".format(
            path, self._host
        )
        if headers:
            for k, v in headers.items():
                req += "{}: {}\r\n".format(k, v)
        req += "\r\n"
        self._sock.write(req.encode())

        status_line = self._readline()
        if not status_line:
            raise OSError("Connection closed by server")
        status_code = int(status_line.split(b" ", 2)[1])

        content_length = -1
        chunked = False
        conn_close = False
        while True:
            line = self._readline()
            if not line or line in (b"\r\n", b"\n"):
                break
            low = line.lower()
            if low.startswith(b"content-length:"):
                content_length = int(line.split(b":", 1)[1].strip())
            elif low.startswith(b"transfer-encoding:") and b"chunked" in low:
                chunked = True
            elif low.startswith(b"connection:") and b"close" in low:
                conn_close = True

        if chunked:
            body = self._read_chunked()
        elif content_length >= 0:
            body = self._read_exact(content_length)
        else:
            body = b""

        if conn_close:
            self.close()

        return status_code, body

    # ── low-level socket helpers ───────────────────────────────────

    def _readline(self):
        line = bytearray()
        while True:
            b = self._sock.read(1)
            if not b:
                break
            line.extend(b)
            if b == b"\n":
                break
        return bytes(line)

    def _read_exact(self, n):
        pieces = []
        left = n
        while left > 0:
            chunk = self._sock.read(left)
            if not chunk:
                break
            pieces.append(chunk)
            left -= len(chunk)
        return b"".join(pieces)

    def _read_chunked(self):
        pieces = []
        while True:
            size_line = self._readline().strip()
            if not size_line:
                break
            chunk_size = int(size_line, 16)
            if chunk_size == 0:
                self._readline()
                break
            pieces.append(self._read_exact(chunk_size))
            self._readline()
        return b"".join(pieces)
