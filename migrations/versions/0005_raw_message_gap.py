"""raw_message.published_at e published_vs_capture_gap (backfill ponto-no-tempo)

Tambem offer_evidence.start_inferred (spec coletor-livelo-smiles 3.1: inicio nulo => start_at = first_seen).
"""
from alembic import op

revision = "0005"
down_revision = "0004"

UP = """
ALTER TABLE raw_message ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE raw_message ADD COLUMN IF NOT EXISTS published_vs_capture_gap BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE offer_evidence ADD COLUMN IF NOT EXISTS start_inferred BOOLEAN NOT NULL DEFAULT FALSE;
"""
DOWN = """
ALTER TABLE offer_evidence DROP COLUMN IF EXISTS start_inferred;
ALTER TABLE raw_message DROP COLUMN IF EXISTS published_vs_capture_gap;
ALTER TABLE raw_message DROP COLUMN IF EXISTS published_at;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
