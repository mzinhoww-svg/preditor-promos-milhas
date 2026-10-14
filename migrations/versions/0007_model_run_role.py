"""model_run.role: o run do job diario ('daily') nao e o campeao; so decide_champion muda is_champion.

Unicidade (versao, dados, codigo) para runs diarios: execucoes concorrentes reutilizam o mesmo run.
"""
from alembic import op

revision = "0007"
down_revision = "0006"

UP = """
ALTER TABLE model_run ADD COLUMN IF NOT EXISTS role TEXT NOT NULL DEFAULT 'experiment';
CREATE UNIQUE INDEX IF NOT EXISTS model_run_daily_uq
  ON model_run (model_version, dataset_version, code_hash) WHERE role = 'daily';
"""
DOWN = """
DROP INDEX IF EXISTS model_run_daily_uq;
ALTER TABLE model_run DROP COLUMN IF EXISTS role;
"""


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
