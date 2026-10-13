# Teste cruzado T09a (PR #9, commit c674daf) — resultado: DEVOLVIDO

Testador não é o autor; código do autor intocado. Ambiente: Node 24.14, npm 11.9, Chrome (Playwright), worktree próprio,
app em `next start` nas portas 3200–3208, API simulada (`fake-api.mjs`, chave fictícia) nas portas 3301–3307.

## Comandos
- `npm ci`: ok (5 vulnerabilidades *high* só em devDependencies via `braces`/eslint; `npm audit --omit=dev`: 0).
- `npm run lint`: sem saída (ok). `npm run build`: Compiled successfully, TypeScript ok, rotas `/ /alertas /fontes /modelo` dinâmicas.
- Segredos: nenhuma chave no código, nos mocks ou no histórico do PR; só `process.env.PREDITOR_API_KEY` em código `server-only`;
  nenhum `NEXT_PUBLIC_*`; header `X-API-Key` chegou à API simulada; nenhum valor de chave nem detalhe de erro da API no HTML.
- Navegador: 8 cenários × 2 viewports (390×844, 1440×900) × 4–7 rotas (`saida_browser.txt`), axe WCAG 2.1 AA, teclado.

## Passou
- Lista vazia: mensagem própria; painel de resumo com "—".
- Probabilidade 0 e 1: barra vazia/cheia, número e intervalo coerentes; sem `NaN`/`undefined`/`null` em nenhuma tela.
- API fora do ar (porta fechada), HTTP 500 com corpo de erro, JSON inválido, chave ausente: todas caem em `error.tsx`
  ("Não foi possível carregar os dados", só `digest`), sem vazar mensagem da API.
- Dados de exemplo: pílula âmbar "Dados de exemplo" fixa no cabeçalho de todas as telas em modo mock; "API" verde em modo API.
- Teclado: skip link, foco visível (outline 2px), filtros e `<details>` operáveis por Enter, ordem de tab lógica.
- Contraste (axe color-contrast): sem violações nas 4 telas, 390 e 1440.
- 390×844 e 1440×900 com dados do mock: sem rolagem horizontal; 404 customizado.

## Defeitos
| # | Sev | Defeito | Evidência | Causa raiz / sugestão |
|---|---|---|---|---|
| D1 | ALTA | Tabelas em `overflow-x-auto` não são alcançáveis por teclado: axe `scrollable-region-focusable` (serious) em `/modelo` e `/fontes` a 390 px, já com os dados de exemplo | `browser-teclado-axe.mjs` | adicionar `tabIndex={0}`, `role="region"` e `aria-label` ao contêiner rolável (WCAG 2.1.1) |
| D2 | ALTA | Textos longos sem quebra estouram o layout: nome de programa/segmento/fator de 200–300 caracteres gera largura de página de 2412 px (390) e 2987 px (1440), sobrepõe colunas de probabilidade e desloca o botão "ver fatores" para fora da tela | cenário `extremes`, `shots/extremes-desktop_.png` | `break-words`/`min-w-0`/`truncate` com `title` em `PairName`, badge de segmento, `summary` e `SummaryPanel` |
| D3 | ALTA | A página 404 diz "Dados de exemplo" mesmo com a API ativa (layout do `not-found` é pré-renderizado no build sem `PREDITOR_API_BASE_URL`): rotulagem de dados falsa | `/nao-existe` nos 6 cenários API | ler `dataSource()` em tempo de requisição (`export const dynamic = "force-dynamic"` no layout) ou não exibir a pílula quando desconhecido |
| D4 | MÉDIA | Um item com campo ausente derruba a página inteira: `windows["15"]` ou `bonus_pct` ausente → 500 em `/` (só a lista; as outras telas seguem) | cenário `missing` | validar a resposta na camada de acesso (`lib/api`), descartando/sinalizando o item inválido |
| D5 | MÉDIA | `fetch` sem timeout: API lenta pendura a tela até o limite da plataforma (curl em 10 s sem resposta) | cenário `slow` | `AbortSignal.timeout(8000)` em `getJson` |
| D6 | BAIXA | `reasons: []` mostra "Por que está na lista:" vazio; `probability` 0,0004 aparece "0%" (sem "<1%") | `extremes` | tratar vazio; formatar < 1% |
| D7 | BAIXA | README manda `cp .env.example .env.local`, mas não há `.env.example` (e `.gitignore` tem `.env*`, que o ignoraria) | `ls -a dashboard` | criar o arquivo e excluí-lo do padrão com `!.env.example` |
| D8 | BAIXA | Texto a 200% em 390 px gera rolagem horizontal (WCAG 1.4.4/1.4.10) | `kb.mjs` | revisar grades fixas do `SummaryPanel` |
| D9 | BAIXA | Chave `r.kind + r.label` e chave de item podem repetir (rank duplicado); o rodapé diz "calibradas pelo modelo em produção" também em modo mock | leitura de código | incluir índice na chave; esconder a frase em modo mock |

