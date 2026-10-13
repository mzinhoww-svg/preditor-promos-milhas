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
