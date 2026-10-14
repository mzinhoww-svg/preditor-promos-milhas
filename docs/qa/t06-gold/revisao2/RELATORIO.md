# QA — PR #45 (ressalvas do #44, ce389bf) — APROVADO

- 100% `gold_provisional` (50 campanhas, 95 mensagens); `MANIFEST.sha256` vazio; split 20/30 e 8/12 mantido.
- Sem texto integral: max 597 chars (0 > 600), total 34.899, 0 HTML, sem campos de corpo.
- Schemas validam **sem** extrair do markdown (`$ref` interno `#/$defs/oferta_v1`; 0 erros em 50+95 linhas).
- 5 distratores trocados (m-0081/0082/0083/0087/0088): titulos RSS do PPV, `texto == conteudo` do raw e `content_sha256` conferem, `expected.ofertas = []`, sem oferta Livelo/Smiles no titulo.
- Bonus condicional: regra no README + tag `bonus_condicional` em m-0035/0054/0055/0058 e c-0023/0034/0035/0037; valores inalterados (90/90/90/100).
- Integridade: 0 orfaos, `first_seen` = minimo das evidencias, `all_evidence_gap` consistente.
- Ressalva residual (nao bloqueia): ainda sem cobertura das categorias do §4 para distratores (expirada, cartao, bumerangue isolado) — declarado no README.
