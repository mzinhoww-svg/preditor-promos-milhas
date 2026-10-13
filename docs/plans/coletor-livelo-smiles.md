# Spec T05: coletor Livelo → Smiles

Data: 2026-10-13. Autor: revisor/spec. Status: revisada após o QA do PR #2. A decisão 002 foi aceita por Aurimar (opção C), e o purge segue a decisão 003.

Escopo: bônus de transferência Livelo → Smiles, com histórico de 24 meses ou mais. O Telegram fica fora, conforme `docs/decisions/001`. Este documento não coleta conteúdo. Ele define o que coletar, como coletar e quando a coleta é considerada pronta.

## 1. Permissão de coleta por fonte

Verificação feita em 2026-10-13 com User-Agent `preditor-promos-milhas/0.1`. Li apenas os arquivos `robots.txt`, as páginas de termos e privacidade e o cabeçalho dos feeds. Não li artigos.

| Fonte | robots.txt | Termos de uso | Feed RSS | Coleta recorrente |
|---|---|---|---|---|
| Passageiro de Primeira (`passageirodeprimeira.com`) | `User-agent: *` bloqueia só `/wp-admin/`, `/destaques-json-api/`, `/view-widget/`, `/grupos/`, `/ppsfb/`, `/ppstt/`, `/ppsxx/`, `/categorias/classe-economica/` e o tema. Artigos, tags e `/feed/` estão liberados. | `/termos-de-uso/` traz só regras de comentários e links. Não tem cláusula sobre robôs, scraping ou reprodução. | `/feed/` e `/tag/livelo/feed/` respondem 200 `application/rss+xml`. | **Permitida** por robots, para feed e artigos, com limite de taxa. |
| Melhores Cartões (`www.melhorescartoes.com.br`) | `User-agent: *` com `Disallow:` vazio (Yoast). Bloqueia só um JSON interno de plugin. | Não há página de termos publicada (`/termos-de-uso` responde 404). O rodapé diz "Todos os direitos reservados". A política de privacidade não trata de robôs. | `/feed` responde 200 `application/rss+xml`. | **Permitida** por robots. |
| Pontos pra Voar (`pontospravoar.com`, rede BoardingArea) | Política BA-3.1, de 2026-08-27. `User-agent: *` tem acesso total, salvo higiene (`/wp-admin/`, `?s=`, `/search/`, `?preview=`, `?replytocom=`, `/trackback/`, `/comments/feed/`). Bloqueia `/` para robôs de treino de IA (GPTBot, ClaudeBot, CCBot, Bytespider, cohere, Diffbot, etc.). O aviso de direitos proíbe usar o conteúdo **para treinar modelos generativos** e reserva TDM (art. 4 da Diretiva UE 2019/790). | Os termos da BoardingArea (`boardingarea.com/terms/`) declaram direitos autorais sobre a compilação e os artigos e vedam uso "que não tenha sido autorizado". Não há cláusula específica de robôs. | `/feed/` e `/tag/livelo/feed/` respondem 200 `application/rss+xml`. | **Permitida com restrição.** Nosso UA não cai em grupo bloqueado, mas o uso não pode ser treino de IA. Coleta só de título, data e link (decisão 002, opção C). |

Regras de coleta que valem para as três fontes (o PR do coletor só passa se cumprir todas):

1. O `robots.txt` é relido a cada execução, com cache de no máximo 24 h, e consultado por URL com `urllib.robotparser`. Uma URL bloqueada é pulada e registrada em log.
2. A coleta recorrente usa **só o feed RSS**: `/feed/` geral, filtrado localmente. As páginas de artigo são lidas só quando o item do feed casa com o pré-filtro (seção 3.3). A busca interna (`?s=`) nunca é usada.
3. Nos domínios das fontes, o ritmo é de no máximo 1 requisição a cada 10 s, com teto de 200 requisições por dia por domínio. Na `web.archive.org`, que não é fonte e tem limite próprio, o ritmo é de 1 req a cada 2 s na CDX e 1 a cada 4 s nos downloads `id_`, com teto de 2.000 requisições por dia. Um 429 ou 503 pausa o domínio por 1 h.
4. O UA identificável é o atual de `wayback.py`, com o link do repositório.
5. Armazenamento e publicação:
   - `raw_message` guarda o HTML/texto para extrair fatos (datas, %, par). O banco é local e não é publicado.
   - O repositório é público, então **não se commita texto integral de artigo**. As fixtures devem ser sintéticas ou ter só trechos curtos factuais (ver 4.2).
   - O dashboard mostra só os fatos extraídos e o link da fonte.
