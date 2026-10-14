# QA — PR #48 follow-up do #36 (6d2e998) — APROVADO COM RESSALVAS

Banco proprio `qa_pr48` (vazio + copia de `raw_message` do `preditor_p2` p/ reprocess); `preditor_p2` so SELECT. Codigo intocado.

## Verificado
| Item | Resultado |
|---|---|
| Suite / lint / alembic | 240 passed (banco vazio), ruff limpo, head unico `0005`; testes de API/loader/gap tambem passam com banco populado (64 ofertas, 1.239 raw) |
| Relatorio vs banco | bate com `preditor_p2`: 64 ofertas (livelo→smiles 55, latam_pass 5, esfera→smiles 3, esfera→azul 1), 7 validadas, 27 sem so-gap, 1 sem bonus, `published_at` 877/897 no PPV, 1.239 raw / 177 gap |
| Reprocess | reextracao da copia → 64 ofertas, 0 diferencas vs banco do autor, idempotente |
| Falsos antigos | 0 ofertas 110/58%; livelo→esfera e smiles→esfera invalidas sumiram; bonus nulo 6 → 1 |
| Loader | `first_seen_at` so de evidencias sem gap: 11/11 ofertas mistas = min(observed_at sem gap) (na tabela ja era igual: 0 mudancas); sem `validated`/`n_sources`/`weight` (campos: bonus_pct, destination, end_at, event_type, first_seen_at, gap_only, origin, segment_label, segmented, start_at) |
| `recompute_gap` | nao zera `published_at` de titulos RSS (877 preservados) |
| Portao no ACTIONS.md | corrigido: "atende so para o B1 no job (27)"; treino do walk-forward 23 < 25 → `keep_champion` (confere com o evaluate real) |
| Extracao | "inclusive Livelo e Esfera – para a Smiles" → livelo→smiles; "exceto Esfera" → sem par (nao inventa); "milhas/pontos bonus" contam como bonus (LATAM 35%); controle simples ok |

## Ressalvas
1. **Regressao de recall no extrator:** o novo `re.sub(r"\b(?:exceto|menos|salvo)\b\s+[^.;,]*", "", ...)` apaga o resto da frase ate o primeiro `. ; ,`. "Em **menos** de um dia a Smiles anunciou ate 90% de bonus nas transferencias de pontos da Livelo." perde o par (None, None) — na `main` (a6afd98) o par era livelo→smiles. Restringir a "exceto/salvo" seguidos de programa/ate a virgula, ou nao incluir "menos".
2. **Teste de "sem estado final" e textual e contornavel:** pega `.get("n_sources")` e `'weight'` em model/baseline/walkforward, mas passa com chave concatenada (`"n_"+"sources"`), `itemgetter("val" "idated")` e com um modulo novo (`c1_features.py` usando `.validated`) — so 3 arquivos sao lidos. Considerar teste por comportamento (loader/feature list) em vez de grep.
3. `jobs/daily_predict.fetch_offers` ainda le `offer.first_seen_at` direto (nao o first_seen sem gap do loader); hoje sao iguais (0 diferencas nas 11 mistas), mas e a mesma regra em dois lugares.
4. Herdado: 877/897 PPV com `published_at` (20 sem data no feed).
