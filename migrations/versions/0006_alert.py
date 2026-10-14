"""alert: registro de cruzamento de limiar de probabilidade (T10b; sem canal externo)."""
from alembic import op

revision = "0006"
down_revision = "0005"

UP = """
CREATE TABLE IF NOT EXISTS alert (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  made_at TIMESTAMPTZ NOT NULL,
  model_run_id BIGINT REFERENCES model_run(id) ON DELETE SET NULL,
  origin TEXT NOT NULL,
  destination TEXT NOT NULL,
  event_type TEXT NOT NULL,
  horizon_days INT NOT NULL CHECK (horizon_days IN (7,15,30)),
  probability NUMERIC(6,5) NOT NULL CHECK (probability BETWEEN 0 AND 1),
  previous_probability NUMERIC(6,5),
  threshold NUMERIC(6,5) NOT NULL CHECK (threshold BETWEEN 0 AND 1),
  UNIQUE (made_at, origin, destination, event_type, horizon_days, threshold)
);
CREATE INDEX IF NOT EXISTS alert_made_at_idx ON alert (made_at DESC);
"""
DOWN = "DROP TABLE IF EXISTS alert;"


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
