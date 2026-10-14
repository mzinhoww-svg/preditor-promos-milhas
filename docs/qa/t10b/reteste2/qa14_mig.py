import json, os, sys
sys.path.insert(0, "src")
from sqlalchemy import create_engine, text
E = create_engine(os.environ["DATABASE_URL"])
def run(sql, **p):
    with E.begin() as c: return c.execute(text(sql), p)
INS = "INSERT INTO model_run (model_version, trained_at, dataset_version, feature_version, hyperparams, metrics, code_hash, is_champion, role) VALUES (:mv, now(), :dv, '1', CAST(:hp AS jsonb), '{}'::jsonb, :ch, :ch2, :role) RETURNING id"
ids = {}
def add(k, mv, dv, hp, ch, champ, role="experiment"):
    with E.begin() as c: ids[k] = c.execute(text(INS), dict(mv=mv, dv=dv, hp=json.dumps(hp), ch=ch, ch2=champ, role=role)).scalar()
add("job_a", "B0", "ds1", {"name": "B0", "methods": {"b0": 3}}, "h1", True)           # run antigo do job (ultimo marcado champion)
add("job_a_dup", "B0", "ds1", {"name": "B0", "methods": {"b0": 3}}, "h1", False)      # duplicata da mesma tripla
add("job_b", "B1", "ds2", {"name": "B1", "methods": {"b1": 2}}, "h2", False)
add("job_c_sha", "B0", "ds3", {"name": "B0", "methods": {"b0": 1}}, "daily-job", False)
add("t08b_champ", "C1", "t08b", {}, "t08b", False)                                   # campeao T08b sem 'methods'
add("t08b_champ_methods", "C1", "t08b2", {"methods": "lightgbm"}, "t08b", False)      # T08b com chave 'methods' nos hiperparametros (caso limite)
run("UPDATE model_run SET is_champion=FALSE"); run("UPDATE model_run SET is_champion=TRUE WHERE id IN (:a,:b)", a=ids["job_a"], b=ids["t08b_champ"])
before = [tuple(r) for r in run("SELECT id, model_version, role, is_champion FROM model_run ORDER BY id").all()]
print(json.dumps({"ids": ids, "antes": before}))
