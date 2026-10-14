"""T10b (2,3,4): model_run por execucao, alertas por limiar, explicacao sem vazamento."""
import datetime as _dt
import os
import subprocess
import sys
from datetime import datetime

import pytest
from sqlalchemy import text

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")

UTC = _dt.UTC
D = _dt.date
H = {"X-API-Key": "test-key"}


@pytest.fixture(scope="module")
def engine():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=dict(os.environ))
    from preditor.api.db import get_engine

    return get_engine()


def _wipe(engine):
    with engine.begin() as c:
        c.execute(text("DELETE FROM alert"))
        c.execute(text("DELETE FROM prediction"))
        c.execute(text("DELETE FROM offer"))
        c.execute(text("DELETE FROM model_run"))


@pytest.fixture(autouse=True)
def clean(engine):
    _wipe(engine)
    yield
    _wipe(engine)


def _offer(engine, o, d, start, first_seen=None, bonus=80):
    fs = first_seen or datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    with engine.begin() as c:
        c.execute(
            text(
                "INSERT INTO offer(origin,destination,event_type,start_at,bonus_pct,segmented,segment_label,first_seen_at) "
                "VALUES(:o,:d,'transfer_bonus',:s,:b,false,'',:f)"
            ),
            {"o": o, "d": d, "s": start, "b": bonus, "f": fs},
        )


def _seed(engine, n=5, step=30, start=None):
    start = start or D(2026, 1, 1)
    for i in range(n):
        _offer(engine, "livelo", "smiles", start + _dt.timedelta(days=step * i))


# ---- (2) model_run --------------------------------------------------------
def test_model_run_gravado_a_cada_execucao_com_hash_e_metricas(engine):
    from preditor.jobs.daily_predict import run_daily

    _seed(engine)
    run_daily(as_of="2026-06-01", engine=engine)
    with engine.connect() as c:
        rows = c.execute(text("SELECT model_version, dataset_version, metrics, hyperparams, code_hash FROM model_run")).fetchall()
    assert len(rows) == 1
    mv, dv, metrics, hp, ch = rows[0]
    assert mv in {"B0", "B1", "C1"}
    assert len(dv) == 64 and ch
    assert metrics["n_offers"] == 5 and metrics["n_pairs"] == 1 and metrics["n_predictions"] == 3
    assert hp["name"] == mv


def test_model_run_hash_muda_com_os_dados_e_reexecucao_e_idempotente(engine):
    from preditor.jobs.daily_predict import run_daily

    _seed(engine)
    run_daily(as_of="2026-06-01", engine=engine)
    run_daily(as_of="2026-06-01", engine=engine)  # mesma entrada: reutiliza
    with engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM model_run")).scalar() == 1
        assert c.execute(text("SELECT count(*) FROM prediction")).scalar() == 3
    _offer(engine, "livelo", "smiles", D(2026, 5, 20))  # dado novo conhecido em as_of
    run_daily(as_of="2026-06-02", engine=engine)
    with engine.connect() as c:
        hashes = {r[0] for r in c.execute(text("SELECT dataset_version FROM model_run"))}
    assert len(hashes) == 2


def test_hash_dos_dados_nao_inclui_ofertas_futuras(engine):
    from preditor.jobs.daily_predict import run_daily

    _seed(engine)
    run_daily(as_of="2026-06-01", engine=engine)
    with engine.connect() as c:
        h1 = c.execute(text("SELECT dataset_version FROM model_run")).scalar()
    _offer(engine, "livelo", "smiles", D(2026, 9, 1))  # futuro em relacao a as_of
    _wipe_pred_only(engine)
    run_daily(as_of="2026-06-01", engine=engine)
    with engine.connect() as c:
        hs = {r[0] for r in c.execute(text("SELECT dataset_version FROM model_run"))}
    assert hs == {h1}


def _wipe_pred_only(engine):
    with engine.begin() as c:
        c.execute(text("DELETE FROM prediction"))


# ---- (3) alertas ----------------------------------------------------------
def _insert_pred(engine, made_at, p, mr):
    with engine.begin() as c:
        for h in (7, 15, 30):
            c.execute(text(
                "INSERT INTO prediction (made_at, model_run_id, origin, destination, event_type, horizon_days, probability) "
                "VALUES (:m, :mr, 'livelo','smiles','transfer_bonus', :h, :p)"
            ), {"m": made_at, "mr": mr, "h": h, "p": p})


def _mr(engine):
    with engine.begin() as c:
        return c.execute(text(
            "INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, metrics, code_hash, is_champion) "
            "VALUES ('B0', now(), 'd','1','{}'::jsonb,'{}'::jsonb,'h',TRUE) RETURNING id"
        )).scalar()