6. O conteúdo das três fontes não pode servir para treinar ou ajustar modelos. Extração por LLM via OpenRouter é inferência, não treino. Só se usam provedores cuja política não retenha a entrada para treino (por exemplo, o flag de *data collection* "deny" do OpenRouter).

**Pontos pra Voar: decidido (decisão 002, opção C, aceita por Aurimar).** Do Pontos pra Voar usamos só título, data e link: do feed RSS na coleta recorrente e do índice CDX e do RSS arquivado (C5) no histórico. O corpo dos artigos não é baixado, nem do site nem da Wayback (`id_`). Em paralelo, pedimos autorização por escrito à BoardingArea (`info@pontospravoar.com`). Se ela vier, uma decisão nova libera o corpo.

Isto não é parecer jurídico. A verificação precisa ser refeita se os termos mudarem: o coletor grava o hash do `robots.txt` em `source_health` e alerta quando ele muda.

## 2. Histórico de 24+ meses via Wayback CDX

### 2.1 Cobertura medida (CDX em 2026-10-13, janela 2023-10 a 2026-10)

Consulta feita: `matchType=prefix`, `filter=statuscode:200`, `filter=mimetype:text/html`, `filter=original:.*livelo.*smiles.*`. O resultado abaixo já está normalizado (sem `?utm_*`, `%0A`, `/embed/`, `/feed/`, `/amp/`).

| Fonte | Capturas | URLs únicas de artigo | Por ano (1ª captura) |
|---|---|---|---|
| passageirodeprimeira.com | 398 | 83 | 2023: 9, 2024: 46, 2025: 23, 2026: 5 |
| pontospravoar.com | 130 | 40 | 2023: 9, 2024: 20, 2025: 9, 2026: 2 |
| melhorescartoes.com.br | 160 | 23 | 2023: 9, 2024: 11, 2025: 3 |

O padrão `livelo.*smiles` perde slugs na ordem inversa ou sem a palavra "livelo", como `smiles-...-livelo` ou `transferencia-bonificada-smiles`. Por isso a consulta final usa os filtros da 2.2 e a classificação fica com o pré-filtro de texto, não com o slug. A cobertura de 2025 e 2026 é fraca, e o feed RSS (coleta recorrente) cobre daqui em diante.

### 2.2 URLs candidatas e filtros

Todas as consultas usam `from=` 24 meses antes de hoje no mínimo (proposta: `202301`, para ter folga), `to=` hoje, `output=json`.

| # | `url` | `matchType` | Filtros | Uso |
|---|---|---|---|---|
| C1 | `passageirodeprimeira.com/` | `prefix` | `statuscode:200`, `mimetype:text/html`, `original:.*(livelo.*smiles\|smiles.*livelo).*` | artigos |
| C2 | `pontospravoar.com/` | `prefix` | idem C1 | **só a listagem CDX** (URL, slug e timestamp). Sem download `id_` do corpo (decisão 002, opção C). Título e data vêm de C5. Serve só como segunda fonte de validação e não conta para o critério 4.1(3). |
| C3 | `www.melhorescartoes.com.br/` | `prefix` | idem C1 | artigos |
| C4 | `{dominio}/tag/livelo/` e `{dominio}/tag/smiles/` | `exact` | `statuscode:200`, `collapse=timestamp:8` (1/dia) | páginas de listagem: datas de publicação e títulos de artigos não capturados |
| C5 | `{dominio}/feed/` | `exact` | `statuscode:200`, `collapse=timestamp:8` | itens RSS históricos com `pubDate` |
| C6 | `www.livelo.com.br/` e `www.smiles.com.br/` (páginas de promoção/transferência) | `prefix` | `statuscode:200`, `original:.*(promo\|transfer\|bonus).*` | fonte oficial para validar datas (**verificar** robots e termos antes da T05; não verificado nesta spec) |

