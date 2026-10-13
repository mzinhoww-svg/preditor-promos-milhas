"""schema inicial"""
from alembic import op

revision = "0001"
down_revision = None

UP = """
CREATE TABLE raw_message (
  id BIGSERIAL PRIMARY KEY,
  source TEXT NOT NULL,
  url TEXT NOT NULL,
  content TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  collected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source, content_hash)
);

CREATE TABLE offer (
  id BIGSERIAL PRIMARY KEY,
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  event_type TEXT NOT NULL CHECK (event_type IN
    ('transfer_bonus','purchase_discount','boosted_accrual')),
  start_at DATE NOT NULL,
  end_at DATE,
  bonus_pct NUMERIC(6,2),
  segmented BOOLEAN NOT NULL DEFAULT FALSE,
  segment_label TEXT NOT NULL DEFAULT '',
  first_seen_at TIMESTAMPTZ NOT NULL,
  n_sources INT NOT NULL DEFAULT 1,
  validated BOOLEAN NOT NULL DEFAULT FALSE,
  date_conflict BOOLEAN NOT NULL DEFAULT FALSE,
  weight NUMERIC(3,2) NOT NULL DEFAULT 0.5,
  UNIQUE (origin, destination, event_type, start_at, segmented, segment_label)
);

CREATE TABLE offer_evidence (
  id BIGSERIAL PRIMARY KEY,
  offer_id BIGINT NOT NULL REFERENCES offer(id),
  raw_message_id BIGINT NOT NULL REFERENCES raw_message(id),
  source TEXT NOT NULL,
  seen_start_at DATE NOT NULL,
  UNIQUE (offer_id, raw_message_id)
);

CREATE TABLE calendar_event (
  id BIGSERIAL PRIMARY KEY,
  name TEXT NOT NULL,
  kind TEXT NOT NULL,
  event_date DATE NOT NULL,
  UNIQUE (name, event_date)
);

CREATE TABLE source_health (
  source TEXT NOT NULL,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  items_new INT NOT NULL,
  extraction_rate NUMERIC(5,4),
  alert BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (source, checked_at)
);

CREATE TABLE model_run (
  id BIGSERIAL PRIMARY KEY,
  model_version TEXT NOT NULL,
  trained_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  dataset_version TEXT NOT NULL,
  feature_version TEXT NOT NULL,
  hyperparams JSONB NOT NULL,
  metrics JSONB NOT NULL,
  code_hash TEXT NOT NULL,
  is_champion BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE prediction (
  id BIGSERIAL PRIMARY KEY,
  made_at TIMESTAMPTZ NOT NULL,
  model_run_id BIGINT NOT NULL REFERENCES model_run(id),
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  event_type TEXT NOT NULL,
  horizon_days INT NOT NULL CHECK (horizon_days IN (7,15,30)),
  probability NUMERIC(6,5) NOT NULL CHECK (probability BETWEEN 0 AND 1),
  bonus_p25 NUMERIC(6,2), bonus_p50 NUMERIC(6,2), bonus_p75 NUMERIC(6,2),
  explanation JSONB,
  UNIQUE (made_at, model_run_id, origin, destination, event_type, horizon_days)
);

CREATE TABLE prediction_log (
  id BIGSERIAL PRIMARY KEY,
  logged_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  model_version TEXT NOT NULL,
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  event_type TEXT NOT NULL,
  horizon_days INT NOT NULL,
  probability NUMERIC(6,5) NOT NULL
);

CREATE FUNCTION prediction_log_immutable() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'prediction_log é somente de inserção';
END; $$ LANGUAGE plpgsql;

CREATE TRIGGER prediction_log_no_update
  BEFORE UPDATE OR DELETE ON prediction_log
  FOR EACH ROW EXECUTE FUNCTION prediction_log_immutable();
CREATE TRIGGER prediction_log_no_truncate
  BEFORE TRUNCATE ON prediction_log
  FOR EACH STATEMENT EXECUTE FUNCTION prediction_log_immutable();

CREATE TABLE budget_ledger (
  id BIGSERIAL PRIMARY KEY,
  provider TEXT NOT NULL,
  amount_brl NUMERIC(10,4) NOT NULL CHECK (amount_brl >= 0),
  recorded_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

DOWN = """
DROP TABLE IF EXISTS budget_ledger, prediction_log, prediction, model_run,
  source_health, calendar_event, offer_evidence, offer, raw_message CASCADE;
DROP FUNCTION IF EXISTS prediction_log_immutable();
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
