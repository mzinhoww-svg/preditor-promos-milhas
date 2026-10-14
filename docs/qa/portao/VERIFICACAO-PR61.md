# QA — verificacao do PR #61 (relatorio do portao, ae78fa2) — APROVADO COM 3 OBSERVACOES

Fontes: `preditor_p2` (so SELECT) e uma copia `CREATE DATABASE … TEMPLATE preditor_p2` migrada ate 0008 onde o `run_champion_challenger` foi reexecutado (main 3a52046). Banco e copia nao foram alterados alem da copia descartavel.

## Numeros conferidos (todos batem)
| Item do relatorio | Banco / reexecucao |
|---|---|
| raw 1.239 (314 / 28 / 897), gap 177 (169 / 8 / 0) | 1239 (314 / 28 / 897), 177 (169 / 8 / 0) |
| livelo→smiles 55, validadas 7 (13%), 47 meses, 27 utilizaveis (28 so-gap) | 55, 7, 47, 27 (28) |
| ultimos 24 meses 12, ultima 2026-03-11, periodo 2020-02 a 2026-03 | 12, 2026-03-11, 2020-02 a 2026-03 |
| latam_pass 5/0/5/3/4 (2020-08 a 2025-09); esfera→smiles 3/0/3/0/1 (2023-08 a 2025-03); esfera→azul 1/0/1/1/1 (2025-11); 0 purchase/boosted | identicos |
| 90 de 109 evidencias com `start_inferred` | 90 de 109 |
| `prediction_log` do `preditor_p2` vazio (n = 0) | 0 (prediction e model_run tambem 0) |
| C1 × B1: 10 dobras (2023-09-24 a 2025-12-20; 3 a 29 no treino), 3.471 linhas / 651 positivas, campanhas 23/3/1 | identicos |
| Brier B1 0,125 / C1 0,306; log-loss 0,376 / 1,261; IC Δ Brier [−0,239; −0,126]; IC Δ log-loss [−1,146; −0,630]; nao calibrado; keep_champion | 0,1247 / 0,3061; 0,3757 / 1,2612; [−0,2393; −0,1262]; [−0,1146…] [−1,1462; −0,6303]; calibrado=false; keep_champion (motivos: 23 < 25, C1 nao menor, IC, nao calibrado) |
| ouro: 23 de 50 campanhas so-gap; dev 28/28 pares e bonus, fim 79% | 23 de 50; dev 28/28/28, fim 22/28 |
| "relatorio antigo (t08b-champion-decision.md) e sintetico" | banner SINTETICO no arquivo da main |

## Texto vs dado (nao afirma mais que o dado, com 3 ressalvas)
1. **Contrafactual no resumo:** "Não haveria promoção mesmo com dados suficientes" afirma o que nao foi medido. A avaliacao treina o C1 com 3 a 29 campanhas por dobra; ela mostra que **com estes dados** o C1 perde (a secao 4 diz isso corretamente). Trocar por "com estes dados, o C1 perde para o B1 …".
2. **316 × 314:** "o backfill baixou 316 de 9.750 URLs" vs 314 `raw_message` do PdP (diferenca de 2, provavel dedupe por `content_hash`); dizer "316 baixadas (314 gravadas)".
3. **"Período observado 2015-02 a 2026-10"** e o `observed_at` (minimo entre publicacao e captura); as campanhas comecam em 2020-02. Rotular como "observed_at" para nao parecer cobertura de 2015.

Resto: separa real × sintetico, deixa claro que os 0,319/n=9 dos testes sao replay e nao producao, e declara o buraco recente (nenhuma campanha apos 2026-03-11), a 2a fonte fraca e os tipos ausentes.
