import json, os
from sqlalchemy import create_engine, text
E = create_engine(os.environ["DATABASE_URL"])
with E.connect() as c:
    print(json.dumps([tuple(r) for r in c.execute(text("SELECT id, model_version, dataset_version, role, is_champion FROM model_run ORDER BY id"))]))
