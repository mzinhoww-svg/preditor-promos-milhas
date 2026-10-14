# QA — PR #49 reteste (50c7227) — APROVADO COM RESSALVAS

Banco proprio `qa_pr49c`; rede simulada (stubs). Codigo intocado.

## Verificado
| Item | Resultado |
|---|---|
| Suite / lint / alembic | 255 passed, ruff limpo, head 0005; merge limpo com `main` |
| Regressao dos ataques anteriores | robots 403/Disallow por URL e do feed/404, ritmo 6 sleeps/9 req, idempotencia, PPV so titulo (46 B), feed 500/XML quebrado, artigos 404 + retomada: iguais ao df843e0 |
| URL canonica | `http://www.…/Artigo-A/?utm#frag` ja gravada reconhece `https://…/artigo-a/` (0 buscas); variantes http/https, www, query, barra final nao duplicam; link gravado e `https` sem query (U1/U2) |
| Teto 200 req/dia por dominio | em 198: executa robots+feed e para (`daily_cap_reached`, count=200 persistido); mesmo dia 0 requisicoes; dia seguinte reseta e coleta (D1–D3) |
| Pausa 1 h apos 429/503 | 429 em artigo: grava `pause_until`, interrompe, 30 min depois `paused` com 0 requisicoes, 61 min depois retoma; 503 no robots e 429 no feed tambem pausam (P1–P6) |
| `robots_changed` | agora e calculado (ultimo hash != anterior): true quando acabou de mudar (h0→h1) e com `None` no meio |
| Exit code | `paused`/`daily_cap_reached` contam como sucesso |

## Ressalvas
1. **Excecao interna ainda aborta o ciclo** (X4, do parecer anterior): `_store` levantando em PdP derruba `run_once`; MC nao roda e a fonte que falhou nao ganha linha em `source_health`.
2. **`clean_link` + canonica colapsam links por query:** feed com `?p=101`, `?p=102`, `?p=103` grava 1 item (`https://dominio/`) e trata os outros como conhecidos (U3); caminhos que diferem so por caixa viram o mesmo (U4). Hoje PdP/PdP/MC usam permalinks bonitos; nao remover query quando o path for vazio e nao baixar a caixa do path.
3. **Estado do teto/pausa:** `STATE_PATH` e relativo ao cwd (cron em outro diretorio perde teto e pausa); arquivo corrompido reinicia a contagem em silencio (S1); estado so e gravado no fim do ciclo — falha no meio perde a contagem (S2).
4. **`robots_changed` segue efemero:** `h0,h1,h1` volta a false no check seguinte; guardar a ultima mudanca (timestamp) para o painel.
5. Pausa/teto nao geram linha em `source_health` (a fonte nao aparece como `paused` na API); pacing do 1º request por dominio nao persiste entre execucoes; titulos repetidos (E2) e wildcards de robots inalterados.
6. **Conflito de merge com o PR #50** em `api/queries.py` (`fetch_source_health`): unificar na ordem de merge.
