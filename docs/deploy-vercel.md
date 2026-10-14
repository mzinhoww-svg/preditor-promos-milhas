# Plano de deploy do dashboard na Vercel

Data: 2026-10-14. Status: **plano, sem deploy feito**. Este documento existe para Aurimar
aprovar antes do primeiro deploy em produção. Motivos para esperar: a API ainda não tem host
público (VPS bloqueada) e, na Vercel, **o primeiro deploy de um projeto novo vira produção**
mesmo sem `--prod` (lição registrada no APR-006).

## 1. O que sobe

| Item | Valor |
|---|---|
| Diretório raiz do projeto Vercel | `dashboard/` (monorepo: "Root Directory" = `dashboard`) |
| Framework | Next.js 16 (App Router), build `next build`, Node 22+ |
| Rotas | `/`, `/modelo`, `/fontes`, `/alertas` (Server Components, `force-dynamic`) e `/api/explanation` (Route Handler, proxy server-side) |
| Dados | lidos no servidor da Vercel; o navegador nunca fala com a API da VPS |
| Cache | nenhum (`cache: "no-store"`): falha da API aparece na hora e a tela mostra a idade do dado |
| O que **não** sobe | nada do Python, banco, coletores ou job; nenhuma chave no bundle (`npm run build` + `grep` em `.next/static` confirmam) |

## 2. Projeto e ambiente

1. Criar o projeto na Vercel a partir do repositório `mzinhoww-svg/preditor-promos-milhas`,
   branch de produção `main`, Root Directory `dashboard`. Não importar `.env`.
2. Proteção de acesso: ligar **Vercel Authentication** (ou senha, "Password Protection") em
   produção e previews até o painel ter login próprio. O painel não tem autenticação.
3. Variáveis de ambiente (todas "Encrypted", escopo por ambiente):

| Variável | Production | Preview | Observação |
|---|---|---|---|
| `PREDITOR_DATA_SOURCE` | `mock` no primeiro deploy; `api` quando a VPS tiver host | `mock` | `mock` força dados simulados mesmo com base configurada |
| `PREDITOR_API_BASE_URL` | vazio até a VPS ter host público; depois `https://api.<domínio>/v1` | vazio | lida só no servidor |
| `PREDITOR_API_KEY` | chave emitida na VPS (`PREDITOR_API_KEY` da API) | vazio | **nunca** `NEXT_PUBLIC_`; marcar como Sensitive |

   `NEXT_PUBLIC_API_BASE_URL` é aceita como alternativa à base, mas a recomendação é usar
   `PREDITOR_API_BASE_URL` para deixar claro que nada é exposto ao cliente.

4. Domínio: começar com `<projeto>.vercel.app`. Domínio próprio (ex. `painel.<domínio>`) só
   depois do primeiro deploy aprovado; a API da VPS precisa de HTTPS válido (Caddy) e, se
   um dia for chamada do navegador, `PREDITOR_CORS_ORIGINS` com a origem do painel (hoje
   não é necessário, as chamadas são server-side).

## 3. Sequência proposta

1. **Aprovação de Aurimar** deste plano (este arquivo).
2. Criar o projeto na Vercel com as variáveis acima em `mock`. O primeiro deploy será
   produção: o painel sobe com o aviso "Dados simulados" em todas as telas e com proteção
   de acesso ligada. Conferir `vercel inspect <url>` → `target: production` e registrar em
   `docs/ACTIONS.md`.
3. Quando a VPS tiver host público e TLS: preencher `PREDITOR_API_BASE_URL` e
   `PREDITOR_API_KEY` em Production, trocar `PREDITOR_DATA_SOURCE` para `api`, fazer
   redeploy. Se a API falhar, o painel cai sozinho para dados simulados com o aviso e o
   motivo; não derruba a tela.
4. Verificação pós-deploy: as quatro telas em 200; badge "API" na barra; `StatusStrip`
   com STOP e último job (ou "a API não expõe /v1/status" até a rota existir); abrir um
   item e ver "Baseado em N campanhas históricas"; `curl` do HTML sem a chave.
5. Rollback: "Promote to Production" do deploy anterior na Vercel, ou voltar
   `PREDITOR_DATA_SOURCE=mock` e redeploy.

## 4. Checklist antes de apertar o botão

- [ ] Aurimar aprovou este plano.
- [ ] Proteção de acesso configurada no projeto Vercel.
- [ ] Variáveis criadas como Encrypted/Sensitive; nenhuma com `NEXT_PUBLIC_` além da base.
- [ ] `npm run lint`, `npm test` e `npm run build` verdes no commit a publicar.
- [ ] Limite da API (60 req/min por chave) compatível com o uso: 3–4 chamadas por tela sem
      cache (cerca de 15 aberturas de tela por minuto); explicação por item sob demanda.
- [ ] Registro em `docs/ACTIONS.md` com data, URL e `target`.

## 5. Alternativas consideradas

- **Preview antes de produção**: na Vercel, só existe preview depois de haver uma produção.
  Por isso o primeiro deploy entra em `mock`, protegido, e só depois a API é ligada.
- **Chamar a API do navegador** (`NEXT_PUBLIC_API_BASE_URL` + chave no cliente): rejeitado,
  a chave vazaria no bundle. O proxy server-side mantém a chave no servidor e permite cache.
- **Túnel temporário para a VPS** (Cloudflare Tunnel, Tailscale Funnel) para testar a API
  real antes do host definitivo: possível, mas é decisão de infraestrutura de Aurimar.
