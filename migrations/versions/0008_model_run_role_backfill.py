"""Dados: runs gerados pelo job diario (antes do role) deixam de ser campeoes.

Runs com is_champion=TRUE criados pelo job (assinatura: code_hash 'daily-job' ou hyperparams com
'methods') viram role='daily' e is_champion=FALSE; o campeao do T08b (outros runs) e preservado.
Duplicatas do mesmo (versao, dados, codigo) ficam como 'daily_legacy' para respeitar o indice unico.
"""
from alembic import op

revision = "0008"
down_revision = "0007"

UP = """
WITH job_runs AS (
  SELECT id, model_version, dataset_version, code_hash,
         row_number() OVER (PARTITION BY model_version, dataset_version, code_hash ORDER BY id) AS rn
  FROM model_run
  WHERE role = 'experiment' AND (code_hash = 'daily-job' OR hyperparams ? 'methods')
)
UPDATE model_run m
SET role = CASE WHEN j.rn = 1 AND NOT EXISTS (
        SELECT 1 FROM model_run d WHERE d.role = 'daily' AND d.model_version = m.model_version
          AND d.dataset_version = m.dataset_version AND d.code_hash = m.code_hash)
      THEN 'daily' ELSE 'daily_legacy' END,
    is_champion = FALSE
FROM job_runs j WHERE m.id = j.id;
"""
DOWN = "SELECT 1;"  # dado: nao ha como restaurar quais runs eram campeoes


def upgrade() -> None:
    op.execute(UP)


def downgrade() -> None:
    op.execute(DOWN)
