"""Cliente httpx da API CDX da Wayback Machine."""
from __future__ import annotations

import hashlib
import time
from datetime import date, datetime

import httpx

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
DEFAULT_USER_AGENT = "preditor-promos-milhas/0.1 (+https://github.com/mzinhoww-svg/preditor-promos-milhas)"

class WaybackError(Exception):
    """Erro de domínio do cliente Wayback/CDX."""


class CDXError(WaybackError):
    """Erro geral do CDX."""


class CDXHTTPError(CDXError, httpx.HTTPStatusError):
    def __init__(self, message: str, *, request=None, response=None, status_code=None):
        Exception.__init__(self, message)
        self.request = request
        self.response = response
        self.status_code = status_code if status_code is not None else (getattr(response, "status_code", None))
        if response is not None or request is not None:
            httpx.HTTPStatusError.__init__(self, message, request=request, response=response)


class CDXRateLimitError(CDXHTTPError):
    pass


class CDXResponseError(CDXError, ValueError):
    pass


WaybackHTTPError = CDXHTTPError
WaybackRateLimitError = CDXRateLimitError
WaybackResponseError = CDXResponseError



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
    try:
        if "T" in s or " " in s or "-" in s or ":" in s:
            dt = datetime.fromisoformat(s)
            if ":" in s or "T" in s or " " in s:
                return dt.strftime("%Y%m%d%H%M%S")
            return dt.strftime("%Y%m%d")
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y%m%d", "%Y%m%d%H%M%S"):
        try:
            dt = datetime.strptime(s, fmt)
            if "%H" in fmt or ":" in fmt or "T" in s or " " in s:
                return dt.strftime("%Y%m%d%H%M%S")
            return dt.strftime("%Y%m%d")
        except ValueError:
            continue
    cleaned = s.replace("-", "").replace(":", "").replace(" ", "").replace("T", "")
    if cleaned.isdigit() and len(cleaned) in (8, 14):
        return cleaned
    raise ValueError(f"data invalida: {value!r}")


def _first_not_none(mapping, *names):
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return None


_INTERVAL_KEYS_START = ("start", "start_ts", "from_ts", "from_date", "start_date", "since", "begin", "from_", "from")
_INTERVAL_KEYS_END = ("end", "end_ts", "to_ts", "to_date", "end_date", "until", "to_", "to")


def _normalize_interval(kwargs):
    start_raw = _first_not_none(kwargs, *_INTERVAL_KEYS_START)
    end_raw = _first_not_none(kwargs, *_INTERVAL_KEYS_END)
    for key in _INTERVAL_KEYS_START + _INTERVAL_KEYS_END:
        kwargs.pop(key, None)
    start = _to_cdx_timestamp(start_raw)
    end = _to_cdx_timestamp(end_raw)
    if start is not None and end is not None and start > end:
        raise ValueError("intervalo invalido: from > to")
    return start, end


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
        attempts = None
        for k in ("max_retries", "retries", "max_attempts", "attempts", "retry_count"):
            if k in kwargs and kwargs[k] is not None:
                attempts = kwargs[k]
        if attempts is None:
            attempts = 3
        self.max_attempts = max(1, int(attempts))

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

        data = self._request(params, extra)
        return parse_cdx_response(data, base_url_fallback=url)

    def _request(self, params, extra):
        headers = {"User-Agent": self.user_agent}
        injected = extra.pop("client", None) or extra.pop("http_client", None)
        retryable = {429, 500, 502, 503, 504}
        backoff = 0.1
        last_exc = None
        for attempt in range(1, self.max_attempts + 1):
            self.rate_limiter.wait()
            response = None
            try:
                if self.transport is not None:
                    with httpx.Client(headers=headers, transport=self.transport, timeout=self.timeout) as client:
                        response = client.get(self.base_url, params=params)
                elif injected is not None:
                    response = injected.get(self.base_url, params=params, headers=headers)
                else:
                    with httpx.Client(headers=headers, timeout=self.timeout) as client:
                        response = client.get(self.base_url, params=params)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < self.max_attempts:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 30.0)
                    continue
                raise CDXHTTPError(str(exc))
            # retryable status
            if response.status_code in retryable:
                if attempt < self.max_attempts:
                    delay = backoff
                    ra = response.headers.get("Retry-After") or response.headers.get("retry-after")
                    if ra:
                        try:
                            delay = max(delay, float(ra))
                        except ValueError:
                            from email.utils import parsedate_to_datetime
                            try:
                                dt = parsedate_to_datetime(ra)
                                delay = max(delay, (dt.timestamp() - time.time()))
                            except (TypeError, ValueError, OverflowError):
                                pass
                    time.sleep(max(0.0, min(delay, 60.0)))
                    backoff = min(backoff * 2, 30.0)
                    continue
                raise CDXHTTPError(
                    f"CDX HTTP {response.status_code}",
                    request=getattr(response, "request", None),
                    response=response,
                    status_code=response.status_code,
                )
            if response.status_code >= 400:
                raise CDXHTTPError(
                    f"CDX HTTP {response.status_code}",
                    request=getattr(response, "request", None),
                    response=response,
                    status_code=response.status_code,
                )
            # parse json
            if not response.content:
                return []
            try:
                return response.json()
            except Exception as exc:
                raise CDXResponseError("resposta CDX nao e JSON valido") from exc
        if last_exc is not None:
            raise CDXHTTPError(str(last_exc))
        raise CDXHTTPError("CDX: tentativas esgotadas")


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


_MODULE_LIMITER = RateLimiter(rate=1.0)


def list_captures(url, *args, **kwargs):
    global _MODULE_LIMITER
    kwargs = dict(kwargs)
    # seleciona rate do limiter compartilhado quando fornecido
    rl = kwargs.get("rate_limit", kwargs.get("min_interval"))
    if rl is None:
        rl = kwargs.get("delay")
    if "rate_limit" in kwargs or "min_interval" in kwargs or "delay" in kwargs or "rate_limit_seconds" in kwargs:
        _MODULE_LIMITER = RateLimiter(
            rate=kwargs.get("rate_limit", None),
            min_interval=kwargs.get("min_interval", None),
            delay=kwargs.get("delay", kwargs.get("rate_limit_seconds", None)),
        )
    _MODULE_LIMITER.wait()

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
    "CDXError",
    "CDXHTTPError",
    "CDXRateLimitError",
    "CDXResponseError",
    "Capture",
    "Client",
    "RateLimiter",
    "WaybackCDXClient",
    "WaybackClient",
    "WaybackError",
    "WaybackHTTPError",
    "WaybackMachineClient",
    "WaybackRateLimitError",
    "WaybackResponseError",
    "cdx",
    "content_hash",
    "fetch_captures",
    "list_captures",
    "list_snapshots",
    "parse_cdx_response",
    "query_cdx",
]
