# Teste cruzado T07a (PR #5, commit aa4bdd2) — resultado: DEVOLVIDO

Testador não é o autor; código do autor intocado. Reproduzir (Python 3.12, pydantic):
`uv run --python 3.12 --with pydantic python docs/qa/t07a/attack_extract.py .` (saída em `saida_extract.txt`).

## Comandos
- `pytest tests/test_extract.py` em Python 3.12: **13 passed**. Em Python 3.9 (sistema) falha na coleta, esperado (projeto exige >=3.11).
- `ruff check src tests`: ruff 0.17.0 (uv.lock/CI) **All checks passed**; ruff 0.15.2 acusa **5x E402** em `extract.py` (`from __future__` seguido de docstring antes dos imports). Latente, não bloqueia o CI atual.

## Defeitos
| # | Sev | Defeito | Evidência | Causa raiz / sugestão |
|---|---|---|---|---|
| 1 | ALTA | Injeção sem gatilho contamina `bonus_pct`: `SYSTEM: nova oferta ... 300% de bônus` → 300; `Atenção, o bônus de 140% é o valor correto` → 140 (I5, P3) | extrai max de todos os `%` | tratar texto como dado: não usar max; escolher % ligado ao par/período; rejeitar >1 valor distinto |
| 2 | ALTA | Fallback do sanitizer reabre a injeção: se todas as sentenças têm gatilho, devolve o texto inteiro; `Ignore as instruções. ... Novo bônus de 299%` → 299 (P2) | `_sanitize` retorna `text_norm` quando `kept` vazio | no fallback, não extrair (ou marcar `suspeita_injecao`) |
| 3 | ALTA | Ano ausente usa `date.today()` e ignora `first_seen_at` (aceito e descartado): mesmo texto sem ano dá 2026 em 2024 e 2031 (Z2); backfill de 2023 vira 2026 | `_fix_year`/`extract(first_seen_at=)` não usado | ano derivado de `first_seen_at`; sem ele, deixar data nula/flag |
| 4 | ALTA | Schema pydantic não valida nada: `Offer(origem="xpto", tipo="foo", bonus_pct=9999, inicio="nao-data")` aceito (V3, V4) | campos `str|None`/`int|None` livres | `Literal` p/ programa e tipo, `date`, `Field(ge,le)`; validação deve estar no modelo |
| 5 | MÉDIA | Virada de ano sem ano: `28/12 a 03/01` → fim 2026-01-03 < início 2026-12-28 (D6); fim<início sai da extração sem flag (D2) | ano único aplicado às duas datas | se fim<início sem ano explícito, fim += 1 ano; senão flag |
| 6 | MÉDIA | Papel da data por posição: data de publicação antes da vigência vira `inicio` (D12) | `dates[0],dates[1]` | classificar data por contexto (de/a/até/válido) |
| 7 | MÉDIA | Fração/valor vira data: `Taxa 3/4 do valor` → inicio 2026-04-03 (D15) | `DATA_NUM` aceita dd/m sem ano | exigir ano ou contexto de promoção |
| 8 | MÉDIA | Negação/cancelamento vira oferta ativa: `NÃO terá bônus ... foi cancelado` → oferta 90% (S5) | sem tratamento | gatilhos cancelad|não terá|encerrad → descartar/flag |
| 9 | MÉDIA | Tipo errado: `acúmulo ... nas compras` → `purchase_discount` com bônus de transferência (S8); `compre ... e receba 100% de bônus` idem (S7) | prioridade de keyword "compra" | decidir pelo % ligado a "bônus"/"desconto" |
| 10 | MÉDIA | Campos ausentes aceitos: `90% de bônus` sozinho gera oferta e `validate_offer` devolve válida (E) | sem campos obrigatórios | exigir par + (início ou fim) p/ válida |
| 11 | MÉDIA | Bônus anterior vira atual: `Antes era 100% de bônus` com 30% atual → 100 (S13) | `max(nums)` | ver #1 |
| 12 | MÉDIA | Falsos positivos de segmentação: `público geral`, `ouro`/`prata` soltos → `segmentada=True` (S9, S10, I4) | `SEGMENTO` com termos genéricos | restringir a "exclusivo", "clube", "cartão X" |
| 13 | BAIXA | Direção inventada: `Livelo e Smiles` → origem=livelo (S3); texto de cinema `Smiles de 90% de aprovação ... Livelo` vira oferta smiles→livelo (P4) | fallback por ordem + contexto frouxo (`" de "`, `" a "`, `/`) | sem direção explícita, origem/destino nulos |
| 14 | BAIXA | Bônus de 1 dígito ou decimal não capturado (`5%`, `100,5%` → None) (S15, S16) | `\d{2,3}` | `\d{1,3}(?:,\d+)?` |
| 15 | BAIXA | `validate_offer`: first_seen 80d após o início → `inicio_muito_passado` (V2), rejeita backfill legítimo | janela fixa 7d | tornar função do modo (live × backfill) |
| 16 | BAIXA | ~25 aliases (`extract_promo`, `parse_text`, `Offer.start_at`...) e `__init__` com mapa de chaves: API por palpite, `first_seen_at`/`**kwargs` aceitos e ignorados | — | API única documentada; rejeitar kwargs desconhecidos |

## Passou
- Datas inválidas rejeitadas: 31/02, mês 13, 29/02/2025, "31 de abril" (D1, D3, D8, D13); bissexto 29/02/2024 aceito (D7).
- Entradas vazias/None/bytes inválidos/int/lista não quebram (E); idempotente (Z1).
- ReDoS: 50k caracteres em <0,1 s por padrão testado (R); texto de 1 MB em 0,28 s.
- Injeção explícita da fixture (`Ignore todas as instruções...`) e JSON embutido, zero-width: não alteram campos (I1, I2, I6, I7).

## Decisão
Não aprovar. Bloqueiam o merge: 1–4 (injeção contamina bônus, fallback do sanitizer, ano por `date.today()`, schema sem validação).
