# QA — PR #59 (ressalvas 1–4 do #57, aacd7cd) — APROVADO

Dashboard em build de producao contra a API real do #50 e contra servidor falso (13 modos + 2). Codigo intocado.

| Ressalva | Correcao | Resultado do reteste |
|---|---|---|
| 1. comparacao sem dados como zeros | `has_data` falso quando decisao `insufficient_data`, nota "sem dados", Δ=0/IC=[0,0] ou comparacao nula | API real, `insufficient_data` e `comparison: null` → **"Sem dados"** (nenhum Δ 0,000); comparacao real (Δ −0,021, IC [−0,04, −0,005], promote) e Δ=0 com IC [−0,01, 0,01] e folds>0 → numeros exibidos |
| 2. cabecalho B1 com item B0 | `headerModel`: mistura/ambiguidade → "B0/B1 por par" | API real (nome B1, metodo desconhecido) e itens b0+b1 → "B0/B1 por par"; so b0 ou nome B0 → "B0 · taxa-base"; C1 sem promote → "Modelo não decidido" |
| 3. cache mascara falha | `cache: "no-store"` + `Freshness` ("API consultada há X · dados gerados há Y", selo "dado velho" > 36 h) | API boa → derrubada na mesma instancia: a requisicao seguinte ja mostra "Dados simulados"; frescor nas 4 telas; gerado ha 3 h → "há 3 h" sem selo; ha 3 dias → "dado velho"; rota `/api/explanation` com `Cache-Control: no-store` |
| 4. janela invalida descarta item | janela invalida vira `null`, sinalizada "janela inválida" | 1 janela invalida → item mantido (4 linhas) com 1 "janela inválida"; 7 d e 30 d invalidas → 2 sinalizadas; as 3 invalidas → item descartado com aviso "1 item … descartado"; nenhum "undefined/NaN" |

Regressao: lint e build verdes, vitest 28 passed; axe (WCAG 2.x A/AA + best-practice) 0 violacoes nas 4 telas desktop e celular, sem overflow, 0 erros de console; explicacao por teclado ok; chave nao vaza.

## Observacoes (nao bloqueiam)
1. KPI "Pares com ≥ 50% em N dias": item com janela N invalida segue contado em "acompanhados" (denominador) e nao como cruzamento (subestima levemente, ex. 1 de 3 em vez de 2 de 3); considerar excluir do denominador ou sinalizar.
2. Cabecalho "B0/B1 por par" tambem aparece quando todos os pares sao B1 mas o metodo por item nao vem na lista (`/predictions` ainda nao traz `method`); resolver com o campo proposto no contrato.
3. Sem cache, cada tela custa 3–4 chamadas e cada explicacao aberta 1 chamada; limite da API 60/min por chave — ok para uso humano.
