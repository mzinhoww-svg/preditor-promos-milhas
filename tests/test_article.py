from preditor.article import article_text, snippets

HTML = """<html><head><style>.x{background:linear-gradient(red 100%)}</style></head><body>
<aside class="widget"><p>Azul Fidelidade com bônus de até 110% para Smiles</p></aside>
<article><h1>Livelo e Smiles</h1><p>Livelo para Smiles com 80% de bônus até 31/03.</p>
<p>Hotéis com 50% de desconto.</p></article></body></html>"""


def test_article_text_drops_aside_and_css():
    t = article_text(HTML)
    assert "110%" not in t and "linear-gradient" not in t
    assert "80% de bônus" in t


def test_snippets_require_two_programs_and_pct_in_same_sentence():
    s = snippets(article_text(HTML))
    assert len(s) == 1 and "80%" in s[0]
    assert snippets("Livelo tem novidade. Smiles tambem. Bônus de 100%.") == []
