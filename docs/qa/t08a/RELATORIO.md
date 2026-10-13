# Teste cruzado T08a (PR #3, commit 4d888b5) — resultado: DEVOLVIDO

Testador não é o autor. Código do autor não foi alterado. Reproduzir:
`python3 docs/qa/t08a/attack_baseline.py .` e `attack_walkforward.py .` (saídas em `saida_*.txt`).
Suíte do autor: `pytest -q` → 23 passed, 3 skipped (verde, mas não cobre os casos abaixo).

## Defeitos (causa raiz → correção sugerida)

| # | Sev | Defeito | Causa raiz | Sugestão |
|---|---|---|---|---|
| 1 | ALTA | Walk-forward vaza `first_seen_at`: item com start em jan e first_seen em 15/mar entra no treino do teste que começa 10/mar (W7b) | `walk_forward_splits` filtra só por `start_at`/`date_field`; ignora first_seen_at, que o glossário define como limite de informação | excluir do treino (ou mover p/ purged) itens com first_seen_at >= test_start |
| 2 | ALTA | Purge default 15d < maior horizonte (30d): rótulo de treino olha 30d à frente e cruza o início do teste (gap 23–28d em W1) | `purge_days=15` fixo, sem relação com `max(horizons)` | default = max(horizons); validar/avisar se purge < horizonte |
| 3 | ALTA | "Meses" = meses distintos presentes nos dados, não calendário: teste de 3 meses cobre 426d (W4); treino pula 2 anos (W3) | `months_sorted` indexa lista de meses com dado | fatiar por meses de calendário a partir de data |
| 4 | ALTA | Baseline não aplica dedup ±3d do glossário: mesma campanha vista 3x conta 3 eventos, P(30d) 0,402→0,497 (A5b) | `_start_dates` usa `set(starts)` de dias exatos | agrupar por (par,tipo) com janela ±3d antes de contar |
| 5 | ALTA | Oferta segmentada contamina oferta geral: sem `segmented=False` P 0,402→0,452 (A7) | `_matches` só filtra se `segmented` for passado; default None | default: geral exclui `segmented=True` |
| 6 | MÉDIA | `first_seen_at` truncado a data: evento visto às 23h entra em previsão das 08h do mesmo dia (A2: 0,30→0,52) | `_to_date` descarta hora | comparar datetime quando disponível |
| 7 | MÉDIA | Itens sem data / data inválida somem em silêncio (A9, W2), contra "nunca descartada em silêncio" | filtros `if d is not None` | retornar contador/lista `dropped` ou levantar |
| 8 | MÉDIA | `as_of` inválido ("amanha") aceito e vira "último start"; sem as_of vazio vira `date.today()` (A4/A10) | `_to_date` devolve None → fallback | levantar ValueError; as_of obrigatório |
| 9 | MÉDIA | Fonte única (peso 0,5) e `date_conflict` ignorados (A8) | campos não lidos | ponderar contagem |
| 10 | MÉDIA | Métricas: vazio → Brier/logloss 0.0 ("perfeito"); p>1, p<0, y=2, NaN aceitos (M1/M2); logloss p>1 ≈ 0 | sem validação | levantar em vazio/fora de [0,1]/NaN |
| 11 | BAIXA | B1 sem suavização: 1 evento no dia do as_of → P=1,0 em 7/15/30d; 6 eventos/12m → P(30d) B1 0,88 vs B0 0,40 (A13/A15) | taxa mensal = dias distintos / dias observados, sem prior | shrinkage p/ B0 |
| 12 | BAIXA | Parâmetros inválidos viram clamp silencioso (W10); horizon 0/-5 devolve 0.0 (A11) | `max(1, …)` | validar |
| 13 | BAIXA | Performance walk-forward: 5000 itens = 3,1 s (`_in_list` O(n²)); 50k ≈ 5 min | identidade em lista | usar set de ids |
| 14 | BAIXA | ~25 aliases e parsing de kwargs por palpite (`t`, `now`, `date`…) mascaram erro de chamada; `predict` shadow-a nome comum | API desenhada para adivinhar testes | enxugar para API única documentada |

## Passou
- Dado futuro (start > as_of) e first_seen > as_of (data) não alteram baseline (A1, A3).
- Outro par/tipo não contamina (A6); duplicata exata não muda B0 (A5); não muta entrada (A17);
  idempotente e independente da ordem (A18, A20, W12); B1 monótono em horizonte (A12).
- Walk-forward: max(train) < min(test) e gap >= purge_days em 400 casos aleatórios (W5, W6);
  sem item em dois conjuntos (W13); entrada vazia/None/1 mês/gerador → 0 splits sem erro (W9).

## Decisão
Não aprovar para merge. Devolvido ao autor: itens 1–5 bloqueiam (vazamento e regra do glossário).

---

# Reteste (PR #3, commit dc31808) — resultado: APROVADO COM RESSALVAS

## Comandos
- `pytest -q` (Python 3.12): **23 passed, 3 skipped**. `ruff check .` 0.17.0 (CI): **All checks passed**.
- `docs/qa/t08a/attack_reteste.py` (saída em `saida_reteste.txt`), 5000 itens: walk-forward 0,03 s; 20000: 0,13 s.
- Alteração de teste do autor (`test_purge_gap_respected_even_adjacent_months`, teste em fev em vez de mar): coerente com meses de calendário; não enfraquece a cobertura.

