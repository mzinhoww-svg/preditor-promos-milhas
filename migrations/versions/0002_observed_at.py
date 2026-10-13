"""raw_message.observed_at (spec 2.4) + source_health.robots_hash"""
from alembic import op

revision = "0002"
down_revision = "0001"

UP = """
ALTER TABLE raw_message ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ;
ALTER TABLE source_health ADD COLUMN IF NOT EXISTS robots_hash TEXT;
"""
DOWN = """
ALTER TABLE raw_message DROP COLUMN IF EXISTS observed_at;
ALTER TABLE source_health DROP COLUMN IF EXISTS robots_hash;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
