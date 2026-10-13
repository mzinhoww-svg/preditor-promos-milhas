# Dashboard (Next.js, Vercel)

Painel do preditor de promoções: previsões ranqueadas, métricas do modelo, saúde das fontes e alertas.

```
cp .env.example .env.local   # sem PREDITOR_API_BASE_URL usa dashboard/mock/
npm install
npm run dev -- -p 3100
```

- Contrato da API: `../docs/api-contract.md`. Os JSON em `mock/` seguem o mesmo formato.
- Camada de acesso: `lib/api/` (`getPredictions`, `getModelMetrics`, `getSourceHealth`, `getAccuracy`).
  Trocar de mock para API é definir `PREDITOR_API_BASE_URL` e `PREDITOR_API_KEY` no servidor (Vercel).
  A chave só é lida em código de servidor (`server-only`) e vai no header `X-API-Key`.
- Checagens: `npm run lint` e `npm run build`.
