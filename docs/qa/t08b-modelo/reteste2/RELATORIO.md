# QA — T08b reteste 2 (PR #27 @ 0b03645) — APROVADO COM CONDICOES

Banco proprio (`qa_t08b_r2`), venv 3.12, worktree em 0b03645. Codigo do autor intocado; mutacoes aplicadas e revertidas por `mutate27.py` (diff verificado: `restaurado`).

## O que passou
- 160 passed (`t08b_suite.txt`); head unico 0003 (base main).
- Portao `decide_champion`: falha fechada (sem dados/sinteticos/<25/sem IC/nao calibrado); sinal verificado nos dois sentidos (C1 melhor -> ci_low>0; trocando B1<->C1 nao promove).
- `evaluate_c1_vs_b1`: vazio/poucos -> ValueError limpo; duplicatas nao inflam campanhas (143 = 143) nem alteram p_c1; determinismo (mesma seed -> mesmos p e IC); datas invalidas ignoradas; `purge_days < max(h)` rejeitado.
- Relatorio: banner SINTETICO emitido (docs/reports/t08b-champion-decision.md versionado) — condicao 2 do ciclo anterior atendida.
- `predict_proba(c1)`: 1,6 s (antes 53 s); p15 = 0,99 (clamp).
- Mutacao M0 (bug original, `_first_seen_dt(registro)` -> None): agora FALHA (5 failed + 4 errors) — condicao 1 (parte bug original) atendida.
- Invariancia: 40 ofertas tardias (first_seen apos o teste, bonus 300) nao alteram nenhuma das 1149 predicoes B1/C1 (`probe27.py`).

## O que NAO esta coberto (condicao)
Mutacoes que introduzem vazamento parcial e **mudam as predicoes** (hash de p_c1 e Brier diferem) passam em toda a suite (56 passed em modelo/portao/leakage/walkforward):

| Mutacao | p_c1 muda? | Brier C1 | Testes que falham |
|---|---|---|---|
| orig | — | 0,0583 | — |
| M1 `_available_offers` ignora t | sim | 0,0549 | nenhum |
| M2 treino sem cutoff/purge | sim | 0,0540 | nenhum |
| M4 `fit(recs, as_of=data_end)` | sim | 0,0481 | nenhum |
| M7 grade/features sem filtro `fs<=t` | sim | 0,0573 | nenhum |
| M6 vazamento total na predicao (M1+M3+M5) | sim | 0,0520 | 1 (`late_first_seen...`) |
| M3, M5 (guardas redundantes) | nao (equivalentes) | 0,0583 | — |

O unico teste de invariancia usa 2 registros em 2030; uma oferta tardia dentro da janela nao e exercitada. Logo, "ha teste que falha se o futuro vazar" vale so para vazamento grosseiro.

## Condicoes para fechar
1. Teste de invariancia por fold: remover/alterar registros com `first_seen_at` > fim do fold (e dentro da janela de teste, bonus extremo) nao pode mudar p_b1/p_c1 das linhas comuns (modelo em `probe27.py`); e um teste que o treino da dobra so ve `first_seen <= cutoff` (M2/M4).
2. Teste da grade: features em `t` ignoram registros com first_seen > t (M7) e `_feature_row` nao depende de `records` nao filtrados.
3. Renumerar `0003_calendar_seed` (colide com `0003_prediction_log_unique` do T10a quando ambos entrarem).

## Ressalvas
- `data_source` e declarado pelo chamador: mundo sintetico rotulado "real" com 38-57 campanhas/par PROMOVE C1 (`attack27_r2.out`). So `synthetic=True` por registro e honrado; sem prova de procedencia.
- Sem embargo treino<->calibracao documentado alem do purge ja testado.