Medido em C4 (tag Livelo, 2023 a 2026, 1 captura por mês): Pontos pra Voar tem 13 meses com captura e Passageiro de Primeira tem 0. A C4 é complementar, não primária.

Pós-processamento obrigatório:
- Normalizar `original`: remover a query string, o fragmento e `%0A`, descartar `/embed/`, `/feed/` e `/amp/` de artigo, e trocar o esquema e o `www.` por um host canônico.
- Deduplicar por URL normalizada e ficar com a **captura mais antiga** (menor `timestamp`).
- Baixar o conteúdo da captura em modo bruto, `https://web.archive.org/web/{timestamp}id_/{original}`. O sufixo `id_` evita a barra de navegação da Wayback e preserva o HTML original.
- Para o ingest: `source = "{dominio}"`, `url = original normalizada`.

### 2.3 Uso de `src/preditor/wayback.py` (PR #1) e lacunas a fechar

O `CDXClient.list_captures(url, from_=..., to=..., matchType=..., filter=[...], collapse=..., fl=...)` cobre a listagem (linhas 139 a 164). O que falta para esta spec, a implementar na T05 (são achados de revisão do PR #1):

1. **Não baixa o snapshot.** Falta `fetch_snapshot(timestamp, original) -> bytes` com o modo `id_` e o mesmo limitador de taxa.
2. **Sem retry ou backoff.** `response.raise_for_status()` (linha 162) falha na primeira resposta 429/503. A CDX devolve 503 com frequência. Faltam 3 tentativas com backoff exponencial e a pausa do domínio.
3. **Sem paginação.** Não há `showResumeKey` nem `resumeKey`, e prefixos grandes truncam em silêncio. Falta paginar até acabar a `resumeKey`.
4. **Vários filtros.** `filter` precisa aceitar lista, o que o httpx serializa como parâmetros repetidos. Falta um teste que prove `filter=a&filter=b` na URL.
5. **Ritmo padrão.** `rate_limit=1.0` (1 req/s, linha 100) é agressivo para a Wayback. A proposta é 1 req a cada 2 s na CDX e 1 a cada 4 s no `id_`.
6. A API pública tem aliases demais (`list_snapshots`, `cdx`, `fetch_captures`, `query_cdx`, `Client`...). Recomendo reduzir a `CDXClient` e `list_captures` antes de crescer. Não bloqueia.

### 2.4 Auditoria temporal: o que é `first_seen_at` no histórico

- **Risco:** `raw_message.collected_at` tem `DEFAULT now()`. No backfill, ele marcaria a data do backfill, e com isso todo o histórico pareceria "visto hoje". Se alguém usar o timestamp da captura mais recente, ele vem de recapturas tardias (há capturas de 2025-07 com `utm_source=@beconews` para artigos de 2023). Isso também está errado.
- **Regra:** `first_seen_at` = **mínimo** entre (a) `article:published_time` ou `datePublished` do HTML e (b) o `timestamp` da captura mais antiga da URL. Os dois são instantes em que a informação já era pública. Se (a) ficar mais de 7 dias antes de (b), marcar `published_vs_capture_gap=true` na evidência para revisão manual, porque pode ser data de publicação reescrita.
- **Esquema:** falta a coluna `raw_message.observed_at TIMESTAMPTZ NOT NULL`, para o instante em que o conteúdo ficou público, separado de `collected_at`. Vai na migração 0002 da T05. O `offer.first_seen_at` = o menor `observed_at` entre as evidências.
- **Migração 0002 em linhas já existentes:** a coluna entra nullable. Ela é preenchida pelo `timestamp` da captura Wayback (parseado da URL `id_`) ou pelo `published_time` do HTML. As linhas que não puderem ser preenchidas são apagadas e reingeridas: o banco é local e só tem dado bruto. Nunca se usa `collected_at` nesse preenchimento. Só depois a coluna vira `SET NOT NULL`.
- Features e rótulos da T08 só usam `offer` com `first_seen_at <= t` no corte `t`. O walk-forward usa **purge maior ou igual ao maior horizonte (30 dias)**, contado a partir do início da janela de teste, conforme a decisão 003. Embargo de rótulo fica como melhoria futura.

## 3. Esquema JSON do extrator

### 3.1 Saída por item (JSON Schema 2020-12, estrito)

Uma mensagem pode gerar zero ou mais ofertas. A saída do extrator é `{"ofertas": [ ... ]}`.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://github.com/mzinhoww-svg/preditor-promos-milhas/schemas/oferta-v1.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["ofertas"],
  "properties": {
    "ofertas": {
      "type": "array",
      "maxItems": 10,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["origem", "destino", "tipo", "bonus_pct", "inicio", "fim", "segmentada", "segmento"],
        "properties": {
          "origem":     {"type": ["string", "null"], "enum": ["livelo", "esfera", "latam_pass", "smiles", "azul_fidelidade", null]},
          "destino":    {"type": ["string", "null"], "enum": ["livelo", "esfera", "latam_pass", "smiles", "azul_fidelidade", null]},
          "tipo":       {"type": "string", "enum": ["transfer_bonus", "purchase_discount", "boosted_accrual"]},
          "bonus_pct":  {"type": ["number", "null"], "minimum": 1, "maximum": 300},
          "inicio":     {"type": ["string", "null"], "pattern": "^20[2-3][0-9]-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"},
          "fim":        {"type": ["string", "null"], "pattern": "^20[2-3][0-9]-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$"},
          "segmentada": {"type": "boolean"},
          "segmento":   {"type": ["string", "null"], "maxLength": 60},
          "bumerangue_pct": {"type": ["number", "null"], "minimum": 1, "maximum": 300}
        }
      }
    }
  }
}
```

Semântica dos campos:
- `origem` e `destino` são slugs minúsculos dos 5 programas que o extrator da T07a reconhece. Ficam `null` quando o texto não permite identificar a direção (por exemplo, quando só um programa aparece). O PoC só usa ofertas com `origem=livelo` e `destino=smiles`; os outros pares e os `null` são descartados pelo validador de negócio, com log, e não pelo schema.
- `tipo` segue o glossário. Livelo → Smiles é quase sempre `transfer_bonus`.
- `bonus_pct` é o **bônus máximo anunciado** para o par, em número decimal, para aceitar casos como 37,5% (o banco é `NUMERIC(6,2)`). "Até 90%" vira 90, e "80% + 10% clube" vira 90 com `segmentada=true` se os 10% exigirem clube. É `null` só se o texto não trouxer %.
- `inicio` e `fim` são datas locais (America/Sao_Paulo) em ISO 8601. `fim=null` quando não foi anunciado. `inicio=null` quando o texto só diz "até DD/MM" (correção N2 da T07a). Nesse caso, a consolidação em `offer` usa `start_at = first_seen_at::date` e marca a evidência com `start_inferred=true`. O ano de uma data sem ano vem do ano mais próximo de `first_seen_at` em SP (T07a). Sem `first_seen_at`, a data fica `null`.
- `segmento` é o rótulo da segmentação (`clube`, `cartao`, ...) e corresponde a `offer.segment_label`. É `null` quando `segmentada=false`.
- `segmentada` é `true` quando a oferta é restrita a clube, cartão ou público.

Regras de negócio que o JSON Schema não expressa e que um validador Python aplica após o schema (descartar e logar o motivo):
1. Datas reais: `date.fromisoformat` aceita a data. O regex deixa passar `2025-02-31`.
2. `fim >= inicio` e `fim - inicio <= 90 dias`.
3. `inicio <= first_seen_at::date + 30 dias`. Um anúncio não fala de promoção a mais de 30 dias no futuro; se falar, vai para revisão.
4. `inicio >= first_seen_at::date - 7 dias`. Isso pega texto que menciona campanha passada como se fosse nova.
5. Para Livelo → Smiles com `transfer_bonus`, `bonus_pct` fica entre 10 e 150. Fora disso vai para revisão, sem descarte silencioso.

### 3.2 Divergências com o esquema do banco

- `segmento` foi adicionado ao schema v1 (3.1), correspondendo a `offer.segment_label`, que entra na chave única. Sem ele, duas ofertas segmentadas diferentes no mesmo dia colidiriam. Ver a decisão 004.
- "Bumerangue Livelo" (a Livelo devolve parte dos pontos transferidos) aparece em vários artigos (por exemplo, `bumerangue-livelo-orange-friday-smiles-nov23`). Não é bônus da Smiles, e o glossário não tem esse tipo. Tratamento: **decisão 004** (o bumerangue é ignorado no `bonus_pct`). O campo opcional `bumerangue_pct` entra no schema (3.1).

### 3.3 Regex: pré-filtro e checagem cruzada (camada regex da T07)

Use com `re.IGNORECASE`. O texto deve estar normalizado antes, com `unicodedata.normalize("NFKC")` e espaços colapsados.

```python
# Pré-filtro: o texto menciona o par? Só então chama o LLM.
PAR = r"\blivelo\b.{0,120}\bsmiles\b|\bsmiles\b.{0,120}\blivelo\b"