## Bloqueantes anteriores (1–5): todos corrigidos
Vazamento por `first_seen_at` (datetime, 12h exato), purge default 30d, meses de calendário, dedup ±3d,
segmentada fora da geral por default. Também: `as_of`/horizon inválidos levantam, métricas validam
(vazio, p fora de [0,1], y∉{0,1}, NaN), parâmetros inválidos levantam, perf O(n log n), peso 0,5 por
`n_sources<2`/`validated=False`/`weight`, B1 com encolhimento (0,878 → 0,709), propriedades em 600 casos aleatórios sem violação.

## Ressalvas (não bloqueiam o merge)
| # | Sev | Ressalva | Evidência | Sugestão |
|---|---|---|---|---|
| R1 | MÉDIA | `expanding` é aceito e ignorado: `expanding=True` e `False` dão treinos idênticos (janela móvel de `train_months`); o default documentado é expansivo | tamanhos de treino iguais em `attack_reteste.py` (W-exp) | usar `base_month` como início do treino quando `expanding=True`. Corrigir antes de comparar B0/B1 com C1 |
| R2 | BAIXA | 1 evento no dia do `as_of` → P(7/15/30d) = 1,0 em B0 e B1 | A13 | piso de janela (ex.: >= 30 dias) ou encolhimento no B0 |
| R3 | BAIXA | `predict_proba()` de módulo engole `segmented`/`segment_label` (aceitos em `**kwargs` e ignorados); `B0.predict(segmented=True)` funciona | sondagem: 0,2896 vs 0,9976 | repassar ou levantar `TypeError` |
| R4 | BAIXA | Itens sem data: `WalkSplit.dropped` só existe quando há split (sem split, somem); o baseline ignora registro sujo sem contagem | W2b/W2c, A9 | devolver `dropped` fora dos splits ou logar contagem |
| R5 | BAIXA | `_record_weight` lê `source_count` com `_get` mal posicionado (nunca lê; o campo do schema é `n_sources`, então sem efeito hoje); aliases `as_of_date`, `cutoff`, etc. persistem | leitura de código | remover o ramo morto e os aliases |

## Decisão
Aprovado para merge. R1 deve virar tarefa antes do uso em comparação de modelos (C1); R2–R5 são limpeza.

---

# Reteste 2 (PR #3, commit 7e5310c) — resultado: APROVADO COM RESSALVAS

## Comandos
- `pytest -q` (Python 3.12): **36 passed, 3 skipped** (13 de `tests/test_leakage.py`). `ruff check .` 0.17.0: **All checks passed**.
- Propriedade em 400 gerações aleatórias (8669 splits, `first_seen_at` aleatório até +60 d, purge 30–60 d): **0 violações** de gap
  e de `first_seen_at < test_start`. Perf 20 mil itens: walk-forward 0,16 s, B1 0,13 s.
- `attack_reteste.py`: saída em `saida_reteste2.txt` (o script para no bloco de propriedade antigo por split de treino vazio; ver R6).

## Corrigido desde dc31808
- R1 `expanding`: treino cresce (3,4,4,...) e difere da janela móvel (3,2,3,...).
- R3: `predict_proba` com argumento desconhecido (`segmented`, `asof`) levanta `TypeError`; `B0.predict(segmented=True)` funciona (0,94).
- Fail-closed de `first_seen_at` (ausente/inválido não entra), `as_of` e datas normalizados para America/Sao_Paulo (aware e naive),
  `purge_days >= max(horizons)` validado, alias `source_count` removido.

## Ressalvas (não bloqueiam o merge)
| # | Sev | Ressalva | Evidência | Sugestão |
|---|---|---|---|---|
| R6 | MÉDIA | Walk-forward emite splits com **treino vazio**: 2512 de 8669 (29%) nos casos aleatórios; com `first_seen_at` +40 d o primeiro split tem treino 1 | propriedade acima | descartar o split (e contar) ou lançar `ValueError`; hoje o consumidor treina em nada e a métrica sai "boa" |
| R7 | MÉDIA | Fail-closed é silencioso: histórico sem `first_seen_at` devolve P=0,0 sem erro nem contagem; no walk-forward vira tudo `purged` (4 splits com treino 0, `dropped`=0) | sondagem "sem first_seen_at em TODOS" | levantar `ValueError` ou expor `n_descartados_sem_first_seen` |
| R8 | MÉDIA | Peso 0,5 da fonte única **removido**: `_record_weight` devolve 1,0; fonte única pesa igual à validada (glossário exige 0,5); docstring ainda cita `weight` | sondagem de pesos | o motivo (validated/n_sources são estado final → vazamento) está certo; implementar com evidências `seen_at <= as_of` ou registrar decisão em `docs/decisions/` |
| R2 | BAIXA | (aberta) 1 evento no dia do `as_of` → P=1,0 | A13 | piso de janela |
| R4 | BAIXA | (aberta) `dropped` do walk-forward some quando não há split | W2b/W2c | expor fora dos splits |

## Decisão
Aprovado para merge com R6–R8 como pendências antes do uso em comparação com C1 (R8 exige decisão de Aurimar).
