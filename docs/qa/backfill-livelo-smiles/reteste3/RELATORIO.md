# QA — PR #36 reteste 3 (733405f) — APROVADO COM RESSALVAS

Banco proprio (`qa_bf5` vazio → `alembic upgrade head`; `qa_bf4` com copia de `raw_message` do `preditor_p2` para o reprocess); `preditor_p2` so SELECT. Codigo intocado.

## Verificado
| Item | Resultado |
|---|---|
| alembic | head unico `0005` em banco vazio |
| Suite / lint | 231 passed (banco vazio), ruff limpo |
| Relatorio `docs/ACTIONS.md` vs `preditor_p2` | **todos os numeros batem**: 1.239 raw (314 PdP + 28 MC + 897 PPV), 177 com gap, 66 ofertas, 54 livelo→smiles, 7 validadas (4 sem gap), 27 so-gap / 27 nao-gap, 47 meses distintos, 12 campanhas em 10 meses nos ultimos 24 (ultima 2026-03-11), 111 evidencias / 92 `start_inferred`, outros pares 5/3/2/1/1 |
| Reprocess | reextracao dos 1.239 raw (copia) → **66 ofertas, 0 diferencas** contra o banco do autor; 2a execucao identica (idempotente); 3 prorrogacoes fundidas |
| Ouro (49 campanhas livelo→smiles) | 47/49 encontradas (inicio ±3 d) e 45/49 com bonus correto — igual ao relatorio; faltam c-0028 (dev) e c-0050 (test) |
| Ouro dev/test (mensagens) | dev 28/28 pares e bonus, fim 22/28 (79%), 0 FP em 8; test (so reportado) 47/47, bonus 46, fim 33 (70%), 1 FP em 12 — igual ao relatorio; `tests/test_gold_dev.py` so assere no dev; nenhum id do ouro hardcoded em `src/` |
| Loader `load_offer_records` | devolve 66 registros com `gap_only` (33 so-gap); `exclude_gap_only` → 33; `evaluate_c1_vs_b1` com o loader: 500 linhas vs **1.338** sem o campo → so-gap realmente fora; gate: 23 campanhas de treino em livelo→smiles (< 25) → `keep_champion` |
| Falsos positivos antigos | 0 ofertas com bonus 110 ou 58; 10 das 11 ofertas do 62f0602 descartadas como o relatorio diz |
| RSS arquivado | 897 titulos PPV no banco; nenhuma oferta gerada (so titulo) |

## Ressalvas (nao bloqueiam)
1. **PPV sem `published_at`:** 897/897 linhas com `published_at` NULL e gap = false, embora o feed arquivado traga `<pubDate>` (verifiquei a captura 20230819170544 e o HEAD grava o campo, teste com a captura real). O banco foi populado por uma versao anterior: o gap de 72% da base nao foi medido. Reexecutar `--rss-archive`/recompute antes de usar titulos PPV como oferta.
2. **Pares fora do alvo com erros:** oferta 79 livelo→esfera 90% (frase "... de todos os parceiros – inclusive Livelo e Esfera – para a Smiles": destino e Smiles) e oferta 81 smiles→esfera 70% ("... exceto Esfera": Esfera esta excluida). 6 ofertas com `bonus_pct` NULL (2 livelo→smiles contam entre as 54; ex.: oferta 69 "ate 100% de milhas bonus").
3. **Portao:** "campanhas ≥ 25: 54, atende" — so 27 sao utilizaveis (sem gap) e 23 caem no treino do walk-forward; o relatorio ja diz "metade", mas o status deveria ser "atende so com as 27 sem gap". Ultimos 24 meses: nao atende (declarado).
4. **Testes dependem do estado do banco:** com o banco populado (reprocess), `test_job_daily_runs_with_offers` e `test_prediction_accuracy_with_data_no_500` falham por colisao de unicidade; passam em banco vazio.
5. `start_inferred` = 92/111 evidencias (inicio e a data em que a oferta foi vista) e 1 fonte para 47/54 campanhas — declarado no relatorio.
