# Teste cruzado do painel (PR #21, commit 1811ec4) — resultado: DEVOLVIDO

Testador não é o autor; código do autor intocado. Servidor do autor executado em portas 3350–3368 (`main()` fixa 3300; usei o mesmo `Handler`
e `recalc_loop` do `server.py` com porta minha). `gh`, `maestri` e `uv` simulados por scripts em `PATH`; banco próprio `qa_painel`.
Python 3.12 (o código usa `datetime.UTC`; no 3.9 do sistema o servidor nem sobe).

## Bloqueantes
| # | Defeito | Evidência | Causa raiz / sugestão |
|---|---|---|---|
| B1 | **O painel apaga o banco apontado por `DATABASE_URL`**: `collect_tests()` roda `uv run pytest` a cada ~15 s; com `DATABASE_URL` no ambiente, a suíte derrubou 9 de 10 tabelas e a linha de `raw_message` de um banco de desenvolvimento em 25 s | C11: tabelas 10 → 1, `raw_message` inexistente | testes de schema fazem downgrade/drop. Não rodar pytest no laço do painel (ler último resultado do CI/`gh run`), ou limpar `DATABASE_URL` do ambiente do subprocesso |
| B2 | **XSS armazenado**: título de PR, nome/papel de agente, ID/tarefa de `TASKS.md`, título/evidência/fase do checklist e linhas de `STATUS.md` entram por `innerHTML` sem escape. Com `<img onerror>` o script executou 5 vezes e mudou `document.title` | `xss-1440x900.png`, browser.mjs | usar `textContent`/`createElement` ou escapar `& < > " '`; CSP `default-src 'self'` |
| B3 | `peso: 1e999` (ou NaN) → `/data.json` com `NaN` literal (JSON inválido); o navegador falha em `r.json()`, o `catch` só faz `console.error` e o painel congela em "--%" sem aviso | C7, nan-1440 | validar `isfinite` em `calc_progress`; `json.dumps(..., allow_nan=False)`; mostrar banner de erro no `catch` |
| B4 | Checklist vazio, JSON inválido ou ausente produz **0%** sem nenhum aviso (indistinguível de projeto sem progresso); se `build_data()` lançar, o estado vira `{"error": ...}` e a tela mostra 0% | C5 | `load_json` devolve `None` em silêncio; propagar `checklist_error` e exibir |
| B5 | **Pytest vermelho fica invisível**: `run_cmd` descarta stdout quando `returncode != 0`, então `failed` nunca é preenchido e a tela mostra "--" e "pytest indisponivel" em vez de "N falhando" | C10 | usar stdout mesmo com rc ≠ 0 |

## Ressalvas
- Vazamento de passagem direta em `/data.json`: `status.raw` (STATUS.md inteiro), `agents.raw` (saída bruta do `maestri list`), `tests.tail`, stderr do `gh` (300 caracteres, p.ex. mensagem com token) e `checklist.raw`. Variáveis de ambiente (`DATABASE_URL`, chaves) **não** aparecem. Sanitizar/omitir `raw`.
- Porta 3300 fixa em `main()`; sem `--port`/variável de ambiente.
- Estados fora do vocabulário (`concluida`, `devolvida`, `em_correcao`) viram "Desconhecido" com fator 0 e sem alerta; `peso: "abc"` vira 1,0 em silêncio; fase desconhecida soma no geral mas não aparece nas barras.
- `parse_md_table` não trata `\|` e descarta linhas com menos de 4 colunas sem aviso; Bloqueios/Próximos passos aparecem como "n/a" com o STATUS.md real (heurística de cabeçalho).
- A lógica de cálculo existe em 3 cópias (`painel.py` na raiz, `src/preditor/painel.py`, `tools/painel/calc.py`) com ~25 aliases; testes cobrem só `src/preditor/painel.py`. Quando `gh` falha, a lista de PRs mostra "nehum" (typo) em vez do erro.

## Passou
- `gh`/`maestri`/`uv` ausentes ou com erro: seções `available: false` sem derrubar o painel; saída de `gh` inválida tratada.
- Pesos 0 (0%), 100% e 0%: cálculos corretos; peso negativo vira 0.
- Layout a 1440×900 e 1920×1080 com os dados reais: sem rolagem horizontal, legível (`real-1440x900.png`).
- Servidor só em `127.0.0.1`; variáveis de ambiente fora do `/data.json`.

## Decisão
Devolvido. B1 e B2 são críticos (perda de dados e execução de script); B3–B5 no mesmo ciclo.

