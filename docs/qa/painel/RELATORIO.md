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
