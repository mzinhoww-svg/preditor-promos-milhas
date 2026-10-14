# QA — PR #59 reteste (3f7d261: ressalvas 1–4 + revisao de honestidade) — APROVADO

Build de producao contra a API real da `main` (#50 mesclado, 127.0.0.1:8055) e contra servidor falso (11 modos + big40). Codigo intocado.

## Base
vitest 38 passed (inclui `copy.test.ts`: guardas de texto), lint e build verdes; axe (WCAG 2.x A/AA + best-practice) 0 violacoes nas 4 telas, desktop e celular, sem overflow, 0 erros de console; explicacao abre por teclado; `design-key` ausente de `.next/`.

## Honestidade (revisao do Planejador)
| Item | Resultado |
|---|---|
| Probabilidade "estimada" | API real e `is_calibrated=false` (inclusive com bins) → "probabilidade estimada"; so com bins e `is_calibrated=true` → "calibrada" |
| Bonus historico, nao previsto | "Bônus nas campanhas anteriores (P25 · P50 · P75)", "mediana histórica 80%"; 0 ocorrencias de "bônus previsto"/"faixa prevista"/"fatores que o colocaram ali" nas 4 telas e nos mocks |
| "Não decidido: dados insuficientes" sem Δ/IC | API real: "Não decidido: dados insuficientes (Livelo → Smiles: 23 campanhas no treino, mínimo 25)", nenhum Δ/IC; com comparacao real (promote Δ −0,021, IC [−0,040, −0,005]) e keep (Δ +0,004, IC [−0,010, 0,020]) os numeros aparecem |
| "B0/B1 por par (X em B1, Y em B0)" | API real: "(1 em B1, 2 em B0)"; com 40 itens a explicacao e limitada a 12 e o cabecalho diz "(0 em B1, 12 em B0, 28 sem método)"; explicacao 429/404 → "B0/B1 por par" sem contagem, sem quebrar |
| champion null (T10b) tolerado | `predictions.champion: null` e `model/metrics.champion: null` → /modelo 200, "Modelo não decidido · servindo B0/B1 por par · run mr_1", card "Servindo (sem decisão)" |
| Amostra pequena | n=9 e n=12 → "amostra pequena (n < 30)"; n=120 → sem aviso |
| "dados de HH:MM" | "dados de 00:00 UTC" (= `generated_at` do run) ao lado de "há 8 h" |
| Chamadas a API | 4 telas = 15 chamadas (3 explicacoes por abertura da home, teto 12/tela, memo de 5 min); 429 em explicacao nao derruba a tela |

## Observacoes (nao bloqueiam)
1. `docs/api-contract.md` ainda descreve `windows.*.probability` como "probabilidade calibrada" (l. 91) e `bonus_pct` como "faixa prevista do bônus" (l. 93): alinhar com a copy da tela.
2. "(Livelo → Smiles: 23 campanhas no treino, mínimo 25)" usa o par lider como proxy do treino C1×B1 e chama `n_campaigns` de "no treino"; dizer "23 campanhas conhecidas do par lider".
3. `ci_low == ci_high` da API continua mostrado como "IC indisponível" (correto); corrigir na API para nao mandar IC degenerado.
