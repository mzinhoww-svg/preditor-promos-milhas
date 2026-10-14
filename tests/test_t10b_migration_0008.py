"""0008: runs antigos do job (is_champion=TRUE, role='experiment') viram daily e nao campeoes."""
import os
import subprocess
import sys

import pytest
from sqlalchemy import text

URL_DB = os.environ.get("DATABASE_URL")
pytestmark = pytest.mark.skipif(not URL_DB, reason="DATABASE_URL ausente")


def _alembic(*a):
    subprocess.run([sys.executable, "-m", "alembic", *a], check=True, env=dict(os.environ))


def test_backfill_de_role_preserva_campeao_t08b():
    from preditor.api.db import get_engine

    _alembic("upgrade", "head")
    _alembic("downgrade", "0007")  # estado anterior à 0008, com colunas/índice da 0007
    e = get_engine()
    ins = ("INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, "
           "metrics, code_hash, is_champion) VALUES (:mv, now(), :dv, '1', CAST(:hp AS jsonb), '{}'::jsonb, :ch, TRUE) "
           "RETURNING id")
    with e.begin() as c:
        c.execute(text("DELETE FROM alert"))
        c.execute(text("DELETE FROM prediction"))
        c.execute(text("DELETE FROM model_run"))
        t08b = c.execute(text(ins), {"mv": "C1", "dv": "ds", "hp": '{"name":"C1"}', "ch": "git-abc"}).scalar()
        job_old = c.execute(text(ins), {"mv": "B1", "dv": "daily", "hp": '{"name":"B1"}', "ch": "daily-job"}).scalar()
        job_new = c.execute(text(ins), {"mv": "B0", "dv": "h" * 64, "hp": '{"name":"B0","methods":{"b0":1}}',
                                         "ch": "c" * 64}).scalar()
        dup = c.execute(text(ins), {"mv": "B0", "dv": "h" * 64, "hp": '{"name":"B0","methods":{"b0":1}}',
                                     "ch": "c" * 64}).scalar()
    _alembic("upgrade", "head")
    with e.connect() as c:
        rows = {r[0]: (r[1], r[2]) for r in c.execute(text("SELECT id, role, is_champion FROM model_run"))}
    assert rows[t08b] == ("experiment", True)  # campeao do T08b preservado
    assert rows[job_old] == ("daily", False)
    assert rows[job_new] == ("daily", False)
    assert rows[dup] == ("daily_legacy", False)
    with e.begin() as c:
        c.execute(text("DELETE FROM model_run"))
