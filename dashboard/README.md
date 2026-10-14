# Dashboard (Next.js, Vercel)

Painel do preditor de promoções: previsões ranqueadas com explicação por item, métricas do
modelo, saúde das fontes, alertas e estado de operação (STOP, último job, base histórica).

```
cp .env.example .env.local   # sem PREDITOR_API_BASE_URL usa dashboard/mock/ ("Dados simulados")
npm install
npm run dev -- -p 3100
```

- Contrato da API: `../docs/api-contract.md`. Os JSON em `mock/` seguem o mesmo formato e
  passam pela mesma validação.
- Camada de acesso: `lib/api/` (`getPredictions`, `getModelMetrics`, `getSourceHealth`,
  `getAccuracy`, `getThresholdAlerts`, `getStatus`, `getExplanation`). Trocar de mock para
  API é definir `PREDITOR_API_BASE_URL` (ou `NEXT_PUBLIC_API_BASE_URL`) e `PREDITOR_API_KEY`
  no servidor. A chave só é lida em código de servidor (`server-only`) e vai no header
  `X-API-Key`; com a API configurada, qualquer falha cai para os dados simulados com aviso.
- Explicação por item: rota `app/api/explanation` (proxy server-side), chamada pelo
  componente cliente só quando o bloco "Por que está na lista" é aberto.
- Checagens: `npm run lint`, `npm test` (vitest, validadores) e `npm run build`.
- Teste com a API real em local: suba um Postgres descartável, rode as migrações e o job
  (`python -m preditor.jobs.daily_predict all`), `uvicorn preditor.api.app:app --port 8055`
  com `PREDITOR_API_KEY`, e `PREDITOR_API_BASE_URL=http://127.0.0.1:8055/v1 npm run dev`.
- Deploy: `../docs/deploy-vercel.md` (plano; sem deploy feito).