# Contexto de bônus de transferência.
BONUS_CTX = r"b[ôo]nus|bonificad[ao]|transfer[êe]ncia"

# Percentual de bônus; captura o número. "até 100%", "100% de bônus", "bônus de 80%".
BONUS_PCT = r"(?:at[ée]\s+)?(?<!\d)(\d{2,3})\s?%(?=\s*(?:de\s+)?(?:b[ôo]nus|bonifica|na\s+transfer))|b[ôo]nus\s+de\s+(?:at[ée]\s+)?(\d{2,3})\s?%"

# Datas: "até 15/03", "de 10/03 a 15/03/2025", "até 15 de março".
DATA_NUM = r"(?<!\d)([0-3]?\d)/([01]?\d)(?:/(20\d{2}|\d{2}))?(?!\d)"
DATA_EXT = r"(?<!\d)([0-3]?\d)\s+de\s+(janeiro|fevereiro|mar[çc]o|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)(?:\s+de\s+(20\d{2}))?"

# Segmentação.
# Sem "diamante|ouro|prata": no teste da T07a, "tabela de ouro e prata" virava falso positivo.
SEGMENTO = r"clube\s+(?:livelo|smiles)|exclusiv[oa]\s+para|somente\s+para\s+(?:clientes|assinantes|membros)|cart[ãa]o\s+\w+"
```

A checagem cruzada roda em todo item do LLM. Se `bonus_pct` não estiver entre os números capturados por `BONUS_PCT` no texto, o item vai para revisão (`needs_review=true`). Cada regex tem testes positivos e negativos na fixture (4.2).

## 4. Critérios de aceite

### 4.1 Coletor (T05)

O PR só é aprovado se tiver evidência de cada item no `TASKS.md`:

1. **Robots e ritmo:** um teste unitário mostra que uma URL bloqueada pelo `robots.txt` de fixture não é requisitada. Outro mostra que o limitador espaça as requisições conforme a seção 1, com relógio falso e sem `sleep` real, para fontes e para Wayback separadamente. O teste inclui `rate_limit`/`min_interval` passados por chamada, e o limitador continua compartilhado (bug B1 do PR #1).
2. **Backfill Wayback:** um comando `uv run python -m preditor.backfill --source {dominio} --from 202301` executa C1 e C3 com paginação `resumeKey`, retry, backoff e download `id_`, e executa C2 só como listagem. É idempotente: rodar duas vezes não cria linhas novas em `raw_message`, pela chave `UNIQUE (source, content_hash)`. O teste automatizado usa `httpx.MockTransport`. A execução real contra a Wayback é um teste de integração manual (`-m integration`), fora do CI, com o log anexado ao PR.
3. **Cobertura (determinística):** as respostas CDX de C1 e C3 ficam congeladas em `tests/fixtures/contract/cdx_*.json`, e a cobertura é medida sobre elas, não sobre a Wayback do dia. Meta: pelo menos **100 URLs únicas** de artigo Livelo → Smiles com corpo baixável (C1 + C3; a spec mediu 83 + 23 = 106, margem de 6) e **pelo menos 24 meses** distintos com no mínimo 1 artigo. O objetivo do projeto é cerca de 36 meses. 2025 e 2026 estão fracos (5 e 2 artigos no filtro estreito), então o relatório lista os meses vazios e a cobertura em 36 meses, sem preencher nada à mão. O C2 (Pontos pra Voar, só título) é contado à parte.
4. **Temporal:** a migração 0002 cria `raw_message.observed_at` e preenche as linhas existentes conforme a §2.4, antes do `SET NOT NULL`. Um teste prova que `observed_at` = o mínimo entre `published_time` e a captura mais antiga, e que nunca usa `now()` no backfill. Uma consulta de auditoria `SELECT count(*) FROM raw_message WHERE observed_at > collected_at` retorna 0.
5. **Feed recorrente:** o coletor RSS lê `/feed/` das fontes aprovadas e insere só os itens novos, deduplicados por `content_hash`. Ele grava `source_health` (`items_new`, `extraction_rate`) e o hash do `robots.txt`, e marca `source_health.alert=true` se ficar 7 dias sem item novo ou se o hash do robots mudar. O teste usa relógio falso para os 7 dias.
6. **Segurança:** não há segredo no código e o gitleaks passa no CI. Um teste falha se algum arquivo em `tests/fixtures/` contiver `<html` ou `<body`, ou se uma fixture de texto passar de 4 KB. Isso torna verificável a regra de não commitar HTML integral.
7. **Qualidade:** `ruff` limpo, `pytest` verde local e no CI, e nenhuma chamada de rede real nos testes (usar `httpx.MockTransport`).

### 4.2 Fixture de contrato

Ficam em `tests/fixtures/contract/` e são versionadas. Elas travam o formato das respostas externas e a saída do extrator.

1. **CDX:** 3 respostas JSON reais da CDX, com só as colunas `urlkey, timestamp, original, mimetype, statuscode, digest, length`, uma por fonte. Pelo menos uma tem `resumeKey` e outra tem URL com `?utm_` e `/embed/`. Teste: `parse_cdx_response` e a normalização chegam ao conjunto esperado de URLs únicas e à captura mais antiga.
2. **RSS:** 3 feeds sintéticos que copiam a estrutura real (`<item><title><link><pubDate><guid>`), com textos escritos por nós, sem corpo de artigo de terceiros.
3. **Mensagens para o extrator:** pelo menos 20 casos sintéticos, curtos e factuais, cada um com `entrada.txt` e `esperado.json` válido contra o schema 3.1. Devem cobrir:
   - bônus simples e "até X%" com clube (segmentada);
   - prorrogação (mesmo par, `fim` maior);
   - renovação;
   - relâmpago (até 48 h);
   - sem % (`bonus_pct=null`);
   - sem data de fim;
   - campanha passada citada (deve gerar 0 ofertas, pela regra 4 da 3.1);
   - virada de ano sem ano no texto ("de 30/12 a 05/01" visto em 28/12 e em 02/01) e `inicio=null` só com "até DD/MM";
   - outro par (Livelo → LATAM Pass: o extrator devolve a oferta e o validador do PoC a descarta, então ficam 0 ofertas Livelo → Smiles);
   - bumerangue (`bonus_pct` sem a soma do bumerangue, e `bumerangue_pct` preenchido, conforme a decisão 004);
   - data inválida (`31/02`; deve ser descartada).
4. **Teste de contrato:**
   - todo `esperado.json` valida no schema;
   - o regex e o validador de negócio passam em 100% dos casos;
   - o extrator LLM, rodado de forma explícita e fora do CI para não gastar orçamento, é medido contra a mesma fixture e contra o conjunto de ouro, com as metas por campo da **decisão 004**.
   - Uma mudança no schema exige versão nova (`oferta-v2.json`) e atualização da fixture no mesmo PR.

## 5. Fora de escopo

Telegram (decisão 001), outros pares, compra de pontos e acúmulo turbinado de outras origens, e deploy na VPS.
