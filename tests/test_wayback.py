
import httpx
import pytest

from preditor.wayback import (
    DEFAULT_USER_AGENT,
    CDXClient,
    CDXHTTPError,
    CDXResponseError,
    list_captures,
    parse_cdx_response,
)

FIXTURE = [
    ["urlkey", "timestamp", "original", "mimetype", "statuscode", "digest", "length"],
    ["com,exemplo)/promo", "20260101000000", "https://exemplo.com/promo", "text/html", "200", "ABC", "123"],
    ["com,exemplo)/promo", "20260201000000", "https://exemplo.com/promo", "text/html", "200", "DEF", "456"],
]


def handler(request):
    assert request.headers.get("User-Agent") == DEFAULT_USER_AGENT
    assert request.url.params.get("url") == "https://exemplo.com/promo"
    assert request.url.params.get("from") == "20260101"
    assert request.url.params.get("to") == "20260301"
    return httpx.Response(200, json=FIXTURE)


def test_list_captures_uses_mock_transport_and_parses():
    transport = httpx.MockTransport(handler)
    client = CDXClient(transport=transport, rate_limit=0)
    captures = client.list_captures(
        "https://exemplo.com/promo", from_date="2026-01-01", to_date="2026-03-01"
    )
    assert len(captures) == 2
    assert captures[0]["timestamp"] == "20260101000000"
    assert captures[0]["url"] == "https://exemplo.com/promo"
    assert captures[0].status == "200"


def test_list_captures_function_accepts_interval_positional():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=FIXTURE))
    captures = list_captures(
        "https://exemplo.com/promo", "20260101", "20260301", transport=transport, rate_limit=0
    )
    assert len(captures) == 2


def test_header_only_returns_empty():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[["urlkey", "timestamp"]]))
    captures = CDXClient(transport=transport, rate_limit=0).list_captures("https://exemplo.com/promo")
    assert captures == []


def test_retry_on_500_respects_limit():
    calls = {"n": 0}

    def h(request):
        calls["n"] += 1
        return httpx.Response(500, json={"err": "boom"})

    transport = httpx.MockTransport(h)
    with pytest.raises(CDXHTTPError):
        CDXClient(transport=transport, rate_limit=0, max_retries=2).list_captures("https://exemplo.com/promo")
    assert calls["n"] == 2


def test_retry_on_429_respects_retry_after(monkeypatch):
    slept = []
    monkeypatch.setattr("preditor.wayback.time.sleep", lambda s: slept.append(s))
    calls = {"n": 0}

    def h(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "2"}, json={})
        return httpx.Response(200, json=FIXTURE)

    transport = httpx.MockTransport(h)
    caps = CDXClient(transport=transport, rate_limit=0, max_retries=3).list_captures("https://exemplo.com/promo")
    assert len(caps) == 2
    assert calls["n"] == 2
    assert any(s >= 2 for s in slept)


def test_html_200_raises_response_error():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, text="<html>nope</html>", headers={"content-type": "text/html"}))
    with pytest.raises((CDXResponseError, ValueError)):
        CDXClient(transport=transport, rate_limit=0).list_captures("https://exemplo.com/promo")


def test_parse_empty():
    assert parse_cdx_response([]) == []
    assert parse_cdx_response(None) == []


def test_invalid_dates_raise():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=FIXTURE))
    with pytest.raises(ValueError):
        CDXClient(transport=transport, rate_limit=0).list_captures("https://exemplo.com/promo", from_date="lixo")
    with pytest.raises(ValueError):
        CDXClient(transport=transport, rate_limit=0).list_captures("https://exemplo.com/promo", from_date="2026-03-01", to_date="2026-01-01")


def test_module_level_rate_limit_sleeps(monkeypatch):
    slept = []
    monkeypatch.setattr("preditor.wayback.time.sleep", lambda s: slept.append(s))
    import preditor.wayback as w
    # baseline old
    w._MODULE_LIMITER = w.RateLimiter(rate=1.0)
    w._MODULE_LIMITER._last = 0.5
    # monotonic stays 0 so second call sleeps
    monkeypatch.setattr("preditor.wayback.time.monotonic", lambda: 0.0)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=FIXTURE))
    list_captures("https://exemplo.com/promo", transport=transport)
    list_captures("https://exemplo.com/promo", transport=transport)
    assert slept, "limiter compartilhado nao dormiu na chamada de modulo"


def test_module_list_rate_limit_not_reset_by_kwargs(monkeypatch):
    slept = []
    monkeypatch.setattr("preditor.wayback.time.sleep", lambda s: slept.append(s))
    import preditor.wayback as w
    # estado mais restritivo persiste mesmo com kwargs "leves"
    w._MODULE_LIMITER = w.RateLimiter(min_interval=2.0)
    w._MODULE_LIMITER._last = 0.5
    monkeypatch.setattr("preditor.wayback.time.monotonic", lambda: 0.0)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=FIXTURE))
    # chamada com min_interval menor nao pode desligar o limite existente
    list_captures("https://exemplo.com/promo", transport=transport, min_interval=0)
    assert slept, "limite de modulo foi anulado por parametro por chamada"
