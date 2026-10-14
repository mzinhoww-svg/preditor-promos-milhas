import json, os, sys, datetime as dt, collections
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor import backfill as B
from preditor.records import load_offer_records
from preditor import model as M
from preditor.extract import extract
E = create_engine(os.environ["DATABASE_URL"]); P2 = create_engine(os.environ["P2_URL"])
R = {}
def snap(e):
    with e.connect() as c:
        return sorted(tuple(map(str, r)) for r in c.execute(text("SELECT origin,destination,event_type,start_at,end_at,bonus_pct,segmented,segment_label,n_sources,validated FROM offer")))
r1 = B.reprocess(E); s1 = snap(E); r2 = B.reprocess(E); s2 = snap(E); sp = snap(P2)
R["reprocess"] = {"1": r1, "idempotente": s1 == s2, "meu": len(s1), "autor": len(sp), "so_autor": len(set(sp) - set(s1)), "so_meu": len(set(s1) - set(sp))}
c = collections.Counter(f"{r[0]}->{r[1]}" for r in s1); R["por_par"] = dict(c)
R["sem_bonus"] = sum(1 for r in s1 if r[5] == "None"); R["bonus_110_58"] = sum(1 for r in s1 if r[5] in ("110.00", "58.00"))
with E.connect() as c2:
    R["raw_pub"] = c2.execute(text("SELECT count(*), count(published_at) FROM raw_message WHERE source LIKE 'pontospravoar%'")).first()._asdict() if False else tuple(c2.execute(text("SELECT count(*), count(published_at) FROM raw_message WHERE source LIKE 'pontospravoar%'")).first())
# loader
recs = load_offer_records(E)
R["loader_campos"] = sorted(recs[0].keys())
R["loader_sem_estado_final"] = not any(k in recs[0] for k in ("validated", "n_sources", "weight"))
with E.connect() as c3:
    mixed = c3.execute(text("""SELECT o.id, o.first_seen_at, (SELECT min(rm.observed_at) FROM offer_evidence oe JOIN raw_message rm ON rm.id=oe.raw_message_id WHERE oe.offer_id=o.id AND NOT rm.published_vs_capture_gap) nogap,
        (SELECT min(rm.observed_at) FROM offer_evidence oe JOIN raw_message rm ON rm.id=oe.raw_message_id WHERE oe.offer_id=o.id) anyg
        FROM offer o WHERE EXISTS (SELECT 1 FROM offer_evidence oe JOIN raw_message rm ON rm.id=oe.raw_message_id WHERE oe.offer_id=o.id AND rm.published_vs_capture_gap)
          AND EXISTS (SELECT 1 FROM offer_evidence oe JOIN raw_message rm ON rm.id=oe.raw_message_id WHERE oe.offer_id=o.id AND NOT rm.published_vs_capture_gap)""")).all()
R["mistas"] = len(mixed)
byid = {}
with E.connect() as c4:
    ids = [r[0] for r in c4.execute(text("SELECT id FROM offer ORDER BY start_at, id"))]
recmap = dict(zip(ids, recs))
viol = [m[0] for m in mixed if recmap[m[0]]["first_seen_at"] != m[2]]
R["mistas_first_seen_igual_min_sem_gap"] = (len(mixed) - len(viol), len(mixed))
R["mistas_first_seen_mudou_vs_tabela"] = sum(1 for m in mixed if m[1] != m[2])
# extrator
fs = dt.datetime(2026, 5, 10, 12, tzinfo=dt.UTC)
def pr(t):
    return [(o.origem, o.destino, o.bonus_pct, o.inicio, o.fim) for o in extract(t, first_seen_at=fs).ofertas]
cases = {
 "inclusive_livelo_esfera_para_smiles": "Último dia para ganhar até 90% de bônus nas transferências de pontos de todos os parceiros financeiros – inclusive Livelo e Esfera – para a Smiles. A oferta é válida até hoje (10).",
 "exceto_esfera": "Segue valendo a oferta da Smiles de 70% de bônus nas transferências de pontos, válido para todos os parceiros financeiros, exceto Esfera. A promoção é válida somente até hoje (10).",
 "menos_de_24h_sem_virgula": "Em menos de um dia a Smiles anunciou até 90% de bônus nas transferências de pontos da Livelo. A oferta é válida até hoje (10).",
 "menos_de_com_virgula": "Smiles oferece até 90% de bônus nas transferências de pontos da Livelo, menos de 24 horas para aproveitar. Válida até hoje (10).",
 "exceto_no_meio": "A Smiles oferece até 80% de bônus nas transferências da Livelo, exceto cartões Elo, para quem for do Clube. Válida até hoje (10).",
 "salvo_final": "A Smiles oferece até 100% de bônus nas transferências da Livelo, salvo assinantes inativos. Válida até hoje (10).",
 "milhas_bonus": "A LATAM Pass oferece até 35% de milhas bônus na transferência de pontos Livelo. Válida até hoje (10).",
 "pontos_bonus": "A Smiles oferece 40% de pontos bônus na transferência de pontos da Livelo. Válida até hoje (10).",
 "controle_simples": "A Smiles está oferecendo até 100% de bônus nas transferências de pontos da Livelo. A oferta é válida somente até amanhã (11).",
}
R["extrator"] = {k: pr(v) for k, v in cases.items()}
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
