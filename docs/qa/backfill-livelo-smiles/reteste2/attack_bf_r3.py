"""QA PR #36 reteste 2 (8f4c51b). Banco proprio qa_bf3."""
import argparse, datetime as dt, json, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
from preditor import backfill as B, collector as C, model as M
from preditor.jobs import daily_predict as J
E = create_engine(os.environ["DATABASE_URL"]); R = {}
UTC = dt.UTC
SL = []; time.sleep = lambda s: SL.append(s)
def wipe():
    with E.begin() as c:
        for t in ("offer_evidence", "offer", "raw_message", "prediction", "model_run"):
            try: c.execute(text(f"DELETE FROM {t}"))
            except Exception as e: pass
def raw(url, content, gap, source="s.test", obs="2026-01-01"):
    with E.begin() as c:
        return c.execute(text("INSERT INTO raw_message(source,url,content,content_hash,observed_at,published_vs_capture_gap) VALUES(:s,:u,:c,:h,:o,:g) RETURNING id"),
                         dict(s=source, u=url, c=content, h=url, o=obs, g=gap)).scalar()
def offer(o, d, start, bonus=80):
    with E.begin() as c:
        return c.execute(text("INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) VALUES(:o,:d,'transfer_bonus',:s,:b,false,'',:f) RETURNING id"),
                         dict(o=o, d=d, s=start, b=bonus, f=dt.datetime.combine(start, dt.time.min, tzinfo=UTC))).scalar()
def ev(oid, rid):
    with E.begin() as c: c.execute(text("INSERT INTO offer_evidence(offer_id,raw_message_id,source,seen_start_at) VALUES(:o,:r,'s.test',now()::date)"), dict(o=oid, r=rid))
# ---- A: filtro so-gap
wipe()
rg1, rg2, rok = raw("u1", "x1", True), raw("u2", "x2", True), raw("u3", "x3", False)
ids = {}
for i in range(4):  # par livelo->smiles: 4 ofertas nao-gap
    o = offer("livelo", "smiles", dt.date(2026, 1, 1) + dt.timedelta(days=30*i)); ev(o, rok)
ids["gap_only"] = offer("esfera", "latam", dt.date(2026, 2, 1)); ev(ids["gap_only"], rg1); ev(ids["gap_only"], rg2)
ids["misto"] = offer("itau", "azul", dt.date(2026, 2, 2)); ev(ids["misto"], rg1); ev(ids["misto"], rok)
ids["sem_evidencia"] = offer("c6", "tudo", dt.date(2026, 2, 3))
got = {(o["origin"], o["destination"]) for o in J.fetch_offers(E)}
R["A1_job_fetch_offers"] = {"inclui_gap_only": ("esfera", "latam") in got, "inclui_misto": ("itau", "azul") in got, "inclui_sem_evidencia": ("c6", "tudo") in got}
J.run_daily(as_of="2026-06-01", engine=E)
with E.connect() as c: pares = {(r[0], r[1]) for r in c.execute(text("SELECT origin,destination FROM prediction"))}
R["A2_job_preve_gap_only"] = ("esfera", "latam") in pares
# ---- A3: caminho de avaliacao a partir do banco: carregar ofertas "como qualquer consumidor" e avaliar
with E.connect() as c:
    rows = c.execute(text("SELECT origin,destination,event_type,start_at,first_seen_at FROM offer")).mappings().all()
recs = [dict(r) for r in rows]
R["A3_loader_ingenuo_inclui_gap_only"] = any(r["origin"] == "esfera" for r in recs)
R["A3_exclude_gap_only_remove_sem_campo"] = len(M.exclude_gap_only(recs)) == len(recs)   # sem campo gap_only nada e removido
R["A3_helper_que_carrega_com_filtro_existe"] = [n for n in dir(M) if "load" in n.lower() and "offer" in n.lower()] + [n for n in dir(J) if "gap" in n.lower()]
# ---- B: start_inferred (spec 3.1)
wipe(); fs = dt.datetime(2026, 5, 10, tzinfo=UTC)
def proc(txt, first_seen=fs):
    rid = raw("p-" + str(abs(hash(txt))), txt, False)
    C.process_raw_message(E, {"content": txt, "id": rid, "source": "s.test"}, first_seen_at=first_seen)
    with E.connect() as c:
        return [tuple(map(str, r)) for r in c.execute(text("SELECT o.origin,o.destination,o.start_at,o.end_at,o.bonus_pct,e.start_inferred FROM offer o JOIN offer_evidence e ON e.offer_id=o.id WHERE e.raw_message_id=:r"), {"r": rid})]
