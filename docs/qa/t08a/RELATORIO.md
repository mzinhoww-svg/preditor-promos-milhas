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
