"""Extrai so o corpo do artigo e as sentencas relevantes (sem aside, cards, CSS)."""
from __future__ import annotations

import re
from html.parser import HTMLParser

_SKIP_TAGS = {"script", "style", "noscript", "aside", "nav", "footer", "header", "form",
              "iframe", "svg", "template", "button", "select"}
_VOID = {"br", "img", "hr", "input", "meta", "link", "source", "wbr", "area", "base", "col", "embed", "param", "track"}
_NOISE_CLASS = re.compile(
    r"(related|widget|sidebar|comment|share|social|banner|advert|\bads?\b|promo-card|newsletter|"
    r"breadcrumb|menu|cookie|popular|recommend|author-box|tags?-links)", re.IGNORECASE)
_BLOCK = {"p", "div", "li", "br", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "section", "article", "blockquote"}
_PROGRAMS = (r"livelo", r"smiles", r"esfera", r"latam\s*pass", r"azul\s*fidelidade")
_BODY_CLASS = re.compile(r"(entry-content|post-content|article-content|td-post-content|single-content)", re.IGNORECASE)


class _Body(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, bool, bool]] = []  # tag, skip, in_body
        self.skip_depth = 0
        self.chunks_all: list[str] = []
        self.chunks_body: list[str] = []
        self.body_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _VOID:
            if tag == "br":
                self._add("\n")
            return
        cls = " ".join(v or "" for k, v in attrs if k in ("class", "id"))
        skip = tag in _SKIP_TAGS or bool(_NOISE_CLASS.search(cls))
        body = tag == "article" or bool(_BODY_CLASS.search(cls))
        self.stack.append((tag, skip, body))
        if skip:
            self.skip_depth += 1
        if body:
            self.body_depth += 1
        if tag in _BLOCK:
            self._add("\n")

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for _t, skip, body in self.stack[i:]:
                    if skip:
                        self.skip_depth -= 1
                    if body:
                        self.body_depth -= 1
                del self.stack[i:]
                break
        if tag in _BLOCK:
            self._add("\n")

    def _add(self, s):
        if self.skip_depth:
            return
        self.chunks_all.append(s)
        if self.body_depth:
            self.chunks_body.append(s)

    def handle_data(self, data):
        self._add(data)


def article_text(html: str | None) -> str:
    """Texto do corpo do artigo: <article>/entry-content se houver, senao a pagina sem ruido."""
    if not html:
        return ""
    if "<" not in html:
        return re.sub(r"\s+", " ", html).strip()
    p = _Body()
    try:
        p.feed(html)
        p.close()
    except (ValueError, AssertionError):
        pass
    chunks = p.chunks_body if "".join(p.chunks_body).strip() else p.chunks_all
    text = "".join(chunks)
    text = re.sub(r"[ \t\r\f\v ]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n", text)
    return text.strip()


def _n_programs(s: str) -> int:
    return sum(1 for p in _PROGRAMS if re.search(p, s, re.IGNORECASE))


def snippets(text: str) -> list[str]:
    """Sentencas com >=2 programas e % na MESMA sentenca (+ sentenca seguinte se so tiver data)."""
    out: list[str] = []
    parts = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s and s.strip()]
    for i, s in enumerate(parts):
        if _n_programs(s) < 2 or not re.search(r"\d\s*%", s):
            continue
        cand = s
        if i + 1 < len(parts):
            nxt = parts[i + 1]
            if _n_programs(nxt) == 0 and not re.search(r"%", nxt) and re.search(r"\d{1,2}/\d{1,2}", nxt):
                cand = f"{s} {nxt}"
        if cand not in out:
            out.append(cand)
    return out
