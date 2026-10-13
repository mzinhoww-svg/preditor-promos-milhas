
import httpx

from preditor.wayback import (
    DEFAULT_USER_AGENT,
    CDXClient,
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
    def h(request):
        return httpx.Response(200, json=FIXTURE)
    transport = httpx.MockTransport(h)
    captures = list_captures(
        "https://exemplo.com/promo", "20260101", "20260301", transport=transport, rate_limit=0
    )
    assert len(captures) == 2


def test_rate_limit_calls_sleep(monkeypatch):
    slept = []

    def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr("preditor.wayback.time.sleep", fake_sleep)
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=FIXTURE))
    c1 = CDXClient(transport=transport, rate_limit=2)  # 0.5s interval
    c1.list_captures("https://exemplo.com/promo", rate_limit=0) if False else None
    # duas requisições no mesmo cliente devem respeitar intervalo
    client = CDXClient(transport=transport, rate_limit=2, min_interval=0.25)
    client.list_captures("https://exemplo.com/promo")
    # força segunda chamada imediata
    monkeypatch.setattr("preditor.wayback.time.monotonic", lambda: 0.0)
    client.list_captures("https://exemplo.com/promo")
    assert slept  # ao menos uma espera


def test_parse_cdx_response_handles_empty():
    assert parse_cdx_response([]) == []
    assert parse_cdx_response(None) == []


def test_no_real_network_needed():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json=[["timestamp"], []] if False else FIXTURE))
    captures = CDXClient(transport=transport, rate_limit=0).list_captures("https://exemplo.com/promo")
    assert isinstance(captures, list)
