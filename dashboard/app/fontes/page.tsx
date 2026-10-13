import type { Metadata } from "next";
import { Badge, STATUS_TONE } from "@/components/badge";
import { PageHeader, Section, SummaryPanel } from "@/components/page-header";
import { getSourceHealth, type SourceStatus } from "@/lib/api";
import { SOURCE_KIND_LABEL, SOURCE_STATUS_LABEL, dateTime, int, pct, relativeFrom } from "@/lib/format";

export const metadata: Metadata = { title: "Fontes" };
export const dynamic = "force-dynamic";

const ORDER: SourceStatus[] = ["blocked", "error", "degraded", "stale", "ok"];

export default async function SourcesPage() {
  const data = await getSourceHealth();
  const now = new Date(data.generated_at);
  const sources = [...data.sources].sort((a, b) => ORDER.indexOf(a.status) - ORDER.indexOf(b.status));
  const count = (s: SourceStatus) => sources.filter((x) => x.status === s).length;
  const new24 = sources.reduce((acc, s) => acc + s.items_new_24h, 0);
  const new7 = sources.reduce((acc, s) => acc + s.items_new_7d, 0);

  return (
    <>
      <PageHeader
        title="Saúde das fontes"
        description="Cada fonte coletada, com a última coleta bem-sucedida, itens novos, taxa de extração e mudanças no robots.txt. Uma fonte parada há 7 dias ou com robots alterado vira alerta."
      />

      <SummaryPanel
        items={[
          { label: "Fontes operando", value: `${count("ok")} de ${sources.length}` },
          { label: "Com problema", value: count("blocked") + count("error") + count("degraded"), hint: "bloqueadas, com erro ou degradadas" },
          { label: "Itens novos · 24 h", value: int(new24), hint: `${int(new7)} nos últimos 7 dias` },
          { label: "Verificado", value: dateTime(data.generated_at) },
        ]}
      />

      <Section title="Fontes" description="Ordenadas da mais crítica para a mais saudável.">
        <p className="mb-2 text-xs text-ink-3 lg:hidden">Deslize a tabela para o lado para ver todas as colunas.</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[52rem] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs font-medium text-ink-3">
                <th className="py-2 pr-4 font-medium">Fonte</th>
                <th className="py-2 pr-4 font-medium">Status</th>
                <th className="py-2 pr-4 font-medium">Última coleta</th>
                <th className="py-2 pr-4 font-medium">Último item</th>
                <th className="tnum py-2 pr-4 text-right font-medium">Novos 24 h</th>
                <th className="tnum py-2 pr-4 text-right font-medium">Novos 7 d</th>
                <th className="tnum py-2 pr-4 text-right font-medium">Extração 7 d</th>
                <th className="tnum py-2 pr-4 text-right font-medium">Erro 24 h</th>
                <th className="py-2 font-medium">robots.txt</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {sources.map((s) => (
                <tr key={s.source} className="align-top">
                  <td className="py-3 pr-4">
                    <div className="font-medium text-ink">{s.source}</div>
                    <div className="mt-0.5 text-xs text-ink-3">{SOURCE_KIND_LABEL[s.kind]}</div>
                    {s.message ? <p className="mt-1.5 max-w-[22rem] text-xs leading-5 text-ink-2">{s.message}</p> : null}
                  </td>
                  <td className="py-3 pr-4">
                    <Badge tone={STATUS_TONE[s.status]}>{SOURCE_STATUS_LABEL[s.status]}</Badge>
                  </td>
                  <td className="py-3 pr-4 text-ink-2">
                    {relativeFrom(s.last_success_at, now)}
                    <div className="text-xs text-ink-3">{dateTime(s.last_success_at)}</div>
                  </td>
                  <td className="py-3 pr-4 text-ink-2">
                    {relativeFrom(s.last_item_at, now)}
                    <div className="text-xs text-ink-3">{dateTime(s.last_item_at)}</div>
                  </td>
                  <td className="tnum py-3 pr-4 text-right text-ink">{int(s.items_new_24h)}</td>
                  <td className="tnum py-3 pr-4 text-right text-ink-2">{int(s.items_new_7d)}</td>
                  <td className={`tnum py-3 pr-4 text-right ${s.extraction_rate_7d < 0.8 && s.items_new_7d > 0 ? "font-medium text-warn" : "text-ink-2"}`}>
                    {s.items_new_7d > 0 ? pct(s.extraction_rate_7d) : "—"}
                  </td>
                  <td className={`tnum py-3 pr-4 text-right ${s.error_rate_24h > 0.2 ? "font-medium text-crit" : "text-ink-2"}`}>
                    {pct(s.error_rate_24h)}
                  </td>
                  <td className="py-3">
                    {s.robots_changed ? <Badge tone="crit">mudou</Badge> : <span className="text-ink-3">sem mudança</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-3 max-w-prose text-xs leading-5 text-ink-3">
          Extração = itens com campanha reconhecida sobre itens coletados nos últimos 7 dias. Destaque em laranja
          abaixo de 80%; erro em vermelho acima de 20% nas últimas 24 h. Fontes Wayback só servem ao backfill histórico.
        </p>
      </Section>
    </>
  );
}
