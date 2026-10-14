# QA — PR #65 job diario e2e local + colisao de segmentos (0a16907) — APROVADO

Bancos proprios: `qa_pr65t` (vazio, suite) e `qa_pr65` (`TEMPLATE preditor_p2` migrado a 0008, dados reais). `preditor_p2` nao tocado.

| Item | Resultado |
|---|---|
| Suite / lint | 303 passed (300 + 3 novos), ruff limpo |
| TDD | `test_e2e_segment_collision.py` contra o `daily_predict.py` da main: 2 falham (grupo segmentado vence; conflitos contados como inseridos), 1 passa; com a correcao, 3 passam |
| Job em dados reais (0008), as_of 2026-10-14 | `{'pairs': 3, 'inserted_predictions': 9, 'inserted_logs': 9, 'model_run_id': 1, 'alerts': 0}`; 9 linhas em `prediction`, 9 em `prediction_log`, 1 `model_run` (role daily); **0 series duplicadas** por (par, tipo, horizonte) |
| Series publicadas (= ACTIONS) | livelo→smiles 23 campanhas, B0, 0,113 / 0,227 / 0,402; livelo→latam_pass 3, B0, 0,029 / 0,061 / 0,119; esfera→azul 1 (so segmentada), B0, 0,021 / 0,044 / 0,087 |
| Reexecucao | `inserted_predictions: 0`, `inserted_logs: 0`; linhas 9 / 9 |
| Retroativo semanal 2025-01-05..2026-09-13 | 89 execucoes sem falha; log **672** linhas (7 = 224, 15 = 224, 30 = 224), todas B0; **3 alertas** (esfera→azul, 2025-11-23, P = 0,721 / 0,935 / 0,996) |
| Acuracia (`/v1/prediction-log/accuracy`) | n = 221 por horizonte; hit 0,050 / 0,113 / 0,208; Brier 0,051 / 0,104 / 0,167; log-loss 0,204 / 0,353 / 0,522 — **identico ao ACTIONS** |
| Por par, 30 d (recomputado fora da API) | livelo→smiles 89 linhas, 36 acertos, Brier 0,244; latam_pass 89 / 10 / 0,111; esfera→azul 43 / 0 / 0,122 — identico |

## Observacoes (nao bloqueiam)
1. **Baseline "constante":** o ACTIONS compara com a taxa media global (0,279 / 0,109 / 0,043). Com a constante **por par** (taxa do proprio par) fica 0,241 / 0,100 / 0,000: o modelo (0,244 / 0,111 / 0,122) **nao bate** a constante por par. A conclusao "nao ha base para afirmar acuracia" ja esta no texto; vale citar as duas.
2. **Uma serie por par = grupo com mais campanhas:** o par livelo→smiles publica o grupo base (23) e descarta as 4 campanhas segmentadas; como o metodo e escolhido por grupo (23 < 25), o B1 nunca entra para o par apesar de 27 utilizaveis. Decisao de modelagem a registrar (e e a base da correcao pedida no PR #64).
3. **Retroativo no log append-only:** `daily --as-of` passado grava em `prediction_log` (append-only) linhas de backtest com `logged_at` antigo; em banco de producao seria irreversivel. A doc avisa; falta uma trava (flag `--backtest` ou recusar `as_of` < hoje sem confirmacao).
4. `esfera→azul` com n=1 vira P(30d)=0,996 e gera os 3 alertas (ruido, ja listado no ACTIONS); `run_accuracy` ignora `engine` (`if False`, l. 270).
