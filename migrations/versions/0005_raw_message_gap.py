"""raw_message.published_at e published_vs_capture_gap (backfill ponto-no-tempo)

Parent 0003 (main). Se a 0004 (calendar_seed, T08b) entrar antes, trocar down_revision para "0004".
"""
from alembic import op

revision = "0005"
down_revision = "0003"

UP = """
ALTER TABLE raw_message ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
ALTER TABLE raw_message ADD COLUMN IF NOT EXISTS published_vs_capture_gap BOOLEAN NOT NULL DEFAULT FALSE;
"""
DOWN = """
ALTER TABLE raw_message DROP COLUMN IF EXISTS published_vs_capture_gap;
ALTER TABLE raw_message DROP COLUMN IF EXISTS published_at;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
