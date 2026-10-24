"""The debug log, and an httpx transport that records every request and response in it."""

from __future__ import annotations

import json
import time
from collections import deque
from datetime import UTC, datetime
from typing import Any

import httpx

CAPACITY = 300


class DebugLog:
    """The most recent debug entries, newest first."""

    def __init__(self) -> None:
        self._entries: deque[dict[str, Any]] = deque(maxlen=CAPACITY)

    def add(self, kind: str, title: str, **fields: Any) -> None:
        entry = {
            "at": datetime.now(UTC).isoformat(),
            "kind": kind,
            "title": title,
            "requestHeaders": {},
            "responseHeaders": {},
        }
        entry.update({k: v for k, v in fields.items() if v is not None})
        self._entries.appendleft(entry)

    def info(self, title: str, body: str | None = None) -> None:
        self.add("info", title, responseBody=body)

    def recent(self) -> list[dict[str, Any]]:
        return list(self._entries)

    def clear(self) -> None:
        self._entries.clear()


def pretty(text: str | None) -> str | None:
    if not text or not text.strip():
        return text
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except ValueError:
        return text


def _mask_authorization(value: str) -> str:
    """"Bearer abcdef1234" becomes "Bearer ••••1234": enough to tell which key was used, not enough to reuse it."""
    scheme, _, token = value.rpartition(" ")
    masked = f"••••{token[-4:]}" if len(token) > 8 else "••••"
    return f"{scheme} {masked}" if scheme else masked


def _headers(headers: httpx.Headers) -> dict[str, str]:
    return {k: _mask_authorization(v) if k.lower() == "authorization" else v for k, v in headers.items()}


def _trace_ids(body: str | None) -> dict[str, str]:
    try:
        parsed = json.loads(body or "")
    except ValueError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {k: parsed[k] for k in ("traceId", "spanId") if isinstance(parsed.get(k), str)}


class DebugTransport(httpx.AsyncBaseTransport):
    """Records every request the library sends to Bancontact and the response it gets.

    The library takes an ``httpx.AsyncClient`` (``BancontactClientFactory(http_client=...)``) and uses it for the API calls and
    for the JWKS fetches alike. It adds the Authorization and Signature headers before the client sends the request, so the log
    shows the request as it goes out on the wire.
    """

    def __init__(self, log: DebugLog, inner: httpx.AsyncBaseTransport | None = None) -> None:
        self._log = log
        self._inner = inner or httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        started = time.perf_counter()
        try:
            request_body: str | None = request.content.decode("utf-8") or None
        except httpx.RequestNotRead:
            request_body = "[streamed body]"
        common: dict[str, Any] = {
            "title": f"{request.method} {request.url.path}",
            "method": request.method,
            "url": str(request.url),
            "requestHeaders": _headers(request.headers),
            "requestBody": pretty(request_body),
        }

        try:
            response = await self._inner.handle_async_request(request)
        except Exception as exc:
            self._log.add("request", elapsedMs=round((time.perf_counter() - started) * 1000), error=f"{type(exc).__name__}: {exc}", **common)
            raise

        # Read it here, so the library can still read the body after we did.
        await response.aread()
        text = response.content.decode("utf-8", errors="replace")
        self._log.add(
            "request",
            status=response.status_code,
            elapsedMs=round((time.perf_counter() - started) * 1000),
            responseHeaders=dict(response.headers),
            responseBody=pretty(text),
            **({} if response.is_success else _trace_ids(text)),
            **common,
        )
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()
