"""Injected-session transport; the caller owns and closes the aiohttp session."""

from urllib.parse import urlsplit

import aiohttp

from .protocol import (API, MAX_DOCUMENT_BYTES, MAX_METADATA_BYTES, UINT32_MAX,
                       HTTPResponse, ProtocolError, TransportError)


class AiohttpTransport:
    def __init__(self, session: aiohttp.ClientSession, origin: str, *, request_timeout=7.0):
        try:
            parts = urlsplit(origin)
            port = parts.port
            if (parts.scheme not in {"http", "https"} or not parts.hostname or
                    parts.username is not None or parts.password is not None or parts.query or parts.fragment or
                    parts.path not in {"", "/"} or (port is not None and port == 0) or
                    any(ord(c) <= 32 or ord(c) >= 127 or c in "\\%" for c in origin)):
                raise ValueError
        except ValueError:
            raise ValueError("Expected HTTP(S) origin without credentials, query or path") from None
        if not 0 < request_timeout <= 60:
            raise ValueError("Invalid HTTP request timeout")
        self._session = session
        self._origin = origin.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)

    async def request(self, method, path, *, headers, body, max_bytes):
        suffix = path.removeprefix(API)
        allowed = (method == "GET" and (suffix in {"status", "capabilities"} or
            any(suffix.startswith(prefix) and suffix[len(prefix):].isascii() and
                suffix[len(prefix):].isdecimal() and len(suffix[len(prefix):]) <= 10 and
                0 < int(suffix[len(prefix):]) < UINT32_MAX for prefix in ("jobs/", "downloads/")))) or (
            method == "POST" and suffix in {"export", "validate"})
        if (not path.startswith(API) or not allowed or
                type(max_bytes) is not int or not 0 < max_bytes <= max(MAX_DOCUMENT_BYTES, MAX_METADATA_BYTES) or
                (body is not None and (not isinstance(body, bytes) or len(body) > MAX_DOCUMENT_BYTES))):
            raise ValueError("Unsupported read/check request")
        try:
            async with self._session.request(method, self._origin + path, data=body, headers=headers,
                    timeout=self._timeout, allow_redirects=False, auto_decompress=False) as response:
                if response.headers.get("Content-Encoding") not in (None, "identity"):
                    raise ProtocolError("Compressed responses are not supported")
                if response.content_length is not None and response.content_length > max_bytes:
                    raise ProtocolError("Response exceeds byte limit")
                data = bytearray()
                async for chunk in response.content.iter_chunked(min(4096, max_bytes + 1)):
                    if len(data) + len(chunk) > max_bytes:
                        raise ProtocolError("Response exceeds byte limit")
                    data.extend(chunk)
                return HTTPResponse(response.status, tuple(response.headers.items()), bytes(data))
        except (aiohttp.ClientError, TimeoutError):
            raise TransportError("Panel HTTP request failed or timed out") from None
