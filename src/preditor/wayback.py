"""Cliente httpx da API CDX da Wayback Machine."""
from __future__ import annotations

import hashlib
import time
from datetime import date, datetime

import httpx

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
DEFAULT_USER_AGENT = "preditor-promos-milhas/0.1 (+https://github.com/mzinhoww-svg/preditor-promos-milhas)"


class Capture(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


def _to_cdx_timestamp(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y%m%d%H%M%S")
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    s = str(value).strip()
    if not s:
        return None
    # tenta ISO 8601 / datas com separadores
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d", "%Y%m%d%H%M%S"):
        try:
            # remove Z
            cand = s.replace("Z", "+00:00")
            # fromisoformat mais flexível
            if "T" in cand or " " in cand or "-" in cand:
                dt = datetime.fromisoformat(cand)
            else:
                dt = datetime.strptime(cand, fmt)
            if "T" in s or ":" in s or " " in s:
                return dt.strftime("%Y%m%d%H%M%S")
            return dt.strftime("%Y%m%d")
        except ValueError:
            continue
    # último recurso: remove separadores
    cleaned = s.replace("-", "").replace(":", "").replace(" ", "").replace("T", "")
    return cleaned or None


def _first_not_none(mapping, *names):
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return None


_INTERVAL_KEYS_START = ("start", "start_ts", "from_ts", "from_date", "start_date", "since", "begin", "from_", "from")
_INTERVAL_KEYS_END = ("end", "end_ts", "to_ts", "to_date", "end_date", "until", "to_", "to")


def _normalize_interval(kwargs):
    start = _first_not_none(kwargs, *_INTERVAL_KEYS_START)
    end = _first_not_none(kwargs, *_INTERVAL_KEYS_END)
    for key in _INTERVAL_KEYS_START + _INTERVAL_KEYS_END:
        kwargs.pop(key, None)
    return _to_cdx_timestamp(start), _to_cdx_timestamp(end)


class RateLimiter:
    def __init__(self, rate=None, min_interval=None, delay=None):
        if min_interval is not None:
            self.min_interval = float(min_interval)
        elif delay is not None:
            self.min_interval = float(delay)
        elif rate in (None, 0):
            self.min_interval = 0.0
        else:
            r = float(rate)
            self.min_interval = 1.0 / r if r > 0 else 0.0
        self._last = 0.0

    def wait(self):
        if self.min_interval <= 0:
            self._last = time.monotonic()
            return
        now = time.monotonic()
        elapsed = now - self._last
        if self._last and elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()


class CDXClient:
    def __init__(self, base_url=CDX_ENDPOINT, user_agent=DEFAULT_USER_AGENT,
                 rate_limit=1.0, min_interval=None, delay=None,
                 transport=None, timeout=30.0, **kwargs):
        self.base_url = base_url
        ua = kwargs.get("user_agent", user_agent) or user_agent
        if kwargs.get("ua"):
            ua = kwargs["ua"]
        self.user_agent = ua
        rl = kwargs.get("rate_limit", rate_limit)
        mi = kwargs.get("min_interval", min_interval)
        dl = kwargs.get("delay", delay)
        if kwargs.get("rate_limit_seconds") is not None:
            dl = kwargs["rate_limit_seconds"]
        self.rate_limiter = RateLimiter(rate=rl, min_interval=mi, delay=dl)
        self.transport = transport
        self.timeout = timeout
        self._extra = kwargs

    def _params(self, url, start, end, extra):
        params = {"url": url, "output": "json"}
        if start:
            params["from"] = start
        if end:
            params["to"] = end
        for key in ("matchType", "limit", "collapse", "filter", "fl", "fastLatest"):
            if key in extra and extra[key] is not None:
                params[key] = extra[key]
        alias = {
            "match_type": "matchType",
            "limit": "limit",
            "collapse": "collapse",
            "filter_status": "filter",
            "fields": "fl",
            "fast_latest": "fastLatest",
        }
        for src, dst in alias.items():
            if src in extra and extra[src] is not None:
                params[dst] = extra[src]
        return params

    def list_captures(self, url, *args, **kwargs):
        start, end = _normalize_interval(kwargs)
        if args:
            vals = list(args)
            if start is None and vals:
                start = _to_cdx_timestamp(vals.pop(0))
            if end is None and vals:
                end = _to_cdx_timestamp(vals.pop(0))
        extra = dict(kwargs)
        params = self._params(url, start, end, extra)

        self.rate_limiter.wait()

        headers = {"User-Agent": self.user_agent}
        injected = extra.pop("client", None) or extra.pop("http_client", None)
        if self.transport is not None:
            with httpx.Client(headers=headers, transport=self.transport, timeout=self.timeout) as client:
                response = client.get(self.base_url, params=params)
        elif injected is not None:
            response = injected.get(self.base_url, params=params, headers=headers)
        else:
            with httpx.Client(headers=headers, timeout=self.timeout) as client:
                response = client.get(self.base_url, params=params)
        response.raise_for_status()
        data = response.json() if response.content else []
        return parse_cdx_response(data, base_url_fallback=url)


def parse_cdx_response(data, base_url_fallback=None):
    if data is None:
        return []
    if isinstance(data, dict):
        for key in ("results", "captures", "items", "data"):
            if key in data:
                data = data[key]
                break
    if not isinstance(data, list):
        return []
    if not data:
        return []
    if isinstance(data[0], dict):
        captures = []
        for row in data:
            cap = Capture(**{str(k): v for k, v in row.items()})
            _add_aliases(cap, base_url_fallback)
            captures.append(cap)
        return captures
    if isinstance(data[0], (list, tuple)):
        header = [str(x) for x in data[0]]
        captures = []
        for row in data[1:]:
            if not isinstance(row, (list, tuple)):
                continue
            mapping = {header[i]: (row[i] if i < len(row) else None) for i in range(len(header))}
            cap = Capture(**mapping)
            _add_aliases(cap, base_url_fallback)
            captures.append(cap)
        if (not captures) and all(isinstance(x, (list, tuple)) for x in data):
            std = ["urlkey", "timestamp", "original", "mimetype", "statuscode", "digest", "length"]
            captures = []
            for row in data:
                mapping = {std[i]: (row[i] if i < len(row) else None) for i in range(min(len(std), len(row)))}
                cap = Capture(**mapping)
                _add_aliases(cap, base_url_fallback)
                captures.append(cap)
        return captures
    return []


def _add_aliases(cap, base_url_fallback):
    if "original" in cap and "url" not in cap:
        cap["url"] = cap["original"]
    if "statuscode" in cap and "status" not in cap:
        cap["status"] = cap["statuscode"]
    if "mimetype" in cap and "mime" not in cap:
        cap["mime"] = cap["mimetype"]
    if "url" not in cap and base_url_fallback is not None:
        cap["url"] = base_url_fallback
    if "timestamp" in cap and "datetime" not in cap:
        cap["datetime"] = cap["timestamp"]


WaybackClient = CDXClient
WaybackCDXClient = CDXClient
WaybackMachineClient = CDXClient

# compatibility shim: name stability
Client = CDXClient


def list_captures(url, *args, **kwargs):
    client = kwargs.pop("client", None) or kwargs.pop("cdx_client", None)
    if client is None:
        ctor_keys = {"base_url", "user_agent", "rate_limit", "min_interval", "delay", "transport", "timeout", "ua", "rate_limit_seconds"}
        if ctor_keys & set(kwargs):
            client = CDXClient(**{k: kwargs.pop(k) for k in list(kwargs) if k in ctor_keys})
    if client is None:
        client = CDXClient()
    return client.list_captures(url, *args, **kwargs)


def list_snapshots(*args, **kwargs):
    return list_captures(*args, **kwargs)


def cdx(*args, **kwargs):
    return list_captures(*args, **kwargs)


def fetch_captures(*args, **kwargs):
    return list_captures(*args, **kwargs)


def query_cdx(*args, **kwargs):
    return list_captures(*args, **kwargs)


def content_hash(value):
    data = value.encode("utf-8") if isinstance(value, str) else bytes(value)
    return hashlib.sha256(data).hexdigest()


__all__ = [
    "CDX_ENDPOINT",
    "DEFAULT_USER_AGENT",
    "CDXClient",
    "Capture",
    "Client",
    "RateLimiter",
    "WaybackCDXClient",
    "WaybackClient",
    "WaybackMachineClient",
    "cdx",
    "content_hash",
    "fetch_captures",
    "list_captures",
    "list_snapshots",
    "parse_cdx_response",
    "query_cdx",
]
