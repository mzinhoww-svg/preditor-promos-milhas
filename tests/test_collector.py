from preditor.collector import content_hash, parse_feed, robots_allowed


def test_parse_feed_basic():
    xml = """<rss><channel>
      <item><title>Livelo e Smiles 90% bônus</title><link>https://x/p</link></item>
    </channel></rss>"""
    items = parse_feed(xml)
    assert len(items) == 1
    assert items[0]["title"].startswith("Livelo")
    assert items[0]["link"] == "https://x/p"


def test_robots_blocked_not_fetched():
    robots = "User-agent: *\nDisallow: /private/\n"
    assert robots_allowed(robots, "https://example.com/public/") is True
    assert robots_allowed(robots, "https://example.com/private/x") is False


def test_content_hash_stable():
    assert content_hash("a") == content_hash("a")
    assert content_hash("a") != content_hash("b")
