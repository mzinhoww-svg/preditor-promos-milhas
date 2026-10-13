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

---

# Reteste (PR #5, commit f3d8db5) — resultado: DEVOLVIDO PARCIAL

## Comandos
- `pytest -q` (Python 3.12): **23 passed, 3 skipped**.
- `ruff check .` 0.17.0 (CI): **All checks passed**. ruff 0.15.2: ainda 5x E402 (latente).
- `attack_extract.py`: **0 FALHA** (saída em `saida_reteste.txt`).

## Os 4 bloqueantes anteriores: corrigidos
Injeção sem gatilho (60 em vez de 140/299/300), fallback do sanitizer, ano via `first_seen_at` (2024 vs 2031),
schema com `ValidationError` para programa/tipo/bônus/data inválidos.
Também corrigidos: virada de ano (28/12→03/01 = 2027), data de publicação, fração 3/4, negação,
tipo por compra, segmentada por "público/ouro", bônus 5% e 100,5%, campos ausentes.

## Novos defeitos (fora do script, que não os cobria)
| # | Sev | Defeito | Evidência | Sugestão |
|---|---|---|---|---|
| N1 | ALTA | Intervalo invertido com ano **explícito** tem o fim fabricado: `15/03/2025 a 10/03/2025` → fim `2026-03-10`; a validação reporta `janela_maior_90`, mascarando o erro real | sondagem D2/D2b | aplicar +1 ano só quando o ano do fim foi omitido; ano explícito e fim<início → rejeitar/flag `fim_antes_inicio` |
| N2 | ALTA | Início fabricado a partir do fim: `bônus até 15/03/2025` → início = fim = `2025-03-15`, e `validate_offer` devolve válida (D14, N2) | sondagem | `inicio=None` quando só há fim; início desconhecido é dado ausente |
| N3 | MÉDIA | Bônus conflitantes no mesmo texto (60% e 80% para o mesmo par/período) resolvem em silêncio para o primeiro (P3b) | sondagem | flag `bonus_conflitante` ou 0 ofertas |
| N4 | MÉDIA | Programa único vira `origem`: `Smiles: compra de pontos` → origem=smiles, destino None (P5); `Filme Smiles de 90% de aprovação` gera oferta (P4). Ambas inválidas por `campos_ausentes`, mas a oferta é emitida | sondagem | emitir só com tipo + % ligado a bônus/desconto; programa único em compra é destino |
| N5 | BAIXA | Dois asserts removidos de `test_prompt_injection_ignored` (origem/destino) e a expectativa de `promo_simples` virou `None`: cobertura reduzida e recall do par PoC perdido (`Livelo e Smiles` não dá par) | diff de tests | decisão de Aurimar sobre par não direcionado; se aceito, assert `is None` na injeção também |

## Decisão
Não aprovar ainda. Bloqueiam: N1 e N2 (campo de data fabricado alimenta a verdade de treino). N3–N5 não bloqueiam.
