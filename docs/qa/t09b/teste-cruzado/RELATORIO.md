# QA — PR #56 T09b dashboard ligado a API real (7105010) — APROVADO COM RESSALVAS

Dashboard em build de producao (`next start`) contra a API real do PR #50 (127.0.0.1:8055, so GET) e contra um servidor falso com 14 modos de falha/contrato. Codigo intocado.

## Passou
| Item | Resultado |
|---|---|
| lint / test / build | verdes; vitest 17 passed |
| Telas com API real | 4 telas 200, badge API, sem "Dados simulados"; numeros batem com o JSON da API: lider 7 d Livelo→Smiles 20% (mediana 80%), pares ≥50% em 7 d 0/3 e 30 d 2/3, producao Brier 0,319 / acerto 33% / 9 resolvidas (= `/prediction-log/accuracy` 30 d), fontes 1 operando/2 com problema, 5 cruzamentos de limiar (= `/v1/alerts`) |
| Selo B0/B1 | por item: Livelo→Smiles (23 campanhas) "B0 · taxa-base"; modelo "C1" fora de `promote_challenger` → "Modelo não decidido"; com `promote_challenger` → "C1" |
| Fallback "Dados simulados" | 401, 500, 429, timeout (8 s), corpo nao-JSON → 4 telas 200 com aviso e motivo ("devolveu erro", "nao respondeu a tempo", "corpo que nao e JSON"); sem lixo ("undefined"/"NaN"/"null") |
| Contrato/validacao | probabilidade 1,7/"0,5"/−0,2 → 3 itens descartados com aviso; campo ausente → 1 descartado com aviso; lista vazia → "Nenhuma previsao"; contadores nulos tolerados; 500 itens → 50 exibidos |
| Explicacao por item | `/api/explanation`: 200 com dados ("Baseado em 23 campanhas historicas · abaixo das 25 que o B1 exige", ultima campanha ha 72 d — confere), 404 para par inexistente, 400 para `..%2F`, `<script>`, tipo invalido e vazio; abre por teclado (Enter no `summary`) |
| STOP/ultimo job | `/v1/status` 404 → "Desconhecido · a API nao expoe /v1/status"; ultimo job "ha menos de 1 h" |
| Segredos | `design-key` ausente em `.next/` e no HTML; chave so no servidor |
| Seguranca de render | nomes com `<img onerror>`/`<script>` aparecem como texto escapado, nada executa |
| Acessibilidade | axe (WCAG 2.x A/AA + best-practice) 0 violacoes nas 4 telas, desktop e celular; sem overflow horizontal; 0 erros de console |
| Docs | `deploy-vercel.md`: plano sem deploy, sem segredos, primeiro deploy em `mock` e protegido |

## Ressalvas
1. **Comparacao sem dados exibida como medida:** com `comparison = {delta_brier: 0.0, ci: [0,0], decision: keep_champion, note: "sem dados suficientes"}` a tela mostra "Campeao mantido · Δ Brier 0,000 · IC 0,000 a 0,000". Tratar `note`/folds=0 como "sem dados" em vez de zeros.
2. **Cabecalho x item:** "Modelo em producao B1 · hazard empirico" enquanto o 1º item e B0 (par com 23 campanhas); o cabecalho deveria dizer "B0/B1 por par" quando houver mistura.
3. **Cache mascara falha da API por ate 5 min** (`revalidate: 300`, persistido em `.next/cache` entre reinicios): derrubar a API logo apos uma resposta boa continua mostrando badge "API" sem aviso; documentado como cache, mas o STOP/ultimo job tambem ficam ate 5 min defasados.
4. Itens com 1 janela invalida sao descartados por inteiro (3 de 3 em `prob_invalid`); aviso aparece, mas o item some da lista em vez de mostrar as janelas validas.
5. Herdada do #50: `/v1/predictions` com campeao C1 nomeia C1 sem que as predicoes sejam do C1 — o selo "Modelo nao decidido" protege o painel, mas o `model.name` da API segue enganoso.