## Decisão
Devolvido. Bloqueiam D1, D2 e D3 (acessibilidade por teclado, layout quebrado por texto longo, rótulo de dados falso).
D4–D9 podem entrar no mesmo ciclo.

---

# Reteste (PR #9, commit 400f591) — resultado: APROVADO COM RESSALVAS

Ambiente: portas próprias 3400–3412 (app) e 3500–3510 (API simulada, chave fictícia).

## Comandos
- `npm ci` ok; `npm audit --omit=dev`: 0. `npm run lint`: sem saída. `npm run build`: ok, `/_not-found` agora dinâmica.
- Navegador (`qa-browser-run.mjs`, saída `qa-saida-reteste.txt`): 11 cenários × 390×844, 1440×900 e 195×422 (zoom 200%) × 4–7 rotas.
- axe WCAG 2.1 AA, mock e extremes, 390 e 1440: **0 violações** (antes: `scrollable-region-focusable`).

## D1–D9: todos verificados como corrigidos
| # | Resultado | Evidência |
|---|---|---|
| D1 | ok | axe sem `scrollable-region-focusable` em `/modelo` e `/fontes` a 390 px |
| D2 | ok | `extremes`: sem rolagem horizontal em 390, 1440 e 195 px nas 4 telas; sem sobreposição |
| D3 | ok | 404: "Dados de exemplo" em mock e "API" com API ativa (extremes, baddate) |
| D4 | ok no caso reportado | `missing` → `/` 200 com itens inválidos descartados e contados; `badjson` → página de erro sem conteúdo da API |
| D5 | ok | `slow`: erro em 8,2 s (antes: pendurava) |
| D6 | ok | `reasons: []` e "<1%" verificados em `extremes` |
| D7 | ok | `dashboard/.env.example` presente, liberado no `.gitignore` |
| D8 | ok | 195×422 sem rolagem horizontal nas 4 telas, mock e extremes |
| D9 | ok | rodapé em mock não afirma modelo em produção; sem aviso de chave duplicada |

## Ressalvas novas (não bloqueiam)
| # | Sev | Ressalva | Evidência | Sugestão |
|---|---|---|---|---|
| N1 | MÉDIA | O validador aceita qualquer string como data; um item com `last_offer.start_at: "nao-data"` derruba a lista inteira (500) em vez de ser descartado, e `generated_at: "lixo"` derruba as 4 telas | cenários `oddnums`, `baddate` | validar ISO (`Date.parse`) em `generated_at`, `start_at`, `end_at`, `trained_at`, `since` |
| N2 | MÉDIA | `/modelo` cai (500) quando falta `ci_brier` em `validation.by_horizon` ou `comparison.ci_delta_brier` | cenário `nociband` | exigir os campos ou tratar ausência na tela |
| N3 | BAIXA | Incoerências passam e são exibidas sem sinal: `ci_low > ci_high` ("60%–40%"), `p25 > p75`, bônus −5%, dias −3, `end_at < start_at`, nome de par vazio | `oddnums2` | descartar ou marcar `role=status` como em D4 |
| N4 | BAIXA | Status HTTP 200 em `/modelo`, `/fontes`, `/alertas` mesmo com `badjson` e `/` 500 | `badjson` | informativo (cada tela valida o seu endpoint) |

## Decisão
Aprovado para merge: D1–D9 corrigidos; N1–N2 entram no próximo ciclo (só disparam com resposta fora do contrato).
