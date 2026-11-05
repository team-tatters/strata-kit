"""One small HTTP door for the source adapters: timeout, one retry, keys from the environment only (never from files),
and an injectable fetcher so tests run on fixtures without the network."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

UA = "strata-kit security core"


class HttpError(RuntimeError):
    pass


class Http:
    def __init__(self, fetcher=None, timeout: int = 20, retries: int = 1, pause: float = 0.0):
        self._fetch = fetcher or self._urllib
        self.timeout, self.retries, self.pause = timeout, retries, pause

    def _headers(self, url: str, headers: dict | None) -> dict:
        h = {"User-Agent": UA, "Accept": "application/json"}
        if "api.github.com" in url and os.environ.get("GITHUB_TOKEN"):
            h["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
        if "services.nvd.nist.gov" in url and os.environ.get("STRATA_SEC_NVD_KEY"):
            h["apiKey"] = os.environ["STRATA_SEC_NVD_KEY"]
        h.update(headers or {})
        return h

    def _urllib(self, url: str, data: bytes | None, headers: dict) -> bytes:
        req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read()

    def raw(self, url: str, params: dict | None = None, data: bytes | None = None, headers: dict | None = None) -> bytes:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                out = self._fetch(url, data, self._headers(url, headers))
                if self.pause:
                    time.sleep(self.pause)
                return out
            except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as e:
                last = e
                if attempt < self.retries:
                    time.sleep(1.0)
        raise HttpError(f"{url}: {last}")

    def text(self, url: str, **kw) -> str:
        return self.raw(url, **kw).decode("utf-8", errors="replace")

    def json(self, url: str, **kw):
        body = self.raw(url, **kw)
        try:
            return json.loads(body)
        except json.JSONDecodeError as e:
            raise HttpError(f"{url}: JSON 아님 ({e}) — {body[:80]!r}")

    def post_json(self, url: str, payload: dict, **kw):
        return self.json(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json", **kw.pop("headers", {})}, **kw)


def fixture_http(mapping: dict[str, bytes | str | dict | list]) -> Http:
    """Tests: url substring → body. A value that is a dict or list is JSON-encoded; a missing url raises like a network error."""
    def fetch(url, data, headers):
        for key, val in mapping.items():
            if key in url:
                if isinstance(val, (dict, list)):
                    return json.dumps(val).encode("utf-8")
                return val.encode("utf-8") if isinstance(val, str) else val
        raise OSError(f"fixture 없음: {url}")
    return Http(fetcher=fetch, retries=0)