def test_alerta_quando_probabilidade_cruza_limiar(engine):
    from preditor.alerts import register_alerts

    mr = _mr(engine)
    _insert_pred(engine, datetime(2026, 6, 1, tzinfo=UTC), 0.20, mr)
    _insert_pred(engine, datetime(2026, 6, 2, tzinfo=UTC), 0.70, mr)
    n = register_alerts(engine, made_at=datetime(2026, 6, 2, tzinfo=UTC), threshold=0.5)
    assert n == 3
    with engine.connect() as c:
        r = c.execute(text("SELECT probability, previous_probability, threshold, horizon_days FROM alert ORDER BY horizon_days")).fetchall()
    assert [float(x[0]) for x in r] == [0.7, 0.7, 0.7]
    assert [float(x[1]) for x in r] == [0.2, 0.2, 0.2]
    assert float(r[0][2]) == 0.5


def test_sem_alerta_se_ja_estava_acima_ou_abaixo(engine):
    from preditor.alerts import register_alerts

    mr = _mr(engine)
    _insert_pred(engine, datetime(2026, 6, 1, tzinfo=UTC), 0.60, mr)
    _insert_pred(engine, datetime(2026, 6, 2, tzinfo=UTC), 0.80, mr)  # ja acima: nao cruza
    assert register_alerts(engine, made_at=datetime(2026, 6, 2, tzinfo=UTC), threshold=0.5) == 0
    _insert_pred(engine, datetime(2026, 6, 3, tzinfo=UTC), 0.10, mr)  # abaixo: nao alerta
    assert register_alerts(engine, made_at=datetime(2026, 6, 3, tzinfo=UTC), threshold=0.5) == 0


def test_alerta_idempotente(engine):
    from preditor.alerts import register_alerts

    mr = _mr(engine)
    _insert_pred(engine, datetime(2026, 6, 1, tzinfo=UTC), 0.20, mr)
    _insert_pred(engine, datetime(2026, 6, 2, tzinfo=UTC), 0.70, mr)
    t = datetime(2026, 6, 2, tzinfo=UTC)
    assert register_alerts(engine, made_at=t, threshold=0.5) == 3
    assert register_alerts(engine, made_at=t, threshold=0.5) == 0


def test_limiar_configuravel_por_env(engine, monkeypatch):
    from preditor.alerts import alert_threshold

    monkeypatch.setenv("PREDITOR_ALERT_THRESHOLD", "0.8")
    assert alert_threshold() == 0.8
    monkeypatch.delenv("PREDITOR_ALERT_THRESHOLD")
    assert 0 < alert_threshold() < 1


def test_endpoint_alerts(engine):
    from fastapi.testclient import TestClient

    from preditor.alerts import register_alerts
    from preditor.api import create_app

    os.environ["PREDITOR_API_KEY"] = "test-key"
    mr = _mr(engine)
    _insert_pred(engine, datetime(2026, 6, 1, tzinfo=UTC), 0.20, mr)
    _insert_pred(engine, datetime(2026, 6, 2, tzinfo=UTC), 0.70, mr)
    register_alerts(engine, made_at=datetime(2026, 6, 2, tzinfo=UTC), threshold=0.5)
    with TestClient(create_app()) as cl:
        assert cl.get("/v1/alerts").status_code == 401
        r = cl.get("/v1/alerts", headers=H)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 3
    assert items[0]["pair"] == {"origin": "livelo", "destination": "smiles"}
    assert items[0]["probability"] == 0.7 and items[0]["threshold"] == 0.5


def test_job_diario_registra_alerta_na_virada(engine, monkeypatch):
    from preditor.jobs.daily_predict import run_daily

    monkeypatch.setenv("PREDITOR_ALERT_THRESHOLD", "0.001")
    # sem historico antes de as_of => nao havia predicao anterior: primeira predicao acima do limiar alerta
    _seed(engine, n=5, step=7, start=D(2026, 4, 1))
    run_daily(as_of="2026-05-10", engine=engine)
    with engine.connect() as c:
        n = c.execute(text("SELECT count(*) FROM alert")).scalar()
    assert n >= 1


# ---- (4) explicacao -------------------------------------------------------
def test_explicacao_por_item_usa_so_o_conhecido_em_as_of(engine):
    from fastapi.testclient import TestClient

    from preditor.api import create_app
    from preditor.jobs.daily_predict import run_daily

    os.environ["PREDITOR_API_KEY"] = "test-key"
    _seed(engine, n=4, step=30, start=D(2026, 1, 1))  # 01/01,31/01,02/03,01/04
    _offer(engine, "livelo", "smiles", D(2026, 9, 1))  # futuro: nao pode aparecer
    run_daily(as_of="2026-06-01", engine=engine)
    with TestClient(create_app()) as cl:
        r = cl.get("/v1/predictions/livelo/smiles/explanation?type=transfer_bonus", headers=H)
        miss = cl.get("/v1/predictions/nada/nada/explanation?type=transfer_bonus", headers=H)
    assert miss.status_code == 404
    assert r.status_code == 200
    ex = r.json()
    assert ex["as_of"] == "2026-06-01"
    f = ex["factors"]
    assert f["n_campaigns"] == 4
    assert f["last_campaign_start"] == "2026-04-01"
    assert f["days_since_last"] == 61
    assert f["method"] in {"b0", "b1"}
    assert set(ex["windows"]) == {"7", "15", "30"}
    assert "2026-09-01" not in str(ex)