---

# Reteste (PR #21, commit 26aa323) — resultado: DEVOLVIDO (1 bloqueante novo)

Servidor do autor via `python tools/painel/server.py` com `PAINEL_PORT`; `gh`/`maestri` simulados; banco `qa_painel` com tabela sentinela; Chrome 1440×900 e 1920×1080.

## Corrigido (B1–B5), verificado
| # | Resultado | Evidência |
|---|---|---|
| B1 | corrigido | em 45 s (3 ciclos) com `DATABASE_URL` no ambiente: nenhuma chamada a `uv`/`pytest` (só `gh`), o processo do painel tem só o socket LISTEN (nenhuma conexão a 5432), tabelas 2 → 2 e sentinela intacta; `run_cmd` ainda remove `DATABASE_URL` do ambiente dos subprocessos |
| B2 | corrigido no código | com o erro de B6 contornado numa cópia, `<img onerror>` em PR, agente, TASKS, STATUS, checklist e fase aparece como texto literal (0 execuções, `document.title` intacto); toda a renderização usa `textContent` |
| B3 | parcial | `allow_nan=False` e `isfinite` no cálculo; ver B7 |
| B4 | corrigido | checklist vazio/lista/JSON inválido/texto → `overall: null` e `checklist_error`, sem 0% |
| B5 | corrigido | CI vermelho vem de `gh run list/view`: `failed: 3, passed: 9`; sem pytest local |

## Bloqueantes novos
| # | Defeito | Evidência | Causa raiz / sugestão |
|---|---|---|---|
| B6 | **O script da página não compila: `SyntaxError: Identifier 'lastCi' has already been declared`**. A tela inteira fica em "--%" e sem itens, em qualquer cenário, com dados reais inclusive; o XSS "corrigido" nem chega a executar porque nada renderiza | `node --check` em `page_script_com_erro.js`; Chrome: `pageerror` nos 4 cenários; `server.py` linhas 497 (`const lastCi`, dentro de `render`) e 625 (segunda `const lastCi` no mesmo escopo) | renomear uma das variáveis; adicionar teste que extrai o `<script>` do `HTML` e roda `node --check` |
| B7 | `/data.json` continua quebrando com entrada inválida: `peso: 1e999` (Infinity no checklist) → `json.dumps(allow_nan=False)` levanta `ValueError` no handler e a conexão pendura (timeout); itens do checklist que não são objetos (`[1, "x", null]`) viram métodos embutidos (`str.title`) e levantam `TypeError` na serialização | A4 `peso 1e999`; `items: [1,"x",null]` | `checklist.raw` repassa o JSON cru; sanitizar (ou omitir `raw`), ignorar itens não-dict, devolver `{"error": ...}` em vez de derrubar o handler |

## Ressalvas
- Quando `gh` falha, a seção mostra só `falha`/`comando indisponivel` (corrigido o vazamento de stderr; perde diagnóstico); "nehum" segue digitado errado; `\|` em `TASKS.md` segue mal tratado.
- `tests/test_painel.py` não cobre `server.py` nem o HTML, por isso B6 passou.

## Decisão
Devolvido por B6 (painel inoperante no navegador) e B7. B1–B5 estão corretos e ficam aprovados.

---

# Reteste 2 (PR #21, commit 835a764) — resultado: APROVADO COM RESSALVAS

## Comandos e resultados
- `node --check` no `<script>` extraído da página: **ok** (B6 corrigido: `lastCi` / `lastCiData`).
- Chrome 1440×900 e 1920×1080 com os dados reais: **42%**, 26 itens, sem erro de página, sem rolagem horizontal.
- B7: `peso: 1e999` → `/data.json` responde (peso infinito tratado como 0, geral 0%); itens `[1,"x",null,{...}]` → só o objeto válido conta;
  `checklist.raw` não é mais repassado; JSON sempre válido (`allow_nan=False`).
- XSS (PR, agente, TASKS, STATUS, checklist, fase): `<img onerror>` aparece como texto; 0 execuções; `document.title` intacto.
- B1 (reconfirmado): só `gh` é chamado (sem `uv`/`pytest`), nenhum acesso a banco; CI vermelho via `gh`.

## Ressalvas (não bloqueiam)
- Itens não-objeto e pesos infinitos são descartados/zerados em silêncio (sem contagem nem aviso na tela).
- `gh` com falha mostra só "falha"; "nehum" com typo; `\|` em `TASKS.md`.

## Decisão
Aprovado: B6 e B7 corrigidos; B1–B5 mantidos.