R["B1_so_fim_ate_20/05"] = proc("A Smiles oferece até 80% de bônus nas transferências da Livelo, válida até 20/05.")
R["B2_com_inicio_e_fim"] = proc("A Smiles oferece até 90% de bônus nas transferências da Livelo de 12/05 a 18/05.")
R["B3_sem_datas"] = proc("A Smiles oferece até 70% de bônus nas transferências da Livelo.")
R["B4_fim_no_passado"] = proc("A Smiles oferece até 60% de bônus nas transferências da Livelo, válida até 01/05.")
R["B5_fim_>90d"] = proc("A Smiles oferece até 50% de bônus nas transferências da Livelo, válida até 30/12.")
# ---- C: feed arquivado via CDX
wipe()
tmp = tempfile.mkdtemp(); os.chdir(tmp); B.STATE_PATH = Path(tmp) / "state.json"
FEED = "https://fonte.test/feed/"
XML = lambda items: "<?xml version='1.0'?><rss><channel>" + "".join(f"<item><title>{t}</title><link>{l}</link><pubDate>{p}</pubDate><description>CORPO LONGO PROIBIDO {t}</description></item>" for t, l, p in items) + "</channel></rss>"
caps = [{"timestamp": f"2025{m:02d}15120000", "original": FEED} for m in (1, 2, 3)]
FETCH = []
def setup(robots=("ok", "User-agent: *\nDisallow:\n")):
    SL.clear(); FETCH.clear()
    B.fetch_robots_strict = lambda s: robots
    B.list_feed_captures = lambda f, d, r, ps=500: list(caps)
    def fs_(ts, url):
        FETCH.append((ts, len(SL)))
        m = int(ts[4:6])
        return XML([(f"Smiles oferece até 80% de bônus da Livelo {m}", f"https://fonte.test/p{m}/", "Mon, 06 Jan 2025 10:00:00 +0000"), ("Titulo repetido", "https://fonte.test/rep/", "Mon, 06 Jan 2025 10:00:00 +0000")])
    B.fetch_snapshot_backoff = fs_
setup(); out = B.collect_archived_feed(E, "fonte.test", FEED, dt.date(2025, 1, 1), rate_limit=10.0, step_days=5)
R["C1_run"] = out
with E.connect() as c:
    R["C1_raw"] = {"n": c.execute(text("SELECT count(*) FROM raw_message")).scalar(), "max_len": c.execute(text("SELECT max(length(content)) FROM raw_message")).scalar(),
                   "corpo_proibido": c.execute(text("SELECT count(*) FROM raw_message WHERE content ILIKE '%CORPO LONGO%'")).scalar(),
                   "gap": c.execute(text("SELECT count(*) FROM raw_message WHERE published_vs_capture_gap")).scalar()}
R["C1_sleep10_antes_de_cada_snapshot"] = all(i >= 1 and SL[i-1] == 10.0 for _, i in FETCH)
n = len(FETCH); out2 = B.collect_archived_feed(E, "fonte.test", FEED, dt.date(2025, 1, 1)); R["C2_reexec_novos_fetches"] = len(FETCH) - n
with E.connect() as c: R["C2_raw_apos_reexec"] = c.execute(text("SELECT count(*) FROM raw_message")).scalar()
os.remove(B.STATE_PATH); n = len(FETCH); B.collect_archived_feed(E, "fonte.test", FEED, dt.date(2025, 1, 1))
with E.connect() as c: R["C3_sem_state_raw"] = c.execute(text("SELECT count(*) FROM raw_message")).scalar()
setup(robots=("ok", "User-agent: *\nDisallow: /feed/\n")); R["C4_robots_disallow_feed"] = (B.collect_archived_feed(E, "fonte.test", FEED, dt.date(2025, 1, 1)), len(FETCH))
setup(robots=("robots_unavailable", None)); R["C5_robots_indisponivel"] = (B.collect_archived_feed(E, "fonte.test", FEED, dt.date(2025, 1, 1)), len(FETCH))
print(json.dumps(R, indent=1, default=str, ensure_ascii=False))
